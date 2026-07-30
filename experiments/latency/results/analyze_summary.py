#!/usr/bin/env python3
"""
Script to analyze the merge summary and calculate average latencies.
"""

import pandas as pd

def analyze_summary():
    # Read the summary data
    df = pd.read_csv('merged-data/merge_summary.csv')
    
    # Calculate latencies
    df['event_latency'] = df['avg_event_time'] - df['avg_creation_start']
    df['event_handle_latency'] = df['avg_handle_time'] - df['avg_creation_start']
    
    print("=" * 80)
    print("LATENCY ANALYSIS BY BURST SIZE")
    print("=" * 80)
    
    # Group by burst size and calculate statistics
    burst_stats = df.groupby('burst').agg({
        'event_latency': ['mean', 'std', 'min', 'max'],
        'event_handle_latency': ['mean', 'std', 'min', 'max'],
        'num_pods': 'mean'
    }).round(4)
    
    # Flatten column names
    burst_stats.columns = ['_'.join(col).strip() for col in burst_stats.columns]
    
    # Sort bursts by size (extract numeric part for proper sorting)
    burst_order = sorted(burst_stats.index, key=lambda x: int(x.split('-')[1]))
    
    print("\nEvent Latency (Creation Start → Event Time):")
    print("-" * 60)
    for burst in burst_order:
        stats = burst_stats.loc[burst]
        print(f"{burst:12} | Mean: {stats['event_latency_mean']:8.4f}s | "
              f"Std: {stats['event_latency_std']:8.4f}s | "
              f"Range: {stats['event_latency_min']:8.4f}s - {stats['event_latency_max']:8.4f}s")
    
    print("\nEvent Handle Latency (Creation Start → Handle Time):")
    print("-" * 60)
    for burst in burst_order:
        stats = burst_stats.loc[burst]
        print(f"{burst:12} | Mean: {stats['event_handle_latency_mean']:8.4f}s | "
              f"Std: {stats['event_handle_latency_std']:8.4f}s | "
              f"Range: {stats['event_handle_latency_min']:8.4f}s - {stats['event_handle_latency_max']:8.4f}s")
    
    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)
    
    overall_stats = df.agg({
        'event_latency': ['mean', 'std', 'min', 'max'],
        'event_handle_latency': ['mean', 'std', 'min', 'max']
    }).round(4)
    
    print(f"\nOverall Event Latency:")
    print(f"  Mean: {overall_stats.loc['mean', 'event_latency']:.4f}s")
    print(f"  Std:  {overall_stats.loc['std', 'event_latency']:.4f}s")
    print(f"  Min:  {overall_stats.loc['min', 'event_latency']:.4f}s")
    print(f"  Max:  {overall_stats.loc['max', 'event_latency']:.4f}s")
    
    print(f"\nOverall Event Handle Latency:")
    print(f"  Mean: {overall_stats.loc['mean', 'event_handle_latency']:.4f}s")
    print(f"  Std:  {overall_stats.loc['std', 'event_handle_latency']:.4f}s")
    print(f"  Min:  {overall_stats.loc['min', 'event_handle_latency']:.4f}s")
    print(f"  Max:  {overall_stats.loc['max', 'event_handle_latency']:.4f}s")
    
    print("\n" + "=" * 80)
    print("DETAILED BREAKDOWN BY BURST AND ITERATION")
    print("=" * 80)
    
    # Create detailed breakdown
    detailed = df[['burst', 'iteration', 'num_pods', 'event_latency', 'event_handle_latency']].copy()
    
    # Sort by burst size (numerically) then by iteration
    detailed['burst_num'] = detailed['burst'].str.extract('(\d+)').astype(int)
    detailed = detailed.sort_values(['burst_num', 'iteration']).drop('burst_num', axis=1)
    
    print(f"{'Burst':<12} {'Iter':<4} {'Pods':<5} {'Event Latency':<15} {'Handle Latency':<15}")
    print("-" * 65)
    
    for _, row in detailed.iterrows():
        print(f"{row['burst']:<12} {row['iteration']:<4} {row['num_pods']:<5} "
              f"{row['event_latency']:<15.4f} {row['event_handle_latency']:<15.4f}")
    
    # Save detailed results to CSV
    detailed.to_csv('merged-data/latency_analysis.csv', index=False)
    print(f"\nDetailed results saved to: merged-data/latency_analysis.csv")

if __name__ == "__main__":
    analyze_summary()
