import os
import pandas as pd
path = os.getcwd()
files = os.listdir(path)
files_xlsx = [f for f in files if f[-13:] == 'requests.xlsx']#only files ending in 'distribution.xlsx'
df_r = pd.DataFrame()
for f in files_xlsx:
    data = pd.read_excel(f)
    df_r = pd.concat([df_r, data])
    
# Group by 'Name' and calculate mean and standard deviation for numeric columns
grouped = df_r.groupby('Name')

# Calculate mean and standard deviation for numeric columns
stats = grouped.agg({col: ['mean', 'std'] for col in df_r.select_dtypes(include='number').columns})

# Flatten the multi-index columns
stats.columns = ['_'.join(col).strip() for col in stats.columns.values]

# Reset index if desired
stats.reset_index(inplace=True)

print(stats)
