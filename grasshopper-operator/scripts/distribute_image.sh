#!/bin/bash

# Check if an image name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <image-name> <node-name>"
    exit 1
fi

# Check if a node name is provided
if [ -z "$2" ]; then
    echo "Error: You must provide a node name as the second argument."
    echo "Usage: $0 <image-name> <node-name>"
    exit 1
fi

# Define the image name, tar file, and the target node
IMAGE_NAME="$1"
NODE="$2"
TAR_FILE="${IMAGE_NAME//[:\/]/_}.tar"  # Replace colons/slashes to make a valid filename

# SSH user (change if needed)
USER="ubuntu"

echo "Saving Docker image: $IMAGE_NAME..."
docker save -o "$TAR_FILE" "$IMAGE_NAME"

# Check if the tar file was created
if [ ! -f "$TAR_FILE" ]; then
    echo "Error: Failed to save Docker image."
    exit 1
fi

# Copy and load the image to the specified node
echo "Copying $TAR_FILE to $NODE..."
scp "$TAR_FILE" "$USER@$NODE:~/$TAR_FILE"

echo "Loading image on $NODE..."
ssh "$USER@$NODE" "sudo ctr -n k8s.io images import ~/$TAR_FILE && rm ~/$TAR_FILE"

echo "Image loaded and tar file removed on $NODE!"

# Optionally delete the tar file locally as well
echo "Cleaning up local tar file..."
rm "$TAR_FILE"

echo "✅ Image distribution complete!"
