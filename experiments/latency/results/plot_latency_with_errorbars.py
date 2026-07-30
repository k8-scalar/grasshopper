#!/usr/bin/env python3
"""
Script to create a nice plot of handle event latencies by burst size with error bars.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

def create_latency_plot():
    """Create a plot of handle event latencies by burst size with error bars."""
    
    # Read the summary data
    df = pd.read_csv('merged-data/merge_summary.csv')
    
    # Calculate the handle event latency (total latency from creation to handle)
    df['handle_event_latency'] = df['avg_handle_time'] - df['avg_creation_start']
    
    # Extract burst size as numeric value
    df['burst_size'] = df['burst'].str.extract(r'burst-(\d+)')[0].astype(int)
    
    # Calculate statistics by burst size
    stats = df.groupby('burst_size')['handle_event_latency'].agg(['mean', 'std', 'count']).reset_index()
    
    # Calculate standard error for error bars
    stats['std_error'] = stats['std'] / np.sqrt(stats['count'])
    
    # Set up the plot style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create the main plot with error bars
    bars = ax.errorbar(stats['burst_size'], stats['mean'], 
                      yerr=stats['std'], 
                      fmt='o-', 
                      capsize=8, 
                      capthick=2, 
                      linewidth=2.5,
                      markersize=10,
                      color='#2E86AB',
                      ecolor='#2E86AB',
                      markerfacecolor='#F18F01',
                      markeredgecolor='#2E86AB',
                      markeredgewidth=2)
    
    # Customize the plot
    ax.set_xlabel('Burst Size (Number of Pods)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Handle Event Latency (seconds)', fontsize=14, fontweight='bold')
    ax.set_title('Pod Handle Event Latency by Burst Size\n(Creation Start → Event Handled)', 
                fontsize=16, fontweight='bold', pad=20)
    
    # Set x-axis ticks to show all burst sizes
    ax.set_xticks(stats['burst_size'])
    ax.set_xticklabels(stats['burst_size'])
    
    # Add grid for better readability
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Customize tick labels
    ax.tick_params(axis='both', which='major', labelsize=12)
    
    # Add annotations with mean and std values (std under mean)
    for i, row in stats.iterrows():
        ax.annotate(f'{row["mean"]:.2f}s\n± {row["std"]:.2f}s', 
                   xy=(row['burst_size'], row['mean']), 
                   xytext=(10, 10), 
                   textcoords='offset points',
                   fontsize=10,
                   fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.3', 
                            facecolor='white', 
                            alpha=0.8,
                            edgecolor='gray'),
                   ha='left',
                   va='center')
    
    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='#2E86AB', linewidth=2.5, 
                  markersize=10, markerfacecolor='#F18F01', markeredgecolor='#2E86AB',
                  label='Mean ± Std Dev')
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=12)
    
    # Adjust layout and add some padding
    plt.tight_layout()
    
    # Add a subtle background color
    fig.patch.set_facecolor('#FAFAFA')
    ax.set_facecolor('#FFFFFF')
    
    # Save the plot
    output_path = 'merged-data/handle_event_latency_plot.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight', 
                facecolor='#FAFAFA', edgecolor='none')
    
    # Also save as PDF
    pdf_path = 'merged-data/handle_event_latency_plot.pdf'
    plt.savefig(pdf_path, bbox_inches='tight', 
                facecolor='#FAFAFA', edgecolor='none')
    
    print(f"Plot saved as: {output_path}")
    print(f"Plot saved as: {pdf_path}")
    
    # Display summary statistics
    print("\n" + "="*60)
    print("HANDLE EVENT LATENCY STATISTICS")
    print("="*60)
    print(f"{'Burst Size':<12} {'Mean (s)':<10} {'Std Dev (s)':<12} {'Min (s)':<10} {'Max (s)':<10}")
    print("-" * 60)
    
    for burst_size in sorted(stats['burst_size']):
        burst_data = df[df['burst_size'] == burst_size]['handle_event_latency']
        print(f"{burst_size:<12} {burst_data.mean():<10.3f} {burst_data.std():<12.3f} "
              f"{burst_data.min():<10.3f} {burst_data.max():<10.3f}")
    
    # Show the plot
    plt.show()
    
    return fig, ax

if __name__ == "__main__":
    create_latency_plot()
