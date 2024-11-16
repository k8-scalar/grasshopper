#! /bin/bash

export GRASSHOPPER=${GRASSHOPPER:-`pwd`}

# Set default values
singleSGPerNodeScenario=true
distributed=false

# Process arguments (optional)
for arg in "$@"; do
    case "${arg,,}" in
        pernodesg=true)
            singleSGPerNodeScenario=true
            ;;
        pernodesg=false)
            singleSGPerNodeScenario=false
            ;;
        distributed=true)
            distributed=true
            ;;
        distributed=false)
            distributed=false
            ;;
        *)
            echo "Invalid argument: $arg. Usage: ./gh.sh [pernodesg=true|pernodesg=false] [distributed=true|distributed=false]"
            exit 1
            ;;
    esac
done

path_variable=$GRASSHOPPER
export PYTHONPATH="${PYTHONPATH}:${path_variable}/"

# Pass the parsed values to the Python script
python3 gh.py $singleSGPerNodeScenario $distributed