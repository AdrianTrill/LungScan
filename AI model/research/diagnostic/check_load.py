# print("heelo")


# import torch
# import os
# # Ensure you have the class definition imported. 
# # If 'monai.networks.nets.vista3d' isn't available, check the bundle's 'scripts' folder.
# from monai.networks.nets import vista3d132 

# device = torch.device("cuda:0")
# root_dir = "/home/dem7clj/repos/mirpr/models" # Adjust path to where you downloaded the bundle

# # 1. Instantiate the Model
# # These params (48, 1) are critical. They match the specific "vista3d132" pre-trained configuration.
# model = vista3d132(encoder_embed_dim=48, in_channels=1).to(device)

# # 2. Load and Clean the Weights
# checkpoint_path = os.path.join(root_dir, "model.pt")
# checkpoint = torch.load(checkpoint_path, map_location=device)

# # Handle different saving formats (Bundles sometimes wrap weights in "state_dict")
# if "state_dict" in checkpoint:
#     state_dict = checkpoint["state_dict"]
# else:
#     state_dict = checkpoint

# # Fix "module." prefix issue (common in distributed training checkpoints)
# new_state_dict = {}
# for k, v in state_dict.items():
#     # remove "module." if present
#     name = k.replace("module.", "") 
#     new_state_dict[name] = v

# # 3. Load into model
# # strict=False is recommended for Fine-tuning (allows head replacement/modification)
# # strict=True is better for Inference (ensures exact match)
# model.load_state_dict(new_state_dict, strict=False)

# print("VISTA3D loaded manually!")


import torch
import config as cfg
from model import get_vista_model

def sanity_check():
    print("--- Running Model Sanity Check ---")
    device = torch.device("cpu") # Keep simple for shape check
    
    # 1. Load Model
    model = get_vista_model(load_weights=False).to(device)
    model.eval()
    
    # 2. Create Dummy Batch (Batch Size = 16)
    B, C, D, H, W = 16, 1, 96, 96, 96
    inputs = torch.randn(B, C, D, H, W).to(device)
    print(f"Input Shape: {inputs.shape}")
    
    # 3. Forward Pass
    with torch.no_grad():
        outputs = model(inputs)
    
    print(f"Output Shape: {outputs.shape}")
    
    # 4. Verdict
    if outputs.shape[0] == 16 and outputs.shape[1] == 2:
        print("\n[SUCCESS] Model preserves Batch Size (16) and outputs 2 channels.")
        print("You are ready to train.")
    else:
        print(f"\n[FAIL] Model output shape is incorrect: {outputs.shape}")

if __name__ == "__main__":
    sanity_check()