import psutil
import time
import pandas as pd
from datetime import datetime
import os
import signal
import sys

# Use absolute path to results folder
RESULTS_FOLDER = "/home/ubuntu/master-thesis-quinten-lauwaert/experiments/system-usage/results"

def monitor_system(interval, num_pods_burst, iteration):
    """
    Monitors system-wide CPU, memory, disk, and network usage.
    """
    print("Monitoring system-wide CPU, memory, disk, and network usage.")
    print("Press Ctrl+C to stop monitoring.")
    print(f"{'Time':<20}{'CPU (%)':<10}{'Mem Used (MB)':<15}{'Mem Total (MB)':<15}{'Mem (%)':<10}{'Disk Used (GB)':<15}{'Net Sent (KB)':<15}{'Net Recv (KB)':<15}")

    # Initialize CPU usage measurement
    psutil.cpu_percent(interval=0)
    net_io_start = psutil.net_io_counters()

    # Create the columns for the metrics.
    time_list = []
    cpu_usage_list = []
    memory_used_list = []
    memory_total_list = []
    memory_percent_list = []
    disk_used_list = []
    net_sent_list = []
    net_recv_list = []

    # Ensure results directory exists
    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    
    # Create results file path.
    date_of_measurement = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    results_file_path = os.path.join(RESULTS_FOLDER, f"system_usage_burst-{num_pods_burst}_iter-{iteration}.csv")

    # Flag to indicate graceful shutdown
    shutdown_requested = False

    def save_and_exit(reason="Unknown"):
        """Save data and exit gracefully"""
        nonlocal shutdown_requested
        shutdown_requested = True
        print(f"\nMonitoring stopped: {reason}")
        if time_list:  # Only save if we have data
            system_usage_df = pd.DataFrame({
                "Time": time_list,
                "CPU Usage (%)": cpu_usage_list,
                "Memory Used (MB)": memory_used_list,
                "Memory Total (MB)": memory_total_list,
                "Memory (%)": memory_percent_list,
                "Disk Used (GB)": disk_used_list,
                "Network Sent (KB)": net_sent_list,
                "Network Received (KB)": net_recv_list
            })
            system_usage_df.to_csv(results_file_path, index=False)
            print(f"Final metrics saved to {results_file_path}.")
        else:
            print("No data to save.")
        sys.exit(0)

    def signal_handler(signum, frame):
        """Handle SIGTERM and SIGINT signals"""
        if signum == signal.SIGTERM:
            save_and_exit("SIGTERM received")
        elif signum == signal.SIGINT:
            save_and_exit("SIGINT received (Ctrl+C)")

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while not shutdown_requested:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=interval)

            # Get the memory usage.
            memory_info = psutil.virtual_memory()
            memory_used = round(memory_info.used / (1024 * 1024), 2)  # Convert to MB, 2 decimals
            memory_total = round(memory_info.total / (1024 * 1024), 2)  # Convert to MB, 2 decimals
            memory_percent = memory_info.percent

            # Get the disk usage.
            disk_info = psutil.disk_usage('/')
            disk_used = round(disk_info.used / (1024 * 1024 * 1024), 2)  # Convert to GB, 2 decimals

            # Get the network usage.
            net_io = psutil.net_io_counters()
            net_sent = round((net_io.bytes_sent - net_io_start.bytes_sent) / 1024, 2)  # Convert to KB, 2 decimals
            net_recv = round((net_io.bytes_recv - net_io_start.bytes_recv) / 1024, 2)  # Convert to KB, 2 decimals

            # Get the current time.
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Print the metrics.
            print(f"{current_time:<20}{cpu_usage:<10.2f}{memory_used:<15.2f}{memory_total:<15.2f}{memory_percent:<10.2f}{disk_used:<15.2f}{net_sent:<15.2f}{net_recv:<15.2f}")

            # Store the metrics in the respective columns.
            time_list.append(current_time) 
            cpu_usage_list.append(cpu_usage)
            memory_used_list.append(memory_used)
            memory_total_list.append(memory_total)
            memory_percent_list.append(memory_percent)
            disk_used_list.append(disk_used)
            net_sent_list.append(net_sent)
            net_recv_list.append(net_recv)

            # Note: CSV file will be written only when the script shuts down
    
    except Exception as e:
        save_and_exit(f"Exception occurred: {e}")
        

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Measure system-wide CPU, memory, disk, and network usage.")
    parser.add_argument("--interval", type=float, default=1, required=True, help="Monitoring interval in seconds.")
    parser.add_argument("--num-pods-burst", type=int, required=True, help="Number of pods that were bursted in experiment.")
    parser.add_argument("--iteration", type=int, required=True, help="Iteration number for this measurement run.")
    args = parser.parse_args()   
    monitor_system(args.interval, args.num_pods_burst, args.iteration)