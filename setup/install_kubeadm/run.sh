export kubeadm_version=1.31
export kubernetes_master_node=172.22.8.143
export subnetmask=172.22.8
export nodes="146 28"
export calico_version=3.28.2
export nfs_account=kronos-dnet-hera.cs.kuleuven.be:/prjeddy
export local_nfs_dir=/mnt/nfs-disk-2/
export containerd_version=1.7.22
export runc_version=1.1.14
export nerdctl_version=1.7.7
export cni_plugins_version=1.5.1
export pod_cidr=192.168.0.0/16
sed -i "s/kubernetes_service_host: \".*\"/kubernetes_service_host: \"${kubernetes_master_node}\"/g" calico-setup/calico-configmap.yml
sed -i "s/export kubeadm_version=.*/export kubeadm_version=${kubeadm_version}/g" install_kubeadm_worker.sh
sed -i "s/\"cniVersion\": .*/\"cniVersion\": \"${cni_plugins_version}\"/g"   calico-setup/calico-configmap.yml
sed -i "s|cidr: .*|cidr: ${pod_cidr}|g"  calico-setup/custom-resources.yaml
for var in nfs_account local_nfs_dir containerd_version runc_version nerdctl_version cni_plugins_version
do
    sed -i "s|export $var=.*|export $var=${!var}|g" 1.pre-install-k8s-node/pre-k8s-node.sh
done
cd 1.pre-install-k8s-node; chmod 700 *.sh; ./pre-k8s-node.sh; cd ..
./install_kubeadm_master.sh
./install_cluster.sh
