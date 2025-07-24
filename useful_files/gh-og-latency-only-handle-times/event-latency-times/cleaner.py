#!/usr/bin/env python3

# Script generated with Github Copilot.

"""
Script to extract only the first entry of each pod from all iteration-x.csv files
in every burst folder within the event-latency-times directory.
"""

import os
import csv
import glob
from pathlib import Path

def extract_first_pod_entries(csv_file_path, output_file_path):
    """
    Extract the first entry of each pod from a CSV file and write to output file.
    
    Args:
        csv_file_path (str): Path to the input CSV file
        output_file_path (str): Path to the output CSV file
    """
    seen_pods = set()
    first_entries = []
    
    try:
        with open(csv_file_path, 'r', newline='') as csvfile:
            # Read each line (assuming format: pod_name,timestamp)
            for line in csvfile:
                line = line.strip()
                if not line:
                    continue
                    
                parts = line.split(',')
                if len(parts) >= 2:
                    pod_name = parts[0]
                    if pod_name not in seen_pods:
                        seen_pods.add(pod_name)
                        first_entries.append(line)
        
        # Write first entries to output file
        with open(output_file_path, 'w', newline='') as outfile:
            for entry in first_entries:
                outfile.write(entry + '\n')
                
        print(f"Processed {csv_file_path} -> {output_file_path} ({len(first_entries)} unique pods)")
        
    except Exception as e:
        print(f"Error processing {csv_file_path}: {e}")

def process_all_burst_folders():
    """
    Process all burst folders and their iteration CSV files.
    """
    # Get the current directory (should be event-latency-times)
    current_dir = Path.cwd()
    print(f"Working in directory: {current_dir}")
    
    # Find all burst folders
    burst_folders = glob.glob("burst-*")
    burst_folders.sort()
    
    if not burst_folders:
        print("No burst folders found in current directory")
        return
    
    print(f"Found burst folders: {burst_folders}")
    
    for burst_folder in burst_folders:
        if not os.path.isdir(burst_folder):
            continue
            
        print(f"\nProcessing {burst_folder}...")
        
        # Create cleaned subfolder
        cleaned_dir = os.path.join(burst_folder, "cleaned")
        os.makedirs(cleaned_dir, exist_ok=True)
        
        # Find all iteration CSV files in this burst folder
        iteration_files = glob.glob(os.path.join(burst_folder, "iteration-*.csv"))
        iteration_files.sort()
        
        if not iteration_files:
            print(f"  No iteration CSV files found in {burst_folder}")
            continue
            
        for csv_file in iteration_files:
            # Generate output filename
            filename = os.path.basename(csv_file)
            output_file = os.path.join(cleaned_dir, f"cleaned_{filename}")
            
            # Process the file
            extract_first_pod_entries(csv_file, output_file)

def main():
    """
    Main function to run the cleaner script.
    """
    print("=== Pod Entry Cleaner Script ===")
    print("This script extracts the first entry of each pod from all iteration CSV files")
    print("in every burst folder.\n")
    
    # Check if we're in the right directory
    if not os.path.exists("burst-20") or not os.path.exists("burst-50"):
        print("Warning: Expected burst folders not found. Are you in the event-latency-times directory?")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    process_all_burst_folders()
    print("\n=== Processing Complete ===")

if __name__ == "__main__":
    main()