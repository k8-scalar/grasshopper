# File generated with ChatGPT.

import os
import pandas as pd

# Define the directories
dir1 = "./creation-times/burst-20"
dir2 = "./event-latency-times/burst-20"

# Get list of files in both directories
files1 = set(os.listdir(dir1))
files2 = set(os.listdir(dir2))

# Find common files
common_files = files1.intersection(files2)

# Dictionary to store merged DataFrames
merged_dataframes = {}

# Iterate over common files
for filename in common_files:
    path1 = os.path.join(dir1, filename)
    path2 = os.path.join(dir2, filename)
    
    # Read the CSVs
    df1 = pd.read_csv(path1, names=["pod_name", "creation_start"])
    df2 = pd.read_csv(path2, names=["pod_name", "event_time", "handle_time"])
    
    # Merge on pod_name
    merged_df = pd.merge(df1, df2, on="pod_name")

    merged_df.to_csv("./burst-20-merged.csv")
    
    # Store the merged DataFrame
    merged_dataframes[filename] = merged_df

# Example: print one merged DataFrame
for name, df in merged_dataframes.items():
    print(f"--- {name} ---")
    print(df.head())
    break  # remove this if you want to print them all
