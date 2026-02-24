# utils.py
"""
Utility functions for the SOTA VISTA-3D pipeline,
primarily for Distributed Data Parallel (DDP) setup.
"""

import os
import torch
import torch.distributed as dist
import config as cfg

def setup_ddp(rank: int, world_size: int):
    """
    Initializes the distributed process group.
    
    Args:
        rank (int): The rank of the current process (usually the GPU ID).
        world_size (int): The total number of processes (total GPUs).
    """
    os.environ['MASTER_ADDR'] = cfg.DDP_MASTER_ADDR
    os.environ['MASTER_PORT'] = cfg.DDP_MASTER_PORT
    
    # Initialize the process group
    # 'nccl' is the standard, optimized backend for NVIDIA GPUs
    dist.init_process_group(
        backend='nccl',
        init_method='env://',
        world_size=world_size,
        rank=rank
    )
    
    # Pin the current process to a specific GPU
    torch.cuda.set_device(rank)
    print(f"[Rank {rank}] DDP setup complete. Using GPU {torch.cuda.current_device()}.")

def cleanup_ddp():
    """
    Cleans up the distributed process group.
    """
    dist.destroy_process_group()
    print("DDP cleanup complete.")