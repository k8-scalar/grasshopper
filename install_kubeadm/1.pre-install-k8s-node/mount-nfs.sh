#!/bin/bash
sudo apt update
sudo apt install nfs-common -y
sudo mkdir -p $local_nfs_dir
sudo mount $nfs_account $local_nfs_dir
