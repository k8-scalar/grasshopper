export containerd_version=1.7.22
export runc_version=1.1.14
export nerdctl_version=1.7.7
export cni_plugins_version=1.5.1
./install-cri.sh

rm *gz
rm containerd.service
rm runc.amd64
