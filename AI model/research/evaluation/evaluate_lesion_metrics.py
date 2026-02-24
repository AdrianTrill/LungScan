import os
import argparse
import subprocess
import glob
import numpy as np
import nibabel as nib
from scipy.ndimage import label
from tqdm import tqdm
import multiprocessing

# ==========================================
# 1. WORKER FUNCTION (Parallel Processing)
# ==========================================
def process_patient(args_tuple):
    pred_path, gt_folder, min_dia, threshold = args_tuple
    
    # Handle filename differences (.npz vs .nii.gz)
    is_npz = pred_path.endswith(".npz")
    filename_base = os.path.basename(pred_path).replace(".npz", ".nii.gz")
    gt_path = os.path.join(gt_folder, filename_base)
    
    if not os.path.exists(gt_path):
        return None

    try:
        # --- LOAD GROUND TRUTH ---
        gt_nii = nib.load(gt_path)
        gt_data = gt_nii.get_fdata().astype(np.uint8)
        current_affine = gt_nii.affine

        # --- LOAD PREDICTION ---
        if is_npz:
            # Load Probabilities (No Threshold Applied Yet)
            npz_content = np.load(pred_path)
            probs = npz_content['probabilities'] # Shape (C, Z, Y, X)
            
            # Select Tumor Channel (usually index 1)
            channel_idx = 1 if probs.shape[0] > 1 else 0
            tumor_prob = probs[channel_idx]
            
            # CRITICAL FIX: Transpose (Z, Y, X) -> (X, Y, Z)
            # nnU-Net saves .npz in ZYX, but Nifti GT is XYZ.
            if tumor_prob.ndim == 3:
                tumor_prob = tumor_prob.transpose((2, 1, 0))
            
            # Apply Custom Threshold
            pred_data = (tumor_prob > threshold).astype(np.uint8)
            
        else:
            # Load Standard Mask (Hard 0.5 threshold baked in)
            pred_nii = nib.load(pred_path)
            pred_data = pred_nii.get_fdata().astype(np.uint8)

        # Safety Check: Shapes must match now
        if pred_data.shape != gt_data.shape:
            # If still mismatching, try to force fit (rare edge case)
            return None 

        # --- CLEAN PREDICTIONS (< min_dia) ---
        # Dynamic threshold based on voxel size
        zooms = np.sqrt(np.sum(current_affine[:3, :3] ** 2, axis=0))
        spacing_vol = np.prod(zooms)
        radius = min_dia / 2.0
        target_vol_mm3 = (4/3) * np.pi * (radius ** 3)
        min_voxels = int(target_vol_mm3 / spacing_vol)

        structure = np.ones((3,3,3))
        lbls, num = label(pred_data, structure)
        sizes = np.bincount(lbls.ravel())
        mask = sizes > min_voxels
        mask[0] = 0
        pred_clean = mask[lbls].astype(np.uint8)

        # --- METRIC 1: VOLUMETRIC DICE ---
        intersection = np.sum(pred_clean * gt_data)
        total_vol = np.sum(pred_clean) + np.sum(gt_data)
        vol_dice = (2. * intersection) / total_vol if total_vol > 0 else 0.0
        
        is_healthy_patient = (np.sum(gt_data) == 0)
        
        # If healthy and we predicted nothing -> Perfect score (technically)
        if is_healthy_patient and np.sum(pred_clean) == 0:
            vol_dice = 1.0 

        # --- METRIC 2: LESION-WISE (TP, FP, FN) ---
        pred_lbls, n_pred = label(pred_clean, structure)
        gt_lbls, n_gt = label(gt_data, structure)

        tp, fp, fn = 0, 0, 0
        lesion_dice_sum = 0.0
        matched_pred_ids = set()

        if n_gt > 0:
            for i in range(1, n_gt + 1):
                gt_nodule_mask = (gt_lbls == i)
                overlap_ids = np.unique(pred_lbls[gt_nodule_mask])
                overlap_ids = overlap_ids[overlap_ids != 0]
                
                if len(overlap_ids) > 0:
                    tp += 1
                    for oid in overlap_ids: matched_pred_ids.add(oid)
                    
                    # Lesion Dice
                    pred_compound_mask = np.isin(pred_lbls, overlap_ids)
                    inter_l = np.logical_and(gt_nodule_mask, pred_compound_mask).sum()
                    union_l = gt_nodule_mask.sum() + pred_compound_mask.sum()
                    lesion_dice_sum += (2.0 * inter_l) / (union_l + 1e-6)
                else:
                    fn += 1

        if n_pred > 0:
            for i in range(1, n_pred + 1):
                if i not in matched_pred_ids:
                    fp += 1

        return {
            "vol_dice": vol_dice,
            "is_healthy": is_healthy_patient,
            "tp": tp, "fp": fp, "fn": fn,
            "lesion_dice_sum": lesion_dice_sum
        }

    except Exception as e:
        return None

# ==========================================
# 2. MAIN SCRIPT
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Unified Evaluation Script")
    parser.add_argument("-d", "--dataset", required=True, help="Dataset ID (e.g. 101)")
    parser.add_argument("-c", "--config", type=str, default="2d", help="nnUNet Config (2d, 3d_fullres)")
    parser.add_argument("-f", "--fold", type=str, default="0")
    parser.add_argument("--threshold", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--min_diameter", type=float, default=3.0, help="Min nodule size (mm)")
    parser.add_argument("--tta", action="store_true")
    parser.add_argument("--force_predict", action="store_true", help="Force re-running inference")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--raw_dir", type=str, default="./nnUNet_raw")
    parser.add_argument("--results_dir", type=str, default="./nnUNet_results")
    args = parser.parse_args()

    # --- SETUP PATHS ---
    try:
        ds_name = glob.glob(os.path.join(args.raw_dir, f"Dataset{args.dataset}*"))[0].split("/")[-1]
    except IndexError:
        print(f"Error: Dataset{args.dataset} not found in {args.raw_dir}")
        return

    input_folder = os.path.join(args.raw_dir, ds_name, "imagesTs")
    gt_folder = os.path.join(args.raw_dir, ds_name, "labelsTs")
    out_folder_name = f"pred_{args.config}_fold{args.fold}_{'tta' if args.tta else 'no_tta'}"
    output_folder = os.path.join(args.results_dir, ds_name, out_folder_name)

    print(f"--- CONFIGURATION ---")
    print(f"Dataset:   {ds_name}")
    print(f"Config:    {args.config}")
    print(f"Threshold: {args.threshold}")
    print(f"Output:    {output_folder}")

    # --- INFERENCE CHECK ---
    # We prefer .npz if threshold != 0.5, otherwise .nii.gz is fine
    need_probs = args.threshold != 0.5
    existing_npz = glob.glob(os.path.join(output_folder, "*.npz"))
    existing_nii = glob.glob(os.path.join(output_folder, "*.nii.gz"))
    
    run_inference = False
    if args.force_predict:
        print(">>> Force Predict ON.")
        run_inference = True
    elif need_probs and len(existing_npz) == 0:
        print(">>> Probabilities (.npz) needed but not found. Running inference...")
        run_inference = True
    elif not need_probs and len(existing_nii) == 0:
        print(">>> Masks (.nii.gz) needed but not found. Running inference...")
        run_inference = True
    else:
        print(f">>> Found existing files ({len(existing_npz) if need_probs else len(existing_nii)}). Skipping Inference.")

    if run_inference:
        cmd = [
            "nnUNetv2_predict",
            "-i", input_folder,
            "-o", output_folder,
            "-d", args.dataset,
            "-c", args.config,
            "-f", args.fold,
            "-chk", "checkpoint_best.pth",
            "-npp", "8", "-nps", "8"
        ]
        if not args.tta: cmd.append("--disable_tta")
        # Always save probabilities just in case we want to tune later
        cmd.append("--save_probabilities")
        
        print(">>> Running nnUNetv2_predict...")
        subprocess.check_call(cmd)

    # --- EVALUATION ---
    print(f"\n>>> Computing Metrics (Threshold > {args.threshold})...")
    
    # Select files to process
    if need_probs:
        pred_files = glob.glob(os.path.join(output_folder, "*.npz"))
    else:
        pred_files = glob.glob(os.path.join(output_folder, "*.nii.gz"))

    if not pred_files:
        print("Error: No prediction files found.")
        return

    # Pack arguments for workers
    worker_args = [(p, gt_folder, args.min_diameter, args.threshold) for p in pred_files]

    # Run Parallel Processing
    with multiprocessing.Pool(args.workers) as pool:
        results = list(tqdm(pool.imap(process_patient, worker_args), total=len(worker_args)))

    # --- AGGREGATION ---
    agg_vol_dice = []
    total_healthy = 0
    healthy_correct = 0
    
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_lesion_dice = 0.0

    for res in results:
        if res is None: continue
        
        if res['is_healthy']:
            total_healthy += 1
            if res['fp'] == 0: healthy_correct += 1
        else:
            agg_vol_dice.append(res['vol_dice'])
            
        total_tp += res['tp']
        total_fp += res['fp']
        total_fn += res['fn']
        total_lesion_dice += res['lesion_dice_sum']

    # Final Math
    mean_vol_dice = np.mean(agg_vol_dice) if agg_vol_dice else 0.0
    specificity = healthy_correct / total_healthy if total_healthy > 0 else 0.0
    
    total_gt = total_tp + total_fn
    recall = total_tp / total_gt if total_gt > 0 else 0.0
    
    total_pred = total_tp + total_fp
    precision = total_tp / total_pred if total_pred > 0 else 0.0
    
    fps_per_scan = total_fp / len(results) if len(results) > 0 else 0.0
    mean_lesion_dice = total_lesion_dice / total_tp if total_tp > 0 else 0.0

    # --- PRINT FINAL REPORT ---
    print("\n" + "="*50)
    print(f" FINAL REPORT | {ds_name}")
    print(f" Config: {args.config} | Thresh: {args.threshold}")
    print("="*50)
    print(f" Scans Analyzed:        {len(results)}")
    print(f"    - Sick:             {len(results) - total_healthy}")
    print(f"    - Healthy:          {total_healthy}")
    print("-" * 50)
    print(f" 1. TUMOR SEGMENTATION (Sick Only)")
    print(f"    Mean Volumetric Dice: {mean_vol_dice:.4f}")
    print("-" * 50)
    print(f" 2. SCREENING PERFORMANCE (Healthy Only)")
    print(f"    Specificity:          {specificity:.4f} (Healthy scans with 0 preds)")
    print("-" * 50)
    print(f" 3. DETECTION ACCURACY (Global)")
    print(f"    Recall (Sens):        {recall:.4f} ({total_tp}/{total_gt} nodules found)")
    print(f"    Precision:            {precision:.4f} (TP / (TP+FP))")
    print(f"    FPs / Scan:           {fps_per_scan:.2f}")
    print("-" * 50)
    print(f" 4. LESION QUALITY (TPs Only)")
    print(f"    Mean Lesion Dice:     {mean_lesion_dice:.4f}")
    print("="*50)

if __name__ == "__main__":
    main()