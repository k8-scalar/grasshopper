import os
import pandas as pd
path = os.getcwd()
files = os.listdir(path)
files_csv = [f for f in files if f[-3:] == 'csv']
for filename in files_csv:
    #df = pd.read_csv(os.path.join(path, filename), delimiter=",") #Read each file
    #df.to_excel(os.path.join(path, filename.split(".")[0]+".xlsx"), index=False) #Write to xlsx in locl dir
    df = pd.read_csv(filename) #Read each file
    df.to_excel(filename.split(".")[0]+".xlsx", index=False) #Write to xlsx in locl dir
