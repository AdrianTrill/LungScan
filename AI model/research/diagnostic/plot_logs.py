#!/usr/bin/env python3

"""
Parses a VISTA-3D/MONAI training .stdout log file and plots the
Training Loss, Validation Mean Dice, and (if present) Validation Mean IoU.

Usage:
    python plot_logs.py /path/to/your/12345.stdout

This will save a file named 'training_plots.png' in the current directory.

You can specify a different output name:
    python plot_logs.py logs/12345.stdout -o my_custom_plot.png
"""

import re
import argparse
import matplotlib.pyplot as plt
import numpy as np

def parse_logfile(filepath):
    """
    Parses the log file to extract training and validation metrics.
    """
    # Regex patterns to find the data
    # \s+ matches one or more whitespace chars
    # (\S+) captures one or more non-whitespace chars (the value)
    train_loss_pattern = re.compile(r"Epoch (\d+)\s+Avg\. Training Loss:\s+(\S+)")
    
    # This pattern splits the file into validation blocks
    val_epoch_pattern = re.compile(r"Validation Metrics - Epoch (\d+):")
    
    # These patterns are run *within* each validation block
    dice_pattern = re.compile(r"Mean Dice:\s+(\S+)")
    iou_pattern = re.compile(r"Mean IoU:\s+(\S+)")
    
    train_epochs = []
    train_losses = []
    val_epochs = []
    val_dices = []
    val_ious = []
    has_iou = False

    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Log file not found at {filepath}")
        return None
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    # --- 1. Parse Training Loss ---
    # findall returns a list of tuples, e.g., [('1', '0.5571'), ('2', '0.5430'), ...]
    train_matches = train_loss_pattern.findall(content)
    if not train_matches:
        print("Warning: No 'Avg. Training Loss' lines found.")
    else:
        for epoch_str, loss_str in train_matches:
            try:
                train_epochs.append(int(epoch_str))
                train_losses.append(float(loss_str))
            except ValueError:
                print(f"Warning: Could not parse train loss line: Epoch {epoch_str}, Loss {loss_str}")

    # --- 2. Parse Validation Metrics ---
    # Split the file by the "Validation Metrics" line
    # This gives [header_junk, '1', epoch_1_content, '2', epoch_2_content, ...]
    val_blocks = val_epoch_pattern.split(content)[1:]
    
    if not val_blocks:
        print("Warning: No 'Validation Metrics' blocks found.")
    else:
        # Iterate over the blocks in pairs (epoch_num_str, block_content)
        for i in range(0, len(val_blocks), 2):
            try:
                epoch = int(val_blocks[i])
                block_content = val_blocks[i+1]
                
                dice_match = dice_pattern.search(block_content)
                iou_match = iou_pattern.search(block_content)
                
                if dice_match:
                    val_epochs.append(epoch)
                    val_dices.append(float(dice_match.group(1)))
                    
                    # Check for IoU *within the same block*
                    if iou_match:
                        has_iou = True # Set the flag if we find it even once
                        val_ious.append(float(iou_match.group(1)))
                    else:
                        # Use None as a placeholder to keep lists aligned
                        val_ious.append(None)
                
            except Exception as e:
                print(f"Warning: Failed to parse validation block for epoch {val_blocks[i]}: {e}")

    if not val_epochs:
        print("Warning: No 'Mean Dice' values were successfully parsed.")

    return train_epochs, train_losses, val_epochs, val_dices, val_ious, has_iou

def plot_metrics(train_epochs, train_losses, val_epochs, val_dices, val_ious, has_iou, output_file):
    """
    Generates and saves the plots.
    """
    # Determine how many subplots we need
    num_plots = 3 if has_iou else 2
    
    fig_height = 12 if has_iou else 9
    fig, axes = plt.subplots(num_plots, 1, figsize=(12, fig_height), sharex=True)
    
    # Ensure 'axes' is always a list for consistent indexing
    if num_plots == 2:
        axes = [axes[0], axes[1]]

    # --- Plot 1: Training Loss ---
    axes[0].plot(train_epochs, train_losses, label='Training Loss', color='blue', alpha=0.7)
    
    # Add a simple moving average to smooth the loss
    if len(train_losses) > 10:
        window_size = 10
        train_losses_smooth = np.convolve(train_losses, np.ones(window_size)/window_size, mode='valid')
        # Adjust epoch axis for the smoothed line
        axes[0].plot(train_epochs[window_size-1:], train_losses_smooth, label='Training Loss (Smoothed)', color='blue', linewidth=2)
        
    axes[0].set_title('Training Loss over Epochs')
    axes[0].set_ylabel('DiceCE Loss')
    axes[0].legend()
    axes[0].grid(True, linestyle='--', alpha=0.6)

    # --- Plot 2: Validation Dice ---
    axes[1].plot(val_epochs, val_dices, label='Mean Dice', color='green', marker='o', linestyle='--')
    axes[1].set_title('Validation Metrics over Epochs')
    axes[1].set_ylabel('Mean Dice')
    axes[1].legend()
    axes[1].grid(True, linestyle='--', alpha=0.6)

    # --- Plot 3: Validation IoU (Conditional) ---
    if has_iou:
        # Filter out the None values for plotting
        iou_epochs_filtered = [e for e, iou in zip(val_epochs, val_ious) if iou is not None]
        ious_filtered = [iou for iou in val_ious if iou is not None]
        
        if ious_filtered:
            axes[2].plot(iou_epochs_filtered, ious_filtered, label='Mean IoU', color='red', marker='x', linestyle=':')
            axes[2].set_ylabel('Mean IoU (Jaccard)')
            axes[2].legend()
        else:
            axes[2].text(0.5, 0.5, 'Mean IoU data was intermittent.', horizontalalignment='center', verticalalignment='center', transform=axes[2].transAxes)
        
        axes[2].set_xlabel('Epoch')
        axes[2].grid(True, linestyle='--', alpha=0.6)
    else:
        # If no IoU, just add the x-label to the Dice plot
        axes[1].set_xlabel('Epoch')

    # Finalize and save
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Successfully parsed log and saved plots to: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Parse a MONAI .stdout log file and plot training metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'logfile',
        type=str,
        help="Path to the .stdout log file to parse."
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='training_plots.png',
        help="Path to save the output plot (default: training_plots.png)"
    )
    args = parser.parse_args()
    
    parsed_data = parse_logfile(args.logfile)
    
    if parsed_data:
        train_epochs, train_losses, val_epochs, val_dices, val_ious, has_iou = parsed_data
        if not train_epochs and not val_epochs:
            print("No data was parsed. Exiting.")
            return
            
        plot_metrics(train_epochs, train_losses, val_epochs, val_dices, val_ious, has_iou, args.output)

if __name__ == "__main__":
    main()