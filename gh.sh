#! /bin/bash

export GRASSHOPPER=${GRASSHOPPER:-`pwd`}

# Set pernode SG scenario (optional, defaults to true)
if [[ -z "$1" ]]; then
    singleSGPerNodeScenario=true
elif [[ "${1,,}" == "pernodesg=true" ]]; then
    singleSGPerNodeScenario=true
elif [[ "${1,,}" == "pernodesg=false" ]]; then
    singleSGPerNodeScenario=false
else
    echo "Invalid argument for pernodesg. Usage: ./gh.sh [pernodesg=true|pernodesg=false] [distributed=true|false]"
    exit 1
fi

# Set distributed scenario (optional, defaults to false)
if [ -z "$2" ]; then
    distributed=false
elif [[ "${2,,}" == "distributed=true" ]]; then
    distributed=true
elif [[ "${2,,}" == "distributed=false" ]]; then
    distributed=false
else
    echo "Invalid argument for distributed. Usage: ./gh.sh [pernodesg=true|pernodesg=false] [distributed=true|false]"
    exit 1
fi

path_variable=$GRASSHOPPER
export PYTHONPATH="${PYTHONPATH}:${path_variable}/"

# Pass the parsed values to the Python script
python3 gh.py $singleSGPerNodeScenario $distributed