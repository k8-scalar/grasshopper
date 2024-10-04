import os

directory_path = './'
files_to_empty = ['netperf-gh.log','netperf-ghfly.log', 'netperf-nogh.log', 'saas-gh.log', 'saas-nogh.log', 'saas-ghfly.log', 'teastore-gh.log', 'teastore-nogh.log', 'teastore-ghfly.log']

def empty_files(directory, filenames):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file in filenames:
                file_path = os.path.join(root, file)
                with open(file_path, 'w') as f:
                    f.truncate(0)

empty_files(directory_path, files_to_empty)
