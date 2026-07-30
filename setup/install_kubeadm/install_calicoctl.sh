curl -L https://github.com/projectcalico/calico/releases/download/v$calico_version/calicoctl-linux-amd64 -o calicoctl
chmod +x ./calicoctl
sudo mv calicoctl /usr/bin/
