#!/usr/bin/env python3
import os
import pandas as pd
import glob
from typing import List, Tuple, Dict

def check_timing_relationships(csv_file: str) -> Dict:
    """
    Check timing relationships in a CSV file.
    Returns a dictionary with validation results.
    """
    try:
        df = pd.read_csv(csv_file)
        
        # Check if required columns exist
        required_cols = ['creation_start', 'event_time', 'handle_time']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return {
                'file': csv_file,
                'valid': False,
                'error': f"Missing columns: {missing_cols}",
                'total_rows': 0,
                'violations': {}
            }
        
        # Convert to numeric, handling any potential string timestamps
        df['creation_start'] = pd.to_numeric(df['creation_start'], errors='coerce')
        df['event_time'] = pd.to_numeric(df['event_time'], errors='coerce')
        df['handle_time'] = pd.to_numeric(df['handle_time'], errors='coerce')
        
        # Check for NaN values
        nan_rows = df[['creation_start', 'event_time', 'handle_time']].isna().any(axis=1).sum()
        
        # Check timing relationships
        # Rule 1: event_time > creation_start
        rule1_violations = df[df['event_time'] <= df['creation_start']]
        
        # Rule 2: handle_time > event_time
        rule2_violations = df[df['handle_time'] <= df['event_time']]
        
        # Rule 3: handle_time > creation_start (implied but good to check)
        rule3_violations = df[df['handle_time'] <= df['creation_start']]
        
        result = {
            'file': os.path.basename(csv_file),
            'full_path': csv_file,
            'total_rows': len(df),
            'nan_rows': nan_rows,
            'violations': {
                'event_time_before_creation': len(rule1_violations),
                'handle_time_before_event': len(rule2_violations),
                'handle_time_before_creation': len(rule3_violations)
            },
            'valid': len(rule1_violations) == 0 and len(rule2_violations) == 0 and nan_rows == 0,
            'rule1_violations': rule1_violations.to_dict('records') if len(rule1_violations) > 0 else [],
            'rule2_violations': rule2_violations.to_dict('records') if len(rule2_violations) > 0 else [],
            'rule3_violations': rule3_violations.to_dict('records') if len(rule3_violations) > 0 else []
        }
        
        return result
        
    except Exception as e:
        return {
            'file': csv_file,
            'valid': False,
            'error': str(e),
            'total_rows': 0,
            'violations': {}
        }

def main():
    # Find all merged CSV files
    base_dir = "/Users/quintenlauwaert/Desktop/results"
    pattern = os.path.join(base_dir, "merged-data", "**", "*merged*.csv")
    csv_files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(csv_files)} merged CSV files to analyze")
    print("=" * 80)
    
    all_results = []
    valid_files = 0
    total_violations = 0
    
    for csv_file in sorted(csv_files):
        result = check_timing_relationships(csv_file)
        all_results.append(result)
        
        if result['valid']:
            valid_files += 1
            print(f"✓ {result['file']}: VALID ({result['total_rows']} rows)")
        else:
            if 'error' in result:
                print(f"✗ {result['file']}: ERROR - {result['error']}")
            else:
                violations = result['violations']
                total_file_violations = sum(violations.values())
                total_violations += total_file_violations
                
                print(f"✗ {result['file']}: INVALID ({result['total_rows']} rows)")
                if violations['event_time_before_creation'] > 0:
                    print(f"    - {violations['event_time_before_creation']} rows where event_time <= creation_start")
                if violations['handle_time_before_event'] > 0:
                    print(f"    - {violations['handle_time_before_event']} rows where handle_time <= event_time")
                if violations['handle_time_before_creation'] > 0:
                    print(f"    - {violations['handle_time_before_creation']} rows where handle_time <= creation_start")
                if result['nan_rows'] > 0:
                    print(f"    - {result['nan_rows']} rows with NaN values")
    
    print("=" * 80)
    print(f"SUMMARY:")
    print(f"Total files analyzed: {len(csv_files)}")
    print(f"Valid files: {valid_files}")
    print(f"Invalid files: {len(csv_files) - valid_files}")
    print(f"Total timing violations: {total_violations}")
    
    # Show detailed violations for problematic files
    problematic_files = [r for r in all_results if not r['valid'] and 'error' not in r]
    if problematic_files:
        print("\nDETAILED VIOLATION EXAMPLES:")
        print("=" * 80)
        for result in problematic_files[:5]:  # Show first 5 problematic files
            print(f"\nFile: {result['file']}")
            
            if result['rule1_violations']:
                print("  Event time before creation time examples:")
                for i, violation in enumerate(result['rule1_violations'][:3]):  # Show first 3
                    print(f"    Row {i+1}: creation={violation['creation_start']:.6f}, event={violation['event_time']:.6f}")
            
            if result['rule2_violations']:
                print("  Handle time before event time examples:")
                for i, violation in enumerate(result['rule2_violations'][:3]):  # Show first 3
                    print(f"    Row {i+1}: event={violation['event_time']:.6f}, handle={violation['handle_time']:.6f}")

if __name__ == "__main__":
    main()
