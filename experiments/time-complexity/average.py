import csv

input_file = "time-complexity-pn.txt"
output_file = "output.csv"

with open(input_file, "r") as f:
    lines = f.readlines()

# Create a list to store values for each step
data_dict = {f"Step {i}": [] for i in range(1, 12)}

current_step = 1
for line in lines:
    parts = line.split(": ")
    if len(parts) == 2:
        value = parts[1].strip()
        data_dict[f"Step {current_step}"].append(value)
        current_step = (current_step % 11) + 1  # Move to the next step, repeat from 1 to 11

with open(output_file, "w", newline="") as csvfile:
    csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    # Write header
    header = list(data_dict.keys())
    csv_writer.writerow(header)

    # Write data
    num_rows = max(len(data) for data in data_dict.values())
    for i in range(num_rows):
        row_data = [data[i] if i < len(data) else '' for data in data_dict.values()]
        csv_writer.writerow(row_data)

print(f"CSV file '{output_file}' has been created.")

