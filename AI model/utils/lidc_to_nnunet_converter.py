import os
import json
import random
import numpy as np
import pylidc as pl
import nibabel as nib
import multiprocessing
from tqdm import tqdm
from functools import partial
from pylidc.utils import consensus

# ================= CONFIGURATION =================
# 1. PATHS
# POINT THIS TO WHERE YOUR "1.3.6..." FOLDERS ARE
TCIA_LOCAL_DIR = "/home/shadeform/work/tciaDownload" 

# Where nnUNet expects raw data
NNUNET_RAW_DIR = "nnUNet_raw" 
TASK_NAME = "Dataset202_LIDC"

# 2. SETTINGS
SEED = 42
TEST_SPLIT = 0.2
NUM_WORKERS = max(1, multiprocessing.cpu_count() - 2) # Leave 2 cores free
# =================================================

# --- PART A: PATCH FUNCTIONS (Must be global for workers) ---
def apply_patches():
    """Applies Numpy and Pylidc patches to the current process"""
    import numpy
    if not hasattr(numpy, 'int'): numpy.int = int
    if not hasattr(numpy, 'float'): numpy.float = float
    if not hasattr(numpy, 'bool'): numpy.bool = bool

    # Apply Path Override
    pl.Scan.get_path_to_dicom_files = get_path_override

def get_path_override(self):
    """Force pylidc to look for SeriesUID folders"""
    # Check if a folder with the Series UID exists directly in root
    uid_path = os.path.join(TCIA_LOCAL_DIR, self.series_instance_uid)
    if os.path.exists(uid_path):
        return uid_path
    
    # Check fallback (PatientID/SeriesUID style)
    nested_path = os.path.join(TCIA_LOCAL_DIR, self.patient_id, self.series_instance_uid)
    if os.path.exists(nested_path):
        return nested_path
        
    return os.path.join(TCIA_LOCAL_DIR, self.patient_id)

def get_affine_from_scan(scan):
    """Constructs a valid affine matrix preserving Spacing AND Origin."""
    try:
        dcm_images = scan.load_all_dicom_images(verbose=False)
        first_slice = dcm_images[0]
        
        spacings = [scan.pixel_spacing, scan.pixel_spacing, scan.slice_spacing]
        origin = first_slice.ImagePositionPatient
        
        affine = np.eye(4)
        affine[0, 0] = spacings[0]
        affine[1, 1] = spacings[1]
        affine[2, 2] = spacings[2]
        
        affine[0, 3] = origin[0]
        affine[1, 3] = origin[1]
        affine[2, 3] = origin[2]
        
        return affine
    except Exception:
        spacing = np.array([scan.pixel_spacing, scan.pixel_spacing, scan.slice_spacing]).flatten()
        affine = np.eye(4)
        affine[0, 0] = spacing[0]
        affine[1, 1] = spacing[1]
        affine[2, 2] = spacing[2]
        return affine

# --- WORKER FUNCTION ---
def process_scan_wrapper(args):
    """
    Unpacks arguments and runs processing for a single scan.
    Returns: Dict entry for dataset.json if successful, else None.
    """
    scan_id, is_train, dirs = args
    
    # Re-query the scan inside the worker process to avoid pickling issues
    # Note: apply_patches() is called by the pool initializer, so paths work.
    try:
        scan = pl.query(pl.Scan).filter(pl.Scan.id == scan_id).first()
        if not scan: return None

        # Check path existence
        dicom_path = scan.get_path_to_dicom_files()
        if not os.path.exists(dicom_path):
            return None

        # Naming
        series_uid = scan.series_instance_uid.replace('.', '')[-10:]
        case_id = f"LIDC_{scan.patient_id}_{series_uid}"
        img_filename = f"{case_id}_0000.nii.gz"
        lbl_filename = f"{case_id}.nii.gz"

        dest_img_dir = dirs["tr_img"] if is_train else dirs["ts_img"]
        dest_lbl_dir = dirs["tr_lbl"] if is_train else dirs["ts_lbl"]
        out_img_path = os.path.join(dest_img_dir, img_filename)
        out_lbl_path = os.path.join(dest_lbl_dir, lbl_filename)

        # Skip if exists
        if os.path.exists(out_img_path) and os.path.exists(out_lbl_path):   
            if is_train:
                return {"image": f"./imagesTr/{img_filename}", "label": f"./labelsTr/{lbl_filename}"}
            return "EXISTS_TEST"
        # Processing
        vol = scan.to_volume(verbose=False)
        mask = np.zeros(vol.shape, dtype=np.uint8)
        v_shape = vol.shape
        
        cluster_annotations = scan.cluster_annotations()
        
        if cluster_annotations:
            for cluster in cluster_annotations:
                if len(cluster) < 3: continue
                avg_diameter = np.mean([ann.diameter for ann in cluster])
                if avg_diameter < 3.0: continue

                try:
                    cmask, cbbox, _ = consensus(cluster, clevel=0.5, pad=[(0,0), (0,0), (0,0)])
                    
                    b_start = [cbbox[0].start, cbbox[1].start, cbbox[2].start]
                    b_stop  = [cbbox[0].stop,  cbbox[1].stop,  cbbox[2].stop]
                    
                    vol_slice = tuple(slice(max(0, s), min(d, e)) for s, e, d in zip(b_start, b_stop, v_shape))
                    mask_slice = tuple(slice(max(0, -s), max(0, -s) + (min(d, e) - max(0, s))) for s, e, d in zip(b_start, b_stop, v_shape))

                    if mask[vol_slice].shape == cmask[mask_slice].shape:
                        combined = np.logical_or(mask[vol_slice], cmask[mask_slice])
                        mask[vol_slice] = combined.astype(np.uint8)
                except Exception:
                    continue

        # Save
        affine = get_affine_from_scan(scan)
        nib.save(nib.Nifti1Image(vol.astype(np.float32), affine), out_img_path)
        nib.save(nib.Nifti1Image(mask.astype(np.uint8), affine), out_lbl_path)

        if is_train:
            return {"image": f"./imagesTr/{img_filename}", "label": f"./labelsTr/{lbl_filename}"}
        else:
            return "SUCCESS_TEST" # Just a marker that we succeeded

    except Exception as e:
        # return f"ERROR: {e}" # Uncomment to debug specific files
        return None

def main():
    # 1. Setup
    apply_patches() # Apply in main process too for the initial query
    
    task_dir = os.path.join(NNUNET_RAW_DIR, TASK_NAME)
    dirs = {
        "tr_img": os.path.join(task_dir, "imagesTr"),
        "tr_lbl": os.path.join(task_dir, "labelsTr"),
        "ts_img": os.path.join(task_dir, "imagesTs"),
        "ts_lbl": os.path.join(task_dir, "labelsTs") 
    }
    for d in dirs.values(): os.makedirs(d, exist_ok=True)

    # 2. Config File for Pylidc (must exist for workers)
    with open(os.path.expanduser("~/.pylidcrc"), "w") as f:
        f.write(f"[dicom]\npath={TCIA_LOCAL_DIR}\nwarn=yes\n")

    print(f"--- Parallel Processing ({NUM_WORKERS} Cores) ---")
    print("Querying Database...")
    scans = pl.query(pl.Scan).all()
    
    # Filter
    valid_scans = [s for s in scans if s.slice_thickness <= 2.5]
    print(f"Valid Scans: {len(valid_scans)} (filtered from {len(scans)})")

    # Split
    patient_ids = sorted(list(set(s.patient_id for s in valid_scans)))
    random.seed(SEED)
    random.shuffle(patient_ids)
    
    split_idx = int(len(patient_ids) * (1 - TEST_SPLIT))
    train_patients = set(patient_ids[:split_idx])

    # Prepare Arguments for Workers
    # We pass scan ID instead of the object to be pickle-safe
    worker_args = []
    for s in valid_scans:
        is_train = s.patient_id in train_patients
        worker_args.append((s.id, is_train, dirs))

    # 3. RUN PARALLEL POOL
    training_entries = []
    
    # We use 'spawn' or 'fork' depending on OS, but standard Pool usually defaults correctly on Linux
    # initializer=apply_patches ensures every worker has the path fix
    with multiprocessing.Pool(processes=NUM_WORKERS, initializer=apply_patches) as pool:
        results = list(tqdm(pool.imap(process_scan_wrapper, worker_args), total=len(worker_args)))

    # 4. Aggregate Results
    for res in results:
        if isinstance(res, dict):
            training_entries.append(res)
        elif res == "SUCCESS_TEST" or res == "EXISTS_TEST":
            pass # Counted as success but not added to training json
            
    # 5. Generate JSON
    json_dict = {
        "channel_names": {"0": "CT"},
        "labels": {"background": 0, "nodule": 1},
        "numTraining": len(training_entries),
        "file_ending": ".nii.gz",
        "name": TASK_NAME,
        "description": "LIDC-IDRI",
        "training": training_entries
    }

    json_path = os.path.join(task_dir, "dataset.json")
    with open(json_path, 'w') as f:
        json.dump(json_dict, f, indent=4)

    print(f"\nDone! Processed {len(training_entries)} training samples.")

if __name__ == "__main__":
    # Needed for multiprocessing on some OS
    multiprocessing.freeze_support()
    main()