"""
Script to copy low affect videos from CSV to dedicated folder
Filters for videos with valenceValue_rounded <= 3
"""
import csv
import shutil
from pathlib import Path

# Configuration
csv_path = r"C:\Users\synchrony\Desktop\SyncExp\lowV_paths 4(in).csv"
source_folder = r"C:\Users\synchrony\Desktop\SyncExp\LIRIS-ACCEDE-data\data"
dest_folder = r"C:\Users\synchrony\Desktop\SyncExp\low_affect"
valence_threshold = 3  # Only copy videos with valenceValue_rounded <= 3

print("=" * 60)
print("Low Affect Videos Copy Script (Filtered)")
print("=" * 60)

# Read CSV and filter by valence
print(f"\nReading CSV: {csv_path}")
print(f"Filter: valenceValue_rounded <= {valence_threshold}")
video_names = []
total_in_csv = 0
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        total_in_csv += 1
        valence_value = float(row['valenceValue_rounded'])
        if valence_value <= valence_threshold:
            video_names.append(row['name'])

total_videos = len(video_names)
print(f"Total videos in CSV: {total_in_csv}")
print(f"Videos matching filter: {total_videos} ({total_videos/total_in_csv*100:.1f}%)")

# Ensure destination exists
dest_path = Path(dest_folder)
dest_path.mkdir(exist_ok=True)
print(f"Destination folder: {dest_folder}")

# Copy videos
copied = 0
missing = []
errors = []

print("\nCopying videos...")
for idx, video_name in enumerate(video_names):
    source_file = Path(source_folder) / f"{video_name}.mp4"
    dest_file = dest_path / f"{video_name}.mp4"

    try:
        if source_file.exists():
            shutil.copy2(source_file, dest_file)
            copied += 1
            if copied % 50 == 0:  # Progress update every 50 videos
                print(f"  Progress: {copied}/{total_videos} videos copied ({copied/total_videos*100:.1f}%)")
        else:
            missing.append(video_name)
    except Exception as e:
        errors.append(f"{video_name}: {str(e)}")

# Final report
print("\n" + "=" * 60)
print("COPY COMPLETE")
print("=" * 60)
print(f"Total videos in CSV: {total_videos}")
print(f"Successfully copied: {copied}")
print(f"Missing from source: {len(missing)}")
print(f"Errors: {len(errors)}")

if missing:
    print(f"\nMissing videos ({len(missing)}):")
    for name in missing[:10]:  # Show first 10
        print(f"  - {name}")
    if len(missing) > 10:
        print(f"  ... and {len(missing) - 10} more")

if errors:
    print(f"\nErrors ({len(errors)}):")
    for err in errors[:10]:  # Show first 10
        print(f"  - {err}")
    if len(errors) > 10:
        print(f"  ... and {len(errors) - 10} more")

print("\n" + "=" * 60)
print(f"Destination: {dest_folder}")
print("=" * 60)
