import os
import argparse
import subprocess
import glob
import numpy as np
import nibabel as nib
from scipy.ndimage import label
from tqdm import tqdm

# ==========================================
# 1. METRIC CALCULATION LOGIC
# ==========================================
def compute_lesion_metrics(y_pred, y_gt):
    """
    Computes TP, FP, FN based on connected components (3D clusters).
    """
    structure = np.ones((3,3,3))
    pred_labels, num_pred = label(y_pred, structure=structure)
    gt_labels, num_gt = label(y_gt, structure=structure)
    
    tp = 0
    fp = 0
    fn = 0
    matched_pred_ids = set()
    
    # Analyze Ground Truths (Did we find them?)
    if num_gt > 0:
        for i in range(1, num_gt + 1):
            gt_mask = (gt_labels == i)
            overlap_ids = np.unique(pred_labels[gt_mask])
            overlap_ids = overlap_ids[overlap_ids != 0]
            
            if len(overlap_ids) > 0:
                tp += 1
                for oid in overlap_ids:
                    matched_pred_ids.add(oid)
            else:
                fn += 1
    
    # Analyze Predictions (Are they hallucinations?)
    if num_pred > 0:
        for i in range(1, num_pred + 1):
            if i not in matched_pred_ids:
                fp += 1

    return {"tp": tp, "fp": fp, "fn": fn, "num_gt": num_gt}

def get_dynamic_threshold(affine):
    """
    Calculates voxel threshold for a 3mm sphere based on image spacing.
    """
    zooms = np.sqrt(np.sum(affine[:3, :3] ** 2, axis=0))
    spacing_vol = zooms[0] * zooms[1] * zooms[2]
    target_vol_mm3 = (4/3) * np.pi * ((3.0/2)**3) # ~14.13 mm3
    return int(target_vol_mm3 / spacing_vol)

# ==========================================
# 2. MAIN SCRIPT
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Run nnU-Net Inference & Custom Evaluation")
    parser.add_argument("-d", "--dataset", type=str, required=True, help="Dataset ID (e.g., 101)")
    parser.add_argument("-c", "--config", type=str, default="2d", help="Configuration (2d, 3d_fullres)")
    parser.add_argument("-f", "--fold", type=str, default="0", help="Fold number")
    parser.add_argument("--tta", action="store_true", help="Activate Test Time Augmentation (8x slower, better results)")
    parser.add_argument("--raw_dir", type=str, default="./nnUNet_raw", help="Path to nnUNet_raw")
    parser.add_argument("--results_dir", type=str, default="./nnUNet_results", help="Path to nnUNet_results")
    args = parser.parse_args()

    # --- PATH SETUP ---
    dataset_name = glob.glob(os.path.join(args.raw_dir, f"Dataset{args.dataset}*"))[0].split("/")[-1]
    
    # Input Images (Test set)
    # NOTE: nnU-Net defaults to 'imagesTs'. If you want to eval on 'imagesTr', change this path.
    input_folder = os.path.join(args.raw_dir, dataset_name, "imagesTs")
    
    # Ground Truth Labels
    gt_folder = os.path.join(args.raw_dir, dataset_name, "labelsTs")
    
    # Output Prediction Folder
    chk_name = "checkpoint_best.pth"
    out_folder_name = f"pred_{args.config}_fold{args.fold}_{'tta' if args.tta else 'no_tta'}"
    output_folder = os.path.join(args.results_dir, dataset_name, out_folder_name)

    print(f"--- CONFIGURATION ---")
    print(f"Dataset: {dataset_name}")
    print(f"Input:   {input_folder}")
    print(f"GT:      {gt_folder}")
    print(f"Output:  {output_folder}")
    print(f"TTA:     {'ENABLED' if args.tta else 'DISABLED'}")
    print("---------------------")

    # --- STEP 1: RUN NNUNET PREDICTION ---
    # nnU-Net v2 enables TTA by default. We use --disable_tta if the user didn't ask for it.
    
    cmd = [
        "nnUNetv2_predict",
        "-i", input_folder,
        "-o", output_folder,
        "-d", args.dataset,
        "-c", args.config,
        "-f", args.fold,
        "-chk", chk_name, 
        "-npp", "8",
        "-nps", "8"
    ]
    
    if not args.tta:
        cmd.append("--disable_tta")
        
    print("\n>>> Running nnUNetv2_predict (This may take a while)...")
    subprocess.check_call(cmd)
    print(">>> Prediction Complete.")

    # --- STEP 2: RUN CUSTOM EVALUATION ---
    print("\n>>> Computing LUNA16 Metrics (TP/FP/FN/Dice)...")
    
    pred_files = glob.glob(os.path.join(output_folder, "*.nii.gz"))
    
    agg_tp = 0
    agg_fp = 0
    agg_fn = 0
    tumor_dice_sum = 0.0
    num_sick_patients = 0
    
    for pred_path in tqdm(pred_files):
        filename = os.path.basename(pred_path)
        gt_path = os.path.join(gt_folder, filename)
        
        if not os.path.exists(gt_path):
            print(f"Warning: No Ground Truth found for {filename}, skipping metrics.")
            continue
            
        # Load Nifti
        pred_nii = nib.load(pred_path)
        gt_nii = nib.load(gt_path)
        
        pred_data = pred_nii.get_fdata().astype(np.uint8)
        gt_data = gt_nii.get_fdata().astype(np.uint8)
        
        # 1. Clean Small Objects (Dynamic Thresholding like your script)
        min_voxels = get_dynamic_threshold(pred_nii.affine)
        
        # Remove small objects from prediction
        structure = np.ones((3,3,3))
        lbls, num = label(pred_data, structure)
        sizes = np.bincount(lbls.ravel())
        mask_sizes = sizes > min_voxels
        mask_sizes[0] = 0 # Background
        pred_clean = mask_sizes[lbls].astype(np.uint8)
        
        # 2. Compute Dice
        intersection = np.sum(pred_clean * gt_data)
        union = np.sum(pred_clean) + np.sum(gt_data)
        
        if np.sum(gt_data) > 0:
            dice = (2. * intersection) / union if union > 0 else 0.0
            tumor_dice_sum += dice
            num_sick_patients += 1
            
        # 3. Compute Lesion Metrics (TP/FP/FN)
        m = compute_lesion_metrics(pred_clean, gt_data)
        agg_tp += m["tp"]
        agg_fp += m["fp"]
        agg_fn += m["fn"]

    # --- FINAL REPORT ---
    final_dice = tumor_dice_sum / num_sick_patients if num_sick_patients > 0 else 0.0
    
    total_gt = agg_tp + agg_fn
    recall = agg_tp / total_gt if total_gt > 0 else 0.0
    
    total_pred = agg_tp + agg_fp
    precision = agg_tp / total_pred if total_pred > 0 else 0.0
    
    fps_per_scan = agg_fp / len(pred_files) if len(pred_files) > 0 else 0.0

    print("\n" + "="*40)
    print(f" CUSTOM RESULTS (Best Checkpoint)")
    print("="*40)
    print(f" Tumor Dice (Avg)     : {final_dice:.4f}")
    print(f" Recall (Sensitivity) : {recall:.4f}")
    print(f" Precision            : {precision:.4f}")
    print(f" FPs / Scan           : {fps_per_scan:.2f}")
    print(f" Counts -> TP:{agg_tp} FP:{agg_fp} FN:{agg_fn}")
    print("="*40)

if __name__ == "__main__":
    main()