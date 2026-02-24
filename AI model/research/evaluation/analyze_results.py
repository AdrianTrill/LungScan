import json
import numpy as np
import argparse
import os

def analyze_json(json_path):
    if not os.path.exists(json_path):
        print(f"Error: File not found at {json_path}")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    all_cases = data['metric_per_case']
    
    sick_cases = []      # Patients who have nodules (Ground Truth > 0)
    healthy_cases = []   # Patients who are clean (Ground Truth == 0)

    # 1. Separate the dataset
    for case in all_cases:
        # nnU-Net keys metrics by class "1" usually
        metrics = case['metrics'].get('1') or case['metrics'].get('0')
        
        # n_ref = Number of Reference (Ground Truth) voxels
        if metrics['n_ref'] > 0:
            sick_cases.append(metrics)
        else:
            healthy_cases.append(metrics)

    # 2. Compute Metrics for SICK Patients (The ones that matter for Dice)
    sick_dices = [c['Dice'] for c in sick_cases]
    sick_ious = [c['IoU'] for c in sick_cases]
    
    # Voxel-level Recall (Sensitivity) = TP / (TP + FN)
    total_tp = sum([c['TP'] for c in sick_cases])
    total_fn = sum([c['FN'] for c in sick_cases])
    voxel_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0

    # 3. Compute Metrics for HEALTHY Patients (False Alarm Rate)
    # How many healthy patients did we accidentally predict a tumor for?
    false_positives_count = sum(1 for c in healthy_cases if c['n_pred'] > 0)
    fp_rate = false_positives_count / len(healthy_cases) if healthy_cases else 0

    print("="*50)
    print(f" RE-EVALUATION REPORT (Filtering Healthy Patients)")
    print("="*50)
    print(f"Total Cases:   {len(all_cases)}")
    print(f"  - Sick:      {len(sick_cases)}")
    print(f"  - Healthy:   {len(healthy_cases)}")
    print("-" * 50)
    
    print(f"SICK PATIENTS (Target Metrics):")
    print(f"  Mean Dice:        {np.mean(sick_dices):.4f}")
    print(f"  Median Dice:      {np.median(sick_dices):.4f}")
    print(f"  Mean IoU:         {np.mean(sick_ious):.4f}")
    print(f"  Voxel Recall:     {voxel_recall:.4f}")
    print("-" * 50)
    
    print(f"HEALTHY PATIENTS (False Alarms):")
    if healthy_cases:
        print(f"  False Positive Rate: {fp_rate*100:.1f}% of healthy scans had predictions")
        print(f"  Avg FP Voxels:       {np.mean([c['n_pred'] for c in healthy_cases]):.1f}")
    else:
        print("  No healthy patients found in this split.")
    print("="*50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Default path based on your previous logs
    parser.add_argument('file', nargs='?', default="nnUNet_results/Dataset101_LIDC/pred_2d_fold0_tta/summary.json", help="Path to summary.json")
    args = parser.parse_args()
    
    analyze_json(args.file)