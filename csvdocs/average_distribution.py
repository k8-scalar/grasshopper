import os
import pandas as pd
path = os.getcwd()
files = os.listdir(path)
files_xlsx = [f for f in files if f[-17:] == 'distribution.xlsx']#only files ending in 'distribution.xlsx'
df = pd.DataFrame()
for f in files_xlsx:
    data = pd.read_excel(f)
    df = pd.concat([df, data])
    

grouped = df.groupby('Name')

# Calculate mean and standard deviation for numeric columns
stats = grouped.agg({col: ['mean', 'std'] for col in df.select_dtypes(include='number').columns})

# Flatten the multi-index columns
stats.columns = ['_'.join(col).strip() for col in stats.columns.values]

# Reset index if desired
stats.reset_index(inplace=True)

print(stats)    #df = df.append(data)
