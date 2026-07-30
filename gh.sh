#! /bin/bash

# remove old files in data

export GRASSHOPPER=${GRASSHOPPER:-`pwd`}
rm data/*

#set pernode SG scenario
if [[ "${1,,}" == "pernodesg=true" ]]; then
    singleSGPerNodeScenario=true
elif [[ "${1,,}" == "pernodesg=false" ]]; then
    singleSGPerNodeScenario=false
else
    echo "Invalid argument. Usage: ./gh.sh pernodesg=True|pernodesg=False"
    return 1
fi
# Update the value in the config.py
python3 update-config.py $singleSGPerNodeScenario

#set the hmap variable in Hmap.py
sed -i "s/h_map = {.*/h_map = {}/" Hmap.py

#unset PYTHONPATH
#cd single_sg_per_node/
#export PYTHONPATH="${PYTHONPATH}:/home/ubuntu/single_sg_per_node/"
#path_variable=$(python3 -c "from config import file_path; print(file_path)")
path_variable=$GRASSHOPPER
export PYTHONPATH="${PYTHONPATH}:${path_variable}/"
python3 gh.py 
