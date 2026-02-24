#!/bin/bash

# Define the base directory
BASE_DIR="/home/shadeform/work"

# Export the required nnUNet variables
export nnUNet_raw="${BASE_DIR}/nnUNet_raw"
export nnUNet_preprocessed="${BASE_DIR}/nnUNet_preprocessed"
export nnUNet_results="${BASE_DIR}/nnUNet_results"

# Export the Data Augmentation process limit
export nnUNet_n_proc_DA=8

echo "SUCCESS: nnUNet environment variables have been exported."