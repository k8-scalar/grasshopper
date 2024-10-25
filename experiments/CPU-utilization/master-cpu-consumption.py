import psutil
import time
import csv

output_file = "saas-ghv4-cpu-usage.csv"  

# CSV header
csv_header = ["Max CPU Usage (%)", "Max Memory Usage (%)", "Current CPU Usage (%)", "Current Memory Usage (%)"]

# List to store values
data = []

def calculate_average(data):
    # Calculate the average of each column
    averages = [sum(column) / len(column) for column in zip(*data)]
    return averages

with open(output_file, "w", newline="") as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(csv_header)

    max_cpu_percent = 0.0
    max_mem_percent = 0.0

    try:
        while True:
            cpu_percent = psutil.cpu_percent(interval=1)
            mem_percent = psutil.virtual_memory().percent

            if cpu_percent >= max_cpu_percent:
                max_cpu_percent = cpu_percent

            if mem_percent >= max_mem_percent:
                max_mem_percent = mem_percent

            current_row = [max_cpu_percent, max_mem_percent, cpu_percent, mem_percent]

            csv_writer.writerow(current_row)
            data.append(current_row)
            print(current_row)  

            time.sleep(5)  

    except KeyboardInterrupt:
        print("Script terminated by user.")
        # Calculate and print averages
        if data:
            averages = calculate_average(data)
            print("\nAverage values on interruption:")
            for header, avg in zip(csv_header, averages):
                print(f"Average-{header}: {avg}")


