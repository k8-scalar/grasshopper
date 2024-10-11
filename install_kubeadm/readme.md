## Prerequisites
The provided scripts have only been tested on Ubuntu20.24 and versions of k8s, containerd, calico as listed in run.sh

The script will also mount an nfs share to which you have access. To know the url, ask the system administrator of your openstack environment 

## Direct/Native routing

For native routing you need to allow that network packets with pod ip addresses as destination are not rejected by the Openstack instance. 

###openstack client

First install the openstack client on one of the vm instances:

```
sudo apt update && sudo apt install python3-openstackclient -y
```



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

edit `./run.sh` to set appropriate values for the `nfs_account` variable, and the `subnet` and `nodes`

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

