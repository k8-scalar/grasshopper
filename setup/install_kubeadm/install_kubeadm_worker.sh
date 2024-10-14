export kubeadm_version=1.31
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl socat
curl -fsSL https://pkgs.k8s.io/core:/stable:/v$kubeadm_version/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v'$kubeadm_version'/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt-get install -y kubelet kubeadm
sudo apt-mark hold kubelet kubeadm
