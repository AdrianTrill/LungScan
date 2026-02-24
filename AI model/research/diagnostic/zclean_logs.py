import os

def clean_log_file(input_path):
    # Determine output path (same filename but with _cleaned appended)
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_cleaned{ext}"

    # Keywords to look for to decide if we keep a line
    keep_keywords = [
        "Avg Loss",
        "Val Nodule Dice",
        "New Best Model",
        "Training Started"
    ]

    try:
        with open(input_path, 'r') as infile, open(output_path, 'w') as outfile:
            print(f"Processing: {input_path}")
            
            for line in infile:
                # check if any of the keywords exist in the current line
                if any(keyword in line for keyword in keep_keywords):
                    outfile.write(line)
        
        print(f"Success! Cleaned log saved to: {output_path}")

    except FileNotFoundError:
        print(f"Error: The file {input_path} was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # The specific path requested
    file_path = "/home/dem7clj/repos/mirpr/logs/21191082.stdout"
    clean_log_file(file_path)