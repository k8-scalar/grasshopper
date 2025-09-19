wget https://github.com/containerd/containerd/releases/download/v$containerd_version/containerd-$containerd_version-linux-amd64.tar.gz
sudo tar Czxvf /usr/local containerd-$containerd_version-linux-amd64.tar.gz
wget https://raw.githubusercontent.com/containerd/containerd/main/containerd.service
sudo cp containerd.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now containerd
sudo systemctl status containerd
wget https://github.com/opencontainers/runc/releases/download/v$runc_version/runc.amd64
sudo install -m 755 runc.amd64 /usr/local/sbin/runc
sudo mkdir -p /etc/containerd/
containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup \= false/SystemdCgroup \= true/g' /etc/containerd/config.toml
sudo systemctl restart containerd
wget https://github.com/containerd/nerdctl/releases/download/v$nerdctl_version/nerdctl-$nerdctl_version-linux-amd64.tar.gz
sudo tar Cxzvf /usr/local/bin nerdctl-$nerdctl_version-linux-amd64.tar.gz

