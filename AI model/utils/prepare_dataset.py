import os
import json
import numpy as np
import pylidc as pl
import nibabel as nib
from tqdm import tqdm
from pylidc.utils import consensus  # <--- FIXED IMPORT
import config as cfg

# --- CRITICAL: PYLIDC MONKEY PATCH ---
import numpy
if not hasattr(numpy, 'int'): numpy.int = int
if not hasattr(numpy, 'float'): numpy.float = float
if not hasattr(numpy, 'bool'): numpy.bool = bool

def get_affine_from_scan(scan):
    """
    Constructs a valid affine matrix preserving Spacing AND Origin.
    """
    try:
        first_slice = scan.images[0]
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
    except Exception as e:
        # Fallback if DICOM header is missing info
        spacing = np.array([scan.pixel_spacing, scan.pixel_spacing, scan.slice_spacing]).flatten()
        affine = np.eye(4)
        affine[0, 0] = spacing[0]
        affine[1, 1] = spacing[1]
        affine[2, 2] = spacing[2]
        return affine

def preprocess_lidc_sota():
    os.makedirs(os.path.join(cfg.DATA_ROOT, "images"), exist_ok=True)
    os.makedirs(os.path.join(cfg.DATA_ROOT, "labels"), exist_ok=True)

    print("Querying LIDC-IDRI database...")
    scans = pl.query(pl.Scan).all()
    print(f"Found {len(scans)} scans.")

    valid_entries = []

    # Iterate with index to catch problematic files easily
    for scan in tqdm(scans, desc="Processing LIDC"):
        try:
            # 1. Check for Annotations
            cluster_annotations = scan.cluster_annotations()
            
            if not cluster_annotations:
                continue

            # 2. Reconstruct Volume (HU)
            vol = scan.to_volume(verbose=False)
            mask = np.zeros(vol.shape, dtype=np.uint8)
            v_shape = vol.shape
            
            has_valid_nodule = False

            for cluster in cluster_annotations:
                # 50% Consensus level
                # Fixed: Calling consensus from pylidc.utils
                # Pad is [(before, after), ...] tuples. 0 padding ensures we stick to the bbox.
                cmask, cbbox, _ = consensus(cluster, clevel=0.5, pad=[(0,0), (0,0), (0,0)])
                
                # --- BOUNDARY LOGIC ---
                b_start = [cbbox[0].start, cbbox[1].start, cbbox[2].start]
                b_stop  = [cbbox[0].stop,  cbbox[1].stop,  cbbox[2].stop]

                # Volume Slices (Clamp to volume limits)
                vol_slice = tuple(
                    slice(max(0, s), min(d, e)) 
                    for s, e, d in zip(b_start, b_stop, v_shape)
                )

                # Mask Slices (Handle cases where bbox starts before 0)
                mask_slice = tuple(
                    slice(max(0, -s), max(0, -s) + (min(d, e) - max(0, s)))
                    for s, e, d in zip(b_start, b_stop, v_shape)
                )
                
                try:
                    # Merge Logic
                    if mask[vol_slice].shape == cmask[mask_slice].shape:
                        combined = np.logical_or(mask[vol_slice], cmask[mask_slice])
                        mask[vol_slice] = combined.astype(np.uint8)
                        has_valid_nodule = True
                except Exception:
                    continue

            if not has_valid_nodule:
                continue

            # 3. Construct Affine
            affine = get_affine_from_scan(scan)

            # 4. Save NIfTI
            series_uid = scan.series_instance_uid.replace('.', '')[-10:]
            file_id = f"{scan.patient_id}_{series_uid}"
            
            img_path = os.path.join(cfg.DATA_ROOT, "images", f"{file_id}_image.nii.gz")
            lbl_path = os.path.join(cfg.DATA_ROOT, "labels", f"{file_id}_label.nii.gz")

            nib.save(nib.Nifti1Image(vol.astype(np.float32), affine), img_path)
            nib.save(nib.Nifti1Image(mask.astype(np.uint8), affine), lbl_path)

            valid_entries.append({
                "image": img_path,
                "label": lbl_path,
                "patient_id": scan.patient_id
            })

        except Exception as e:
            print(f"!!! ERROR on scan {scan.patient_id}: {e}")
            continue

    # 5. Patient-Level Splitting
    unique_patients = sorted(list(set(d['patient_id'] for d in valid_entries)))
    rng = np.random.RandomState(42)
    rng.shuffle(unique_patients)
    
    split_idx = int(len(unique_patients) * 0.8)
    train_patients = set(unique_patients[:split_idx])
    val_patients = set(unique_patients[split_idx:])
    
    final_train = [d for d in valid_entries if d['patient_id'] in train_patients]
    final_val = [d for d in valid_entries if d['patient_id'] in val_patients]
    
    # Remove metadata before saving JSON
    for d in final_train: del d['patient_id']
    for d in final_val: del d['patient_id']

    json_output = {
        "training": final_train,
        "validation": final_val
    }

    with open(cfg.JSON_PATH, "w") as f:
        json.dump(json_output, f, indent=4)

    print(f"Done. Train: {len(final_train)}, Val: {len(final_val)}")

if __name__ == "__main__":
    preprocess_lidc_sota()