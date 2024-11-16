# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY kubelet_watch.py /app/
COPY classes.py /app/

# Copy kubeletctl from the root directory into the container
COPY kubeletctl /usr/local/bin/

# Run kubelet_watch.py when the container launches
CMD ["python", "kubelet_watch.py"]