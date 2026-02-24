import torch
import time
import numpy as np
from monai.inferers import sliding_window_inference
from monai.networks.nets import vista3d132

# --- CONFIGURATION ---
DEVICE = torch.device("cuda:0")
# Typical Large Lung CT dimensions (Channel, Z, Y, X)
# At 0.7mm spacing, a lung scan can be huge (e.g. 400-500 slices)
FAKE_VOLUME_SHAPE = (1, 1, 400, 512, 512) 
ROI_SIZE = (96, 96, 96)
MODEL_PRECISION = "amp" # 'amp' or 'float32'

def benchmark():
    if not torch.cuda.is_available():
        print("Error: CUDA not found.")
        return

    print(f"--- 🚀 H200 Speed Benchmark ---")
    print(f"Fake Volume Shape: {FAKE_VOLUME_SHAPE}")
    print(f"Patch Size: {ROI_SIZE}")
    print(f"VRAM Available: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    print("-" * 60)

    # 1. Init Model (Random weights are fine for timing)
    model = vista3d132(encoder_embed_dim=48, in_channels=1).to(DEVICE)
    model.eval()

    # 2. Create Fake Input (On GPU)
    input_tensor = torch.randn(FAKE_VOLUME_SHAPE, device=DEVICE)
    
    # Dummy prompt (needed for VISTA architecture)
    # Class 23 (Lung Tumor)
    dummy_class_vector = torch.tensor([23], device=DEVICE)

    # 3. Test Configurations
    # We test Batch Size AND Overlap
    configs = [
        # (Batch Size, Overlap)
        (192, 0),  # Baseline
        (192, 0.25),  # Your current plan
        (96, 0.25),  # Pushing it
        (256, 0.5),   # H200 Territory
        (384, 0.5),
        (128, 0.5), # Power user
        (96, 0.5), # Reduced overlap (Algorithmic speedup)
    ]

    for batch_size, overlap in configs:
        print(f"\nTesting: Batch={batch_size} | Overlap={overlap}...")
        
        torch.cuda.reset_peak_memory_stats()
        start_time = time.perf_counter()
        
        try:
            with torch.no_grad():
                with torch.cuda.amp.autocast():
                    # sw_device=DEVICE ensures stitching happens on GPU (Fast)
                    # device=DEVICE ensures patches stay on GPU
                    output = sliding_window_inference(
                        inputs=input_tensor, 
                        roi_size=ROI_SIZE, 
                        sw_batch_size=batch_size, 
                        predictor=model, 
                        overlap=overlap,
                        sw_device=DEVICE, # <--- CRITICAL FOR SPEED
                        device=DEVICE,
                        class_vector=dummy_class_vector
                    )
            
            # Synchronize to get accurate time
            torch.cuda.synchronize()
            end_time = time.perf_counter()
            duration = end_time - start_time
            max_mem = torch.cuda.max_memory_allocated() / 1e9
            
            print(f"✅ Success!")
            print(f"   Time:   {duration:.2f} seconds")
            print(f"   Memory: {max_mem:.2f} GB used")
            
        except RuntimeError as e:
            if "out of memory" in str(e):
                print(f"❌ OOM (Out of Memory) crash!")
            else:
                print(f"❌ Error: {e}")
            torch.cuda.empty_cache()

if __name__ == "__main__":
    benchmark()