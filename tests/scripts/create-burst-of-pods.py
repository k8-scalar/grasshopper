from kubernetes import client, config

def create_pod(api_instance, namespace, pod_name, labels, image="nginx"):
    """
    Create a single pod in the specified namespace.
    """
    pod_manifest = client.V1Pod(
        metadata=client.V1ObjectMeta(name=pod_name, labels=labels),
        spec=client.V1PodSpec(
            containers=[client.V1Container(
                name="container",
                image=image,
                ports=[client.V1ContainerPort(container_port=80)]
            )]
        )
    )

    try:
        api_instance.create_namespaced_pod(namespace=namespace, body=pod_manifest)
        print(f"Pod '{pod_name}' created successfully.")
    except client.exceptions.ApiException as e:
        print(f"Failed to create pod '{pod_name}': {e}")

def create_burst_of_pods(namespace="default", num_pods=100, image="nginx"):
    """
    Create a burst of pods in the specified namespace.
    """
    # Load kubeconfig
    config.load_kube_config()

    # Create the API instance
    api_instance = client.CoreV1Api()

    # Create the specified number of pods
    for i in range(1, num_pods + 1):
        pod_name = f"burst-pod-{i}"
        labels = {"app": "my-app"}
        create_pod(api_instance, namespace, pod_name, labels, image)

if __name__ == "__main__":
    import argparse

    # Argument parser for command-line execution
    parser = argparse.ArgumentParser(description="Create a burst of Kubernetes pods.")
    parser.add_argument("--namespace", type=str, default="default", help="Namespace to create pods in")
    parser.add_argument("--num-pods", type=int, default=100, help="Number of pods to create")
    parser.add_argument("--image", type=str, default="nginx", help="Container image for the pods")
    args = parser.parse_args()

    # Call the function to create pods
    create_burst_of_pods(namespace=args.namespace, num_pods=args.num_pods, image=args.image)


    