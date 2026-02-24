import os
import argparse
import glob
import numpy as np
import nibabel as nib
from scipy.ndimage import label
from tqdm import tqdm
import multiprocessing

# ==========================================
# 1. HELPER: Calculate Voxel Threshold
# ==========================================
def get_min_voxels(affine, diameter_mm):
    """
    Calculates how many voxels make up a sphere of diameter_mm.
    """
    # Get voxel spacing (e.g., [0.7, 0.7, 2.5])
    zooms = np.sqrt(np.sum(affine[:3, :3] ** 2, axis=0))
    voxel_vol = np.prod(zooms)
    
    # Calculate sphere volume: 4/3 * pi * r^3
    radius = diameter_mm / 2.0
    sphere_vol = (4/3) * np.pi * (radius ** 3)
    
    return int(sphere_vol / voxel_vol)

# ==========================================
# 2. WORKER: Process Single Case
# ==========================================
def process_case(args_tuple):
    pred_path, gt_folder, min_dia = args_tuple
    filename = os.path.basename(pred_path)
    gt_path = os.path.join(gt_folder, filename)
    
    if not os.path.exists(gt_path):
        return None

    try:
        # Load Nifti
        pred_nii = nib.load(pred_path)
        gt_nii = nib.load(gt_path)
        pred_data = pred_nii.get_fdata().astype(np.uint8)
        gt_data = gt_nii.get_fdata().astype(np.uint8)

        # --- STEP A: FILTER SMALL PREDICTIONS ---
        if min_dia > 0:
            min_voxels = get_min_voxels(pred_nii.affine, min_dia)
            
            # Label connected components
            structure = np.ones((3,3,3))
            lbls, num_feats = label(pred_data, structure)
            
            if num_feats > 0:
                sizes = np.bincount(lbls.ravel())
                # Create mask of components larger than threshold
                # (sizes > min_voxels) returns boolean, we index into it with lbls
                mask_keep = sizes > min_voxels
                mask_keep[0] = 0 # Ensure background is 0
                pred_data = mask_keep[lbls].astype(np.uint8)
        
        # --- STEP B: COMPUTE METRICS ---
        is_sick = np.sum(gt_data) > 0
        dice = 0.0
        
        if is_sick:
            intersection = np.sum(pred_data * gt_data)
            union = np.sum(pred_data) + np.sum(gt_data)
            if union > 0:
                dice = (2. * intersection) / union
        
        # TP/FP/FN Logic (Object Detection)
        structure = np.ones((3,3,3))
        pred_lbls, n_pred = label(pred_data, structure)
        gt_lbls, n_gt = label(gt_data, structure)
        
        tp = 0
        matched_pred_ids = set()
        
        # Check GTs found
        if n_gt > 0:
            for i in range(1, n_gt + 1):
                gt_mask = (gt_lbls == i)
                overlaps = np.unique(pred_lbls[gt_mask])
                overlaps = overlaps[overlaps != 0]
                if len(overlaps) > 0:
                    tp += 1
                    for oid in overlaps: matched_pred_ids.add(oid)
        
        fn = n_gt - tp
        fp = 0
        if n_pred > 0:
            for i in range(1, n_pred + 1):
                if i not in matched_pred_ids: fp += 1

        return {
            "is_sick": is_sick,
            "dice": dice,
            "tp": tp, "fp": fp, "fn": fn
        }

    except Exception as e:
        print(f"Error {filename}: {e}")
        return None

# ==========================================
# 3. MAIN
# ==========================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dataset", required=True, help="Dataset ID (e.g., 101)")
    parser.add_argument("--pred_folder", required=True, help="Path to predictions folder")
    parser.add_argument("--min_diameter", type=float, default=2.0, help="Minimum diameter (mm) to keep")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    # Paths
    raw_dir = "./nnUNet_raw"
    dataset_name = glob.glob(os.path.join(raw_dir, f"Dataset{args.dataset}*"))[0].split("/")[-1]
    gt_folder = os.path.join(raw_dir, dataset_name, "labelsTs")
    
    pred_files = glob.glob(os.path.join(args.pred_folder, "*.nii.gz"))
    
    print(f"--- EVALUATION SETTINGS ---")
    print(f"Dataset:       {dataset_name}")
    print(f"Filter:        Ignore predictions < {args.min_diameter} mm")
    print(f"Predictions:   {len(pred_files)} files")
    print(f"Ground Truth:  {gt_folder}")
    print("---------------------------")

    # Run Parallel
    worker_args = [(p, gt_folder, args.min_diameter) for p in pred_files]
    
    with multiprocessing.Pool(args.workers) as pool:
        results = list(tqdm(pool.imap(process_case, worker_args), total=len(pred_files)))

    # Aggregation
    sick_dice_sum = 0.0
    sick_count = 0
    
    healthy_fps = 0
    healthy_count = 0
    
    total_tp, total_fp, total_fn = 0, 0, 0
    
    for res in results:
        if res is None: continue
        
        total_tp += res['tp']
        total_fp += res['fp']
        total_fn += res['fn']
        
        if res['is_sick']:
            sick_dice_sum += res['dice']
            sick_count += 1
        else:
            healthy_fps += res['fp']
            healthy_count += 1

    # Final Calcs
    avg_dice_sick = sick_dice_sum / sick_count if sick_count > 0 else 0.0
    avg_fp_healthy = healthy_fps / healthy_count if healthy_count > 0 else 0.0
    
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    fps_per_scan = total_fp / len(results)

    print("\n" + "="*50)
    print(f" RESULTS (Filtered > {args.min_diameter}mm)")
    print("="*50)
    print(f" SICK PATIENTS ({sick_count} cases)")
    print(f"   Dice Score (Avg):    {avg_dice_sick:.4f}")
    print(f"   Recall (Sensitivity):{recall:.4f}")
    print("-" * 50)
    print(f" HEALTHY PATIENTS ({healthy_count} cases)")
    print(f"   Avg FPs per scan:    {avg_fp_healthy:.2f}")
    print("-" * 50)
    print(f" GLOBAL METRICS")
    print(f"   Precision:           {precision:.4f}")
    print(f"   Total FPs / Scan:    {fps_per_scan:.2f}")
    print(f"   Counts -> TP:{total_tp}  FP:{total_fp}  FN:{total_fn}")
    print("="*50)

if __name__ == "__main__":
    main()