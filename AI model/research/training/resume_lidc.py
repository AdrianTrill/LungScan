import os
import time
from tcia_utils import nbia

def resume_download():
    # 1. Fetch the full master list of series for LIDC-IDRI
    print("Fetching master series list from TCIA (this may take a moment)...")
    try:
        all_series = nbia.getSeries(collection="LIDC-IDRI")
    except Exception as e:
        print(f"Failed to fetch metadata: {e}")
        return

    print(f"Found {len(all_series)} total series in LIDC-IDRI.")

    # 2. Check local directory for existing folders
    # TCIA utils typically names folders after the SeriesInstanceUID
    existing_folders = set(os.listdir('.'))
    
    # 3. Filter the list: Keep only series where the folder does NOT exist
    series_to_download = []
    for s in all_series:
        uid = s['SeriesInstanceUID']
        if uid not in existing_folders:
            series_to_download.append(s)

    print(f"Skipping {len(all_series) - len(series_to_download)} existing series.")
    print(f"Starting download for {len(series_to_download)} missing series...")

    # 4. Download loop with Error Handling
    # We download one by one so we can catch errors on specific files
    for index, series in enumerate(series_to_download):
        uid = series['SeriesInstanceUID']
        print(f"[{index+1}/{len(series_to_download)}] Downloading: {uid}")
        
        try:
            # Pass just this single series to the downloader
            nbia.downloadSeries([series])
        except Exception as e:
            print(f"!!! ERROR downloading {uid}: {e}")
            # Identify specific errors here if needed, otherwise continue
            continue
        
        # Optional: Sleep briefly to be nice to the API
        # time.sleep(0.5)

if __name__ == "__main__":
    resume_download()