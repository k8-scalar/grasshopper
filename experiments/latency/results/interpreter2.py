#!/usr/bin/env python3
"""
General script to merge creation times data with event latency times data
for all burst folders and iterations.
"""

import os
import pandas as pd
import re
from pathlib import Path

def extract_iteration_number(filename):
    """Extract iteration number from filename."""
    # For creation times: "1-pod_creation_times_burst_10.csv" -> 1
    creation_match = re.search(r'^(\d+)-pod_creation_times_burst_\d+\.csv$', filename)
    if creation_match:
        return int(creation_match.group(1))
    
    # For event latency: "iteration-1.csv" -> 1
    event_match = re.search(r'^iteration-(\d+)\.csv$', filename)
    if event_match:
        return int(event_match.group(1))
    
    # For cleaned event latency: "cleaned_iteration-1.csv" -> 1
    cleaned_match = re.search(r'^cleaned_iteration-(\d+)\.csv$', filename)
    if cleaned_match:
        return int(cleaned_match.group(1))
    
    return None

def merge_data_for_burst(burst_name, creation_dir, event_dir, output_dir):
    """Merge creation times and event latency data for a specific burst."""
    print(f"Processing {burst_name}...")
    
    creation_path = os.path.join(creation_dir, burst_name)
    event_path = os.path.join(event_dir, burst_name, "cleaned")
    
    if not os.path.exists(creation_path) or not os.path.exists(event_path):
        print(f"  Skipping {burst_name} - missing directories")
        return
    
    # Get files and organize by iteration
    creation_files = {}
    event_files = {}
    
    # Process creation time files
    for filename in os.listdir(creation_path):
        if filename.endswith('.csv'):
            iteration = extract_iteration_number(filename)
            if iteration is not None:
                creation_files[iteration] = os.path.join(creation_path, filename)
    
    # Process event latency files
    for filename in os.listdir(event_path):
        if filename.endswith('.csv'):
            iteration = extract_iteration_number(filename)
            if iteration is not None:
                event_files[iteration] = os.path.join(event_path, filename)
    
    # Find common iterations
    common_iterations = set(creation_files.keys()).intersection(set(event_files.keys()))
    
    if not common_iterations:
        print(f"  No matching iterations found for {burst_name}")
        return
    
    print(f"  Found {len(common_iterations)} matching iterations: {sorted(common_iterations)}")
    
    # Create output directory for this burst
    burst_output_dir = os.path.join(output_dir, burst_name)
    os.makedirs(burst_output_dir, exist_ok=True)
    
    successful_merges = 0
    
    # Process each common iteration
    for iteration in sorted(common_iterations):
        try:
            # Read creation times data - skip the malformed header and read as no header
            # The actual format is: index, pod_name, creation_time
            creation_df = pd.read_csv(creation_files[iteration], header=None, skiprows=1)
            creation_df.columns = ['pod_name', 'creation_start']
            
            # Read event latency data (no header)
            event_df = pd.read_csv(event_files[iteration], names=["pod_name", "event_time", "handle_time"])
            
            # Ensure pod_name columns are same type (string)
            creation_df['pod_name'] = creation_df['pod_name'].astype(str)
            event_df['pod_name'] = event_df['pod_name'].astype(str)
            
            # Merge on pod_name
            merged_df = pd.merge(creation_df, event_df, on="pod_name", how="inner")
            
            # Save merged data
            output_filename = f"iteration-{iteration}-merged.csv"
            output_path = os.path.join(burst_output_dir, output_filename)
            merged_df.to_csv(output_path, index=False)
            
            print(f"    Iteration {iteration}: {len(merged_df)} pods merged -> {output_filename}")
            successful_merges += 1
            
        except Exception as e:
            print(f"    Error processing iteration {iteration}: {e}")
    
    print(f"  Successfully merged {successful_merges} iterations for {burst_name}")
    return successful_merges

def main():
    """Main function to process all burst folders."""
    # Define base directories
    base_dir = "."
    creation_times_dir = os.path.join(base_dir, "creation-times")
    event_latency_dir = os.path.join(base_dir, "event-latency-times")
    output_dir = os.path.join(base_dir, "merged-data")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print("Starting data merge process...")
    print(f"Creation times directory: {creation_times_dir}")
    print(f"Event latency directory: {event_latency_dir}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    # Get all burst directories from creation-times
    if not os.path.exists(creation_times_dir):
        print(f"Error: Creation times directory not found: {creation_times_dir}")
        return
    
    burst_dirs = [d for d in os.listdir(creation_times_dir) 
                  if os.path.isdir(os.path.join(creation_times_dir, d)) and d.startswith('burst-')]
    
    if not burst_dirs:
        print("No burst directories found!")
        return
    
    print(f"Found burst directories: {sorted(burst_dirs)}")
    print("-" * 50)
    
    total_successful = 0
    
    # Process each burst directory
    for burst_name in sorted(burst_dirs):
        successful = merge_data_for_burst(burst_name, creation_times_dir, event_latency_dir, output_dir)
        if successful:
            total_successful += successful
        print()
    
    print("-" * 50)
    print(f"Merge process completed!")
    print(f"Total successful merges: {total_successful}")
    print(f"Results saved in: {output_dir}")
    
    # Create a summary report
    create_summary_report(output_dir)

def create_summary_report(output_dir):
    """Create a summary report of all merged data."""
    summary_data = []
    
    for burst_dir in os.listdir(output_dir):
        burst_path = os.path.join(output_dir, burst_dir)
        if os.path.isdir(burst_path):
            for filename in os.listdir(burst_path):
                if filename.endswith('-merged.csv'):
                    file_path = os.path.join(burst_path, filename)
                    df = pd.read_csv(file_path)
                    
                    iteration = filename.split('-')[1]
                    summary_data.append({
                        'burst': burst_dir,
                        'iteration': int(iteration),
                        'num_pods': len(df),
                        'avg_handle_time': df['handle_time'].mean(),
                        'avg_event_time': df['event_time'].mean(),
                        'avg_creation_start': df['creation_start'].mean()
                    })
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(output_dir, 'merge_summary.csv')
        summary_df.to_csv(summary_path, index=False)
        print(f"Summary report created: {summary_path}")

if __name__ == "__main__":
    main()
