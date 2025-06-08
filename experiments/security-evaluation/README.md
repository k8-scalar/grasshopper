### Instructions for carrying out security evaluation experiment. 


## Setup. 

Firstly ensure that the cloud environment is in an least-privilege setting. 


## Static configuration case. 

Now, we are going to statically apply an application security group to all worker nodes, 
allowing ingress and egress traffic on ports that the application uses (e.g. 8080).

1. Apply cluster setup. 

    > openstack create security group ...

    > openstack attach sg to nodes ...

2. Test connections.

    Trying an ncat connection between the nodes in the cluster works, for all nodes to which to application-sg is applied.


## Dynamic enforcement case (GH):

Now, we will evaluate the case for when GH is running (and ensuring least-privilege)

1. Run the GH program.

    Go to the grasshoper folder, then grasshopper-code, then code.

        > cd ../../grasshopper/grasshopper-code/code
    
    Start the program.

      > python3 main.py --namespace default --mode PLS

2. Apply cluster setup:

    > ./scripts/apply-all-yamls.sh setup/

This sets up the cluster with one application pod running on worker-1, and one running on worker-2. 
It also applies a Network Policy that allows traffic between application pods.

--> Running the GH program while doing this setup, should lead to appriopriate security groups being added to the nodes.

3. Test connections.

    Trying an ncat connection on port 8080 between the nodes, quickly shows this only works between worker-1 and worker-2.

    The connection does not work between the worker node and every other node in the cluster, since the sgs are not 
    being attached to this node, allowing connections on application ports.
