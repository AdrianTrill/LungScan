
import os

# --- PATHS ---
PROJECT_ROOT = "/home/dem7clj/repos/mirpr"
# Path to LIDC-IDRI DICOM files (the folder containing patient folders)
RAW_DICOM_DIR = "/shares/CC_v_Val_FV_Gen3_all/VIDT_DL/data/cnn_training/projects/smart_data_selection/town_signs/mirprfull/LIDC-IDRI"

# Output for Preprocessed NIfTI files
DATA_ROOT ="/shares/CC_v_Val_FV_Gen3_all/VIDT_DL/data/cnn_training/projects/smart_data_selection/town_signs/preprocessed_output_sota/"
JSON_PATH = os.path.join(DATA_ROOT, "dataset.json")

# Model Paths
PRETRAINED_MODEL_PATH = os.path.join(PROJECT_ROOT, "models/model.pt")
LOG_DIR = os.path.join(PROJECT_ROOT, "runs/vista3d_lidc_finetune")

# --- VISTA SPECIFICATIONS (DO NOT CHANGE) ---
# These match the Foundation Model's pre-training settings
TARGET_SPACING = (0.7, 0.7, 0.7) 
INTENSITY_RANGE = (-1000, 1000) 

# --- CLASS MAPPING ---
# LIDC Nodule (1) -> VISTA Lung Tumor (23)
LABEL_MAPPINGS = {"default": [[1, 23]]}
LABEL_SET = [0, 23] 

TARGET_VISTA_CLASS = 23

# --- HYPERPARAMETERS ---
ROI_SIZE = (224, 224, 224)
BATCH_SIZE = 32
NUM_WORKERS = 16
MAX_EPOCHS = 150
VAL_INTERVAL = 2
LR = 5e-5

# --- SAMPLING CONFIG ---
# --- SAMPLING CONFIG ---
MAX_POINT = 5
MAX_PROMPT = 32
MAX_BACKPROMPT = 4
# CHANGE THIS: Force model to use Auto-Seg mode 70% of the time (was 0.2 / 20%)
DROP_POINT_PROB = 0.7 
DROP_LABEL_PROB = 0.1