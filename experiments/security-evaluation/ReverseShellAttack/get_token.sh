pod_uid=$(./get_uid_of_cass_pod.sh)
cat /var/lib/kubelet/pods/"$pod_uid"/volumes/kubernetes.io~projected/kube-api-access-w678m/token 

