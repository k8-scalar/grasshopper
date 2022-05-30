#! /bin/bash
cd current/
export PYTHONPATH="${PYTHONPATH}:/home/ubuntu/current/"
python3 tests/watch_dog.py 
