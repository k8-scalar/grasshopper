## Install a K8s cluster on Openstack with native routing enabled

See [setup/install_kubeadm/readme.md](setup/install_kubeadm/readme.md)

Make sure your kubernetes cluster is properly setup.

The setup should be the same as for the original GH version.

## Starting the GH instance.

1) Go the the GH directory.

    > cd grasshopper/grasshopper-code/code

2) Start GH instance.

    > python3 main.py --mode PLS --namespace test-thesis

    Possible modes (PLS, PLS). Make sure the namespace exists by creating it in the K8s system.



