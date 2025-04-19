import psutil
import time
import pandas as pd
from datetime import datetime 

RESULSTS_FILE_PATH = "./results/system_usage.csv"

def monitor_system(interval=1):
    """
    Monitors system-wide CPU, memory, disk, and network usage.
    """
    print("Monitoring system-wide CPU, memory, disk, and network usage.")
    print("Press Ctrl+C to stop monitoring.")
    print(f"{'Time':<20}{'CPU (%)':<10}{'Mem Used (MB)':<15}{'Mem Total (MB)':<15}{'Mem (%)':<10}{'Disk Used (GB)':<15}{'Net Sent (KB)':<15}{'Net Recv (KB)':<15}")

    # Initialize CPU usage measurement
    psutil.cpu_percent(interval=0)
    net_io_start = psutil.net_io_counters()

    time_list = []
    cpu_usage_list = []
    memory_used_list = []
    memory_total_list = []
    memory_percent_list = []
    disk_used_list = []
    net_sent_list = []
    net_recv_list = []

    try:
        while True:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=interval)

            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_used = round(memory_info.used / (1024 * 1024), 2)  # Convert to MB, 2 decimals
            memory_total = round(memory_info.total / (1024 * 1024), 2)  # Convert to MB, 2 decimals
            memory_percent = memory_info.percent

            # Disk usage
            disk_info = psutil.disk_usage('/')
            disk_used = round(disk_info.used / (1024 * 1024 * 1024), 2)  # Convert to GB, 2 decimals

            # Network usage
            net_io = psutil.net_io_counters()
            net_sent = round((net_io.bytes_sent - net_io_start.bytes_sent) / 1024, 2)  # Convert to KB, 2 decimals
            net_recv = round((net_io.bytes_recv - net_io_start.bytes_recv) / 1024, 2)  # Convert to KB, 2 decimals

            # Get the current time as a human-readable string
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Print the metrics
            print(f"{current_time:<20}{cpu_usage:<10.2f}{memory_used:<15.2f}{memory_total:<15.2f}{memory_percent:<10.2f}{disk_used:<15.2f}{net_sent:<15.2f}{net_recv:<15.2f}")

            # Store the metrics
            time_list.append(current_time) 
            cpu_usage_list.append(cpu_usage)
            memory_used_list.append(memory_used)
            memory_total_list.append(memory_total)
            memory_percent_list.append(memory_percent)
            disk_used_list.append(disk_used)
            net_sent_list.append(net_sent)
            net_recv_list.append(net_recv)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        print("Storing metrics to file...")

        # Saving the metrics to a file
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
        system_usage_df.to_csv(RESULSTS_FILE_PATH, index=False)
        print(f"Metrics saved to {RESULSTS_FILE_PATH}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Measure system-wide CPU, memory, disk, and network usage.")
    parser.add_argument("--interval", type=int, default=1, help="Monitoring interval in seconds.")
    args = parser.parse_args()   
    monitor_system(args.interval)