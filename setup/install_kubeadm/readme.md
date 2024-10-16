## Prerequisites
The provided scripts have only been tested on Ubuntu24.04 and versions of k8s, containerd, calico as listed in run.sh

A number of nodes have been created as VMs (i.e. openstack instances) to take the role of a master node and multiple worker nodes.

Ensure that ssh keys are installed on master and worker nodes so master can ssh to worker nodes
Add appropriate config file to .ssh directory on master node or use ssh agent to automatically select the correct key


### Openstack client

Install the openstack client on one of the master node.

```
sudo apt update && sudo apt install python3-openstackclient -y
```

### Set the Openstack variables


```
export OS_AUTH_URL=https://hera.cs.kuleuven.be:5000
export OS_AUTH_TYPE=v3applicationcredential
export OS_IDENTITY_API_VERSION=3
export OS_REGION_NAME=RegionOne
export OS_INTERFACE=public
```

Then you need to set application credentials that are scoped to your project. You do this via the Identities menu of the Horizon dashboard service of Openstack. In case you have multiple projects, first activate the relevant project, then create the application credentials. Dowload the cloud.yaml file to save yout secret.

```
export OS_APPLICATION_CREDENTIAL_ID=<your credential id>
export OS_APPLICATION_CREDENTIAL_ID
export OS_APPLICATION_CREDENTIAL_SECRET=<your credential secret>
export OS_APPLICATION_CREDENTIAL_SECRET
```
Preferably you add these export staments to the .bashrc file in the home directory of your master node.


### Open default security group

Adjust the default security group of your VMs to an overly permissive setting. This eases the installation of the K8s cluster. Later you can restrict the security group towards only opening those ports and protocols needed for an operational K8s cluster.

Set the `PROJECT` and `SG` variables in the `create_default_security_group.sh` script and execute it. This will install the following rules:

```
direction='ingress', ethertype='IPv4', normalized_cidr='0.0.0.0/0', port_range_max='22', port_range_min='22', protocol='tcp', remote_ip_prefix='0.0.0.0/0' (SSH)                                                                                                            ddi

direction='ingress', ethertype='IPv4', protocol='icmp', remote_ip_prefix='0.0.0.0/0' (ICMP)

direction='ingress', ethertype='IPv6',remote_group_name='default'  (All IPv6-based protocols and ports from instances with default security group attached)

direction='ingress', ethertype='IPv4', remote_group_name='default' (All IPv4-based protocols and ports from instances with default security group attached)

direction='egress', ethertype='IPv4',  remote_ip_prefix='0.0.0.0/0' (All IPv4-based protocols and ports to anywhere)

direction='egress', ethertype='IPv6', remote_ip_prefix='::/0'  (All IPv6-based protocols and ports to anywhere)
```



## Direct/Native routing

For native routing you need to allow that network packets with pod ip addresses as destination are not rejected by the Openstack instance. 




### Using CIDR Range with Allowed Address Pairs

When updating a port's `allowed_address_pairs`, you can specify a CIDR block instead of individual IP addresses. This allows the instance to accept packets for any IP address within that CIDR range.

### Command Syntax

Here’s how you would use the `openstack port set` command to specify a CIDR range for allowed address pairs:

```bash
openstack port set --allowed-address ip-address=<cidr_range> <port_id>
```

### Example Command

For instance, if you want to allow the CIDR range `10.101.11.0/24` on the port with ID `12345678-1234-5678-1234-567812345678`, you would run the following command:

```bash
openstack port set --allowed-address ip-address=10.101.11.0/24 <port_id>
```

### Steps to Implement

1. **Identify the Port**: Use the following command to find the port ID associated with your instance:

   ```bash
   openstack port list
   ```

2. **Update the Port with Allowed Address Pairs**: Use the `openstack port set` command with the CIDR range as shown in the example.

3. **Verify the Changes**: After updating the port, you can verify the configuration with:

   ```bash
   openstack port show <port_id>
   ```

   Look for the `allowed_address_pairs` field in the output to confirm that your CIDR range has been applied correctly.



## Install cluster

execute `chmod -R 750 *.sh`

Put the following line into the ~/.bashrc file, to get kubectl autocompletion: `source <(kubectl completion bash)`

edit `./run.sh` to set appropriate values for the `kubernetes_master`, `subnet` and `nodes` variables. For example: if the VM subnet is 172.22.14.0/24, the master nodle runs on 172.22.14.100 and the worker nodes run on 172.22.14.89 and 172.22.14.90, then set these variables in `run.sh` as follows:
```
kubernetes_master=172.22.14.100
subnet=172.22.14
nodes="89 90"
```


execute `./run.sh`. Answer 'y' or 'yes' to all prompts. If the installation halts, enter 'q' or hit

wait till the tigerastatus shows only available services

then copy the outputted kubeadm join command into a safe place

then go to every worker node to execute the copied kubeadm join command. Execute it in sudo mode by placing `sudo` before the command


### Disabling/Enabling the kube-proxy
The service load balancing is also done by the calico plugin. Therefore the kube-proxy can be removed.
This can be done using the following command:

```
kubectl patch ds -n kube-system kube-proxy -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-calico": "true"}}}}}'
```
When you add new worker nodes via the `kubeam join` command however. The kube-proxy should be temporarily re-enabled. 

```
kubectl patch ds -n kube-system kube-proxy -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-calico": null}}}}}'
   
```

### Troubleshooting

1. The worker nodes remain unhealthy. 
 * check the output of `kubectl get pods -n calico-system`. If there are non-initialized pods:
   * execute: `kubectl patch ds -n kube-system kube-proxy -p '{"spec":{"template":{"spec":{"nodeSelector":{"non-calico": "null"}}}}}'`
   * ssh into each worker node and execute sudo reboot
2. The tigerastatus reports a degraded status:
   * check the logs of the tigera-operator in the tigera-operator namespace with the command `kubect logs -n tigera-operator <tigera-operator> 

