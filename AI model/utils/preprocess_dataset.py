import os
import numpy as np
import pylidc as pl
from scipy.ndimage import zoom
from tqdm import tqdm
import warnings

# --- Configuration ---
TARGET_SPACING = [1.0, 1.0, 1.0]  # Target spacing in mm (z, y, x)
CUBE_SIZE = [128, 128, 128]      # Target patch size (z, y, x)
STRIDE = [64, 64, 64]            # Stride for overlapping patches
LUNG_WINDOW = [-1000, 400]        # HU window for lung tissue

OUT_DIR = "/sc-rom-s3/Roberto-dataset-processed"
IMG_DIR = os.path.join(OUT_DIR, "images")
MASK_DIR = os.path.join(OUT_DIR, "masks")
# --- End Configuration ---


def resample_volume(volume, current_spacing, target_spacing, order=3):
    """
    Resample a volume to a target spacing.
    :param volume: 3D numpy array (z, y, x)
    :param current_spacing: List or tuple of current spacing (z, y, x)
    :param target_spacing: List or tuple of target spacing (z, y, x)
    :param order: Interpolation order (3=cubic, 0=nearest)
    :return: Resampled 3D numpy array
    """
    if current_spacing == target_spacing:
        return volume
        
    zoom_factor = [
        current / target
        for current, target in zip(current_spacing, target_spacing)
    ]
    
    resampled_volume = zoom(volume, zoom_factor, order=order, mode='nearest')
    return resampled_volume


def normalize(volume, window):
    """
    Apply HU windowing and normalize to [0, 1].
    :param volume: 3D numpy array
    :param window: List or tuple of [min_hu, max_hu]
    :return: Normalized 3D numpy array
    """
    vol_clipped = np.clip(volume, window[0], window[1])
    vol_normalized = (vol_clipped - window[0]) / (window[1] - window[0])
    return vol_normalized


def create_consensus_mask(scan, vol_shape):
    """
    Create a consensus mask (union of all annotations) for a scan.
    :param scan: pylidc.Scan object
    :param vol_shape: Shape of the CT volume (z, y, x)
    :return: 3D numpy array (binary mask)
    """
    mask = np.zeros(vol_shape, dtype=np.float32)
    
    try:
        annotation_clusters = scan.cluster_annotations()
    except Exception as e:
        print(f"  [Warning] Skipping mask generation for {scan.patient_id}: {e}")
        return mask # Return empty mask

    if not annotation_clusters:
         # This is normal for many scans, no print needed
         return mask

    for ann_cluster in annotation_clusters:
        try:
            for ann in ann_cluster:
                try:
                    cropped_mask = ann.boolean_mask()
                    slices = ann.bbox()
                    mask_slice_view = mask[slices]
                    
                    if mask_slice_view.shape == cropped_mask.shape:
                        np.logical_or(mask_slice_view, cropped_mask, out=mask_slice_view)
                    else:
                        slice_shape = mask_slice_view.shape
                        cropped_mask_view = cropped_mask[
                            :slice_shape[0], 
                            :slice_shape[1], 
                            :slice_shape[2]
                        ]
                        np.logical_or(mask_slice_view, cropped_mask_view, out=mask_slice_view)
                        
                except Exception as e_inner:
                    print(f"    [Warning] Skipping one annotation for {scan.patient_id}: {e_inner}")
                    continue
        except Exception as e:
            print(f"  [Warning] Error processing annotation cluster for {scan.patient_id}: {e}")
            continue
            
    return mask.astype(np.float32)


def preprocess():
    """
    Main preprocessing function.
    Iterates through LIDC scans, preprocesses them, and saves patches.
    """
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(MASK_DIR, exist_ok=True)
    
    print("Querying LIDC-IDRI database...")
    scans = pl.query(pl.Scan).all()
    print(f"Found {len(scans)} scans.")
    
    global_patch_count = 0
    
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    for i, scan in enumerate(tqdm(scans, desc="Processing Scans")):
        patient_id = scan.patient_id
        print(f"\nProcessing Scan {i+1}/{len(scans)}: {patient_id}")
        
        try:
            # 1. Load CT Volume
            ct_volume = scan.to_volume(verbose=False)
            
            # 2. Get Current Spacing
            current_spacing = [scan.slice_spacing, scan.pixel_spacing, scan.pixel_spacing]
            
            # 3. Create Consensus Mask
            mask_volume = create_consensus_mask(scan, ct_volume.shape)
            
            # 4. Resample both CT and Mask
            ct_resampled = resample_volume(ct_volume, current_spacing, TARGET_SPACING, order=3)
            mask_resampled = resample_volume(mask_volume, current_spacing, TARGET_SPACING, order=0)
            
            # 5. Normalize CT
            ct_normalized = normalize(ct_resampled, LUNG_WINDOW)
            
            # --- (FIX 1: PADDING) ---
            # Pad volumes to be at least CUBE_SIZE before patch extraction
            shape = ct_normalized.shape
            
            pad_z = max(0, CUBE_SIZE[0] - shape[0])
            pad_y = max(0, CUBE_SIZE[1] - shape[1])
            pad_x = max(0, CUBE_SIZE[2] - shape[2])
            
            ct_padding = ((0, pad_z), (0, pad_y), (0, pad_x))
            mask_padding = ((0, pad_z), (0, pad_y), (0, pad_x))
            
            ct_normalized = np.pad(ct_normalized, ct_padding, mode='constant', constant_values=0)
            mask_resampled = np.pad(mask_resampled, mask_padding, mode='constant', constant_values=0)
            # --- End of Padding Fix ---

            # 6. Extract Patches using Sliding Window
            shape = ct_normalized.shape # Get *new* padded shape
            scan_patch_count = 0
            
            for z in range(0, shape[0] - CUBE_SIZE[0] + 1, STRIDE[0]):
                for y in range(0, shape[1] - CUBE_SIZE[1] + 1, STRIDE[1]):
                    for x in range(0, shape[2] - CUBE_SIZE[2] + 1, STRIDE[2]):
                        
                        img_patch = ct_normalized[
                            z : z + CUBE_SIZE[0],
                            y : y + CUBE_SIZE[1],
                            x : x + CUBE_SIZE[2]
                        ]
                        
                        mask_patch = mask_resampled[
                            z : z + CUBE_SIZE[0],
                            y : y + CUBE_SIZE[1],
                            x : x + CUBE_SIZE[2]
                        ]
                        
                        # --- (FIX 2: FILTERING) ---
                        # Filter only patches of pure air (<-986 HU)
                        if np.mean(img_patch) < 0.01:
                            continue
                        # --- End of Filtering Fix ---
                        
                        # Optional: Skip patches without any nodule
                        # (We keep these to help the model learn "background")
                        # if np.sum(mask_patch) == 0:
                        #    continue

                        # Add Channel Dimension for the model: (C, D, H, W)
                        img_patch_1ch = np.expand_dims(img_patch, axis=0) 
                        mask_patch_1ch = np.expand_dims(mask_patch, axis=0)
                        
                        # Save the patches
                        patch_id = f"{patient_id}_{global_patch_count:05d}"
                        img_filename = os.path.join(IMG_DIR, f"{patch_id}.npy")
                        mask_filename = os.path.join(MASK_DIR, f"{patch_id}.npy")
                        
                        np.save(img_filename, img_patch_1ch.astype(np.float32))
                        np.save(mask_filename, mask_patch_1ch.astype(np.float32))
                        
                        global_patch_count += 1
                        scan_patch_count += 1
            
            print(f"  Saved {scan_patch_count} patches for scan {patient_id}.")

        except Exception as e:
            print(f"[ERROR] Failed to process scan {patient_id}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n--- Preprocessing Complete ---")
    print(f"Total patches saved: {global_patch_count}")
    print(f"Image patches saved to: {IMG_DIR}")
    print(f"Mask patches saved to: {MASK_DIR}")


if __name__ == "__main__":
    try:
        pl.query(pl.Scan).first()
        print("pylidc configuration found.")
    except Exception as e:
        print("pylidc not configured. Please run `pylidc-configure` in your terminal.")
        print("This will guide you through setting up the LIDC_IDRI dataset.")
        
    preprocess()