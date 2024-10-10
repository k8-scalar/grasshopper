for i in $nodes
do 
	echo installing kubeadm on node $subnetmask.$i
	scp -r 1.pre-install-k8s-node install_kubeadm_worker.sh reset-iptables.sh $subnetmask.$i:
       	ssh $subnetmask.$i 'cd 1.pre-install-k8s-node; chmod 700 *.sh; ./pre-k8s-node.sh; cd ..; rm -r 1.pre-install-k8s-node; chmod 700 *.sh; ./install_kubeadm_worker.sh; rm ./install_kubeadm_worker.sh'
	ssh $subnetmask.$i 'sudo rm -r /var/lib/kubelet/*; sudo kubeadm reset;'
	#./reset-iptables.sh'
done
sudo rm -r /var/lib/kubelet/*
sudo kubeadm reset
#./reset-iptables.sh
sudo  kubeadm init --pod-network-cidr=$pod_cidr
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v$calico_version/manifests/tigera-operator.yaml
#kubectl create -f calico-setup/calico-configmap.yml
kubectl create -f calico-setup/custom-resources.yaml
watch kubectl get tigerastatus
#kubectl patch ds -n kube-system kube-proxy -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-calico": "true"}}}}}'
