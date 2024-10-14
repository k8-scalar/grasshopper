sudo mkdir -p /opt/cni/bin/
sudo wget https://github.com/containernetworking/plugins/releases/download/v$cni_plugins_version/cni-plugins-linux-amd64-v$cni_plugins_version.tgz
sudo tar Cxzvf /opt/cni/bin cni-plugins-linux-amd64-v$cni_plugins_version.tgz
sudo systemctl restart containerd
