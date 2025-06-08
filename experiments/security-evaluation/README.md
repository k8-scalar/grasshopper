### Instructions for carrying out security evaluation experiment. 

## Dynamic enforcement case (GH):

1. Apply cluster setup: 

    > ./scripts/apply-all-yamls.sh setup/

This sets up the cluster with one application pod running on worker-1, and one 
running on worker-2. 
It also applies a Network Policy that allows traffic between application pods.

--> Running the GH program while doing this setup, should lead to appriopriate security groups being added to the nodes.

2. Test connections.

    Trying an ncat connection on port 8080 between the nodes, quickly shows this only works between worker-1 and worker-2.

    The connection does not work between the worker node and every other node in the cluster, since the sgs are not 
    being attached to this node allowing connections on application ports.


## Static configuration case. 

1. Apply cluster setup. 

    > openstack create security group ...

    > openstack attach sg to nodes ...

2. Test connections.

    Trying an ncat connection between the nodes in the cluster works, for all nodes to which to application-sg is applied.

