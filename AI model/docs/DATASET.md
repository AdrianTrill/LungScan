Here's a summary of the dataset and my preprocessing script.

### The LIDC-IDRI Dataset

For this project, I used the LIDC-IDRI (Lung Image Database Consortium and Image Database Resource Initiative) dataset. This is a large, publicly-available, and ethically-compliant (anonymized) collection of thoracic CT scans.

Its main challenge is that each nodule is annotated by four different radiologists, meaning there is no single "ground truth." My goal was to train a model to segment any area that at least one of the experts identified as a nodule.

### My `preprocess_lidc.py` Script

This script's job was to convert the raw, messy LIDC-IDRI scans into a clean, uniform dataset of 3D patches for the model. Here's the pipeline I built:

1.  **Load Data:** It queries the `pylidc` database to get all available patient scans.

2.  **Create Consensus Mask:** For each scan, it iterates through all available radiologist annotations and creates a single 3D "consensus mask" by taking the *union* of all of them. This means a voxel is "positive" if *any* of the four doctors marked it.

3.  **Resample:** It resamples both the CT volume (using cubic interpolation) and the new mask (using nearest-neighbor) to a uniform `1x1x1mm` spacing. This step is critical to standardize the data, as original CTs have different slice thicknesses.

4.  **Normalize:** The CT volume is windowed (from -1000 to 400 HU) and normalized to a `[0, 1]` range.

5.  **Pad, Patch, and Filter:**
    * First, it **pads** any volumes smaller than 128x128x128 to ensure no scans are skipped (this was an early bug).
    * Then, it uses a 3D sliding window to extract overlapping **patches** (128^3 cube size, 64-voxel stride).
    * Finally, it **filters** out any patches that are just "empty air" (mean value < 0.01) to create a smaller, more relevant dataset.

The final output is a set of `.npy` files (`images` and `masks`) that are all the same shape and format, ready to be loaded by `dataset.py`.