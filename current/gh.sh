#! /bin/bash
unset PYTHONPATH
#cd single_sg_per_node/
#export PYTHONPATH="${PYTHONPATH}:/home/ubuntu/single_sg_per_node/"
path_variable=$(python3 -c "from config import file_path; print(file_path)")
export PYTHONPATH="${PYTHONPATH}:${path_variable}/"
python3 gh.py 
