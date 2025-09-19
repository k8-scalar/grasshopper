#!/usr/bin/env python3
"""
Corrected script to merge creation times data with event latency times data
for all burst folders and iterations.
"""

import os
import pandas as pd
import re
from pathlib import Path

def extract_iteration_number(filename):
    """Extract iteration number from filename."""
    # For both creation times and event latency: "iteration-1.csv" -> 1
    iteration_match = re.search(r'^iteration-(\d+)\.csv$', filename)
    if iteration_match:
        return int(iteration_match.group(1))
    
    return None

def validate_merged_data(merged_df, iteration, burst_name):
    """Validate the merged data for timing consistency."""
    violations = []
    
    # Check if event_time > creation_start
    rule1_violations = merged_df[merged_df['event_time'] <= merged_df['creation_start']]
    if len(rule1_violations) > 0:
        violations.append(f"event_time <= creation_start: {len(rule1_violations)} rows")
    
    # Check if handle_time > event_time
    rule2_violations = merged_df[merged_df['handle_time'] <= merged_df['event_time']]
    if len(rule2_violations) > 0:
        violations.append(f"handle_time <= event_time: {len(rule2_violations)} rows")
    
    if violations:
        print(f"    ⚠️  TIMING VIOLATIONS in {burst_name} iteration {iteration}:")
        for violation in violations:
            print(f"       - {violation}")
        return False
    
    return True

def merge_data_for_burst(burst_name, creation_dir, event_dir, output_dir):
    """Merge creation times and event latency data for a specific burst."""
    print(f"Processing {burst_name}...")
    
    creation_path = os.path.join(creation_dir, burst_name)
    event_path = os.path.join(event_dir, burst_name)
    
    if not os.path.exists(creation_path) or not os.path.exists(event_path):
        print(f"  Skipping {burst_name} - missing directories")
        return 0
    
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
        return 0
    
    print(f"  Found {len(common_iterations)} matching iterations: {sorted(common_iterations)}")
    
    # Create output directory for this burst
    burst_output_dir = os.path.join(output_dir, burst_name)
    os.makedirs(burst_output_dir, exist_ok=True)
    
    successful_merges = 0
    
    # Process each common iteration
    for iteration in sorted(common_iterations):
        try:
            # Read creation times data - CORRECTED: handle malformed CSV properly
            # The header says ",pod_name,creation_time" but data is "test-pod-0,1753346239.8300393"
            # So we skip the malformed header and read without headers
            creation_df = pd.read_csv(creation_files[iteration], header=None, skiprows=1)
            creation_df.columns = ['pod_name', 'creation_start']
            
            # Read event latency data (no header)
            event_df = pd.read_csv(event_files[iteration], names=["pod_name", "event_time", "handle_time"])
            
            # Ensure pod_name columns are same type (string)
            creation_df['pod_name'] = creation_df['pod_name'].astype(str)
            event_df['pod_name'] = event_df['pod_name'].astype(str)
            
            # Remove any leading/trailing whitespace
            creation_df['pod_name'] = creation_df['pod_name'].str.strip()
            event_df['pod_name'] = event_df['pod_name'].str.strip()
            
            # Merge on pod_name
            merged_df = pd.merge(creation_df, event_df, on="pod_name", how="inner")
            
            if len(merged_df) == 0:
                print(f"    ⚠️  No matching pod names found for iteration {iteration}")
                continue
            
            # Validate timing relationships
            is_valid = validate_merged_data(merged_df, iteration, burst_name)
            
            # Save merged data
            output_filename = f"iteration-{iteration}-merged.csv"
            output_path = os.path.join(burst_output_dir, output_filename)
            merged_df.to_csv(output_path, index=False)
            
            status = "✓" if is_valid else "⚠️"
            print(f"    {status} Iteration {iteration}: {len(merged_df)} pods merged -> {output_filename}")
            successful_merges += 1
            
        except Exception as e:
            print(f"    ❌ Error processing iteration {iteration}: {e}")
    
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
                    try:
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
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")
    
    if summary_data:
        summary_df = pd.DataFrame(summary_data)
        summary_path = os.path.join(output_dir, 'merge_summary.csv')
        summary_df.to_csv(summary_path, index=False)
        print(f"Summary report created: {summary_path}")

if __name__ == "__main__":
    main()
