#!/bin/bash

# This scripts applies all network policy .yaml files for a given directory recursively.
# When no directory is specified, it assumes the current working directory.
#

# Usage: 
#     
#    First, give the file execution rights
#
#        chmod +x ~/grasshopper/tests/scripts/apply-all-policies.sh
#
#    While inside the grasshopper directory: 
#       
#       ./tests/scripts/apply-all-policies.sh ~/grasshopper/tests/TestPolicies/
#


# Exit the script on any error
set -e

# Check if a directory argument is provided
if [ "$#" -eq 1 ]; then
    BASE_DIR="$1"
else
    BASE_DIR=$(pwd)  # Default to the current directory
fi

# Check if the supplied directory exists
if [ ! -d "$BASE_DIR" ]; then
    echo "Error: Directory $BASE_DIR does not exist."
    exit 1
fi

echo "Applying all YAML files in directory and subdirectories: $BASE_DIR"

# Find all YAML files recursively and apply them
find "$BASE_DIR" -type f \( -name "*.yaml" -o -name "*.yml" \) | while read -r file; do
    echo "Applying $file..."
    kubectl apply -f "$file"
done

echo "All YAML files applied successfully."