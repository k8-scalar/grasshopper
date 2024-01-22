import csv
import statistics

from kubernetes import client, config
from datetime import datetime
from statistics import mean

# out of cluster!
config.load_kube_config()

# In cluster config!
# config.load_incluster_config()

v1 = client.CoreV1Api()
api_instance = client.AppsV1Api()


#TeaStore
APPGROUP_LABEL = "appgroup.diktyo.x-k8s.io"
APPGROUP_TEASTORE = "teastore"
PODS = ["teastore-auth", "teastore-db", "teastore-image","teastore-persistence","teastore-recommender",
        "teastore-registry", "teastore-webui", "teastore-locust"]
# Infrastructure
GOOD = ["test-worker-1", "test-worker-4"]
BAD = ["test-master2", "test-worker-2", "test-master"]





def save_to_csv(file_name, pod_name, hostname, init, ready, latency, segment):
    file = open(file_name, 'a+', newline='')  # append
    # file = open(file_name, 'w', newline='')
    with file:
        fields = ['pod_name', 'hostname', 'init', 'ready', 'latency', 'segment']
        writer = csv.DictWriter(file, fieldnames=fields)
        # writer.writeheader()
        writer.writerow(
            {'pod_name': pod_name,
             'hostname': hostname,
             'init': init,
             'ready': ready,
             'latency': latency,
             'segment': segment}
        )


def main():
    print("Starting...")
    namespace = "test"
    file_name = "results.csv"

    deployments = api_instance.list_namespaced_deployment(namespace=namespace)
    #pods = v1.list_namespaced_pod(namespace=namespace)

    # print("Pods: {}".format(pods))
    init = []
    ready = []
    latency = []

    init_float = []
    ready_float = []
    latency_float = []

    deployment_creation_time = [] 
    pod_conditions = []
    pod_names = []
    hostnames = []
    segment_count = 0
    segment = False

    for deployment in deployments.items:
        try:
             #labels = deployment.spec.template.metadata.labels
             #if labels[APPGROUP_LABEL] == APPGROUP_TEASTORE:
               print("Checking deployment {}...".format(deployment.metadata.name))
               deployment_name=deployment.metadata.name
               deployment_creation_time.append(deployment.metadata.creation_timestamp)
               pod = v1.list_namespaced_pod(namespace=namespace, label_selector=f'run={deployment_name}').items[0]
               print("Checking pod {}...".format(pod.metadata.name))
               pod_names.append(pod.metadata.name)
               hostnames.append(pod.spec.node_name)
               pod_conditions.append(pod.status.conditions)
        except KeyError:
            print("AppGroup Label not present")
    
    pods = len(pod_names)
    i = 0
    previous_segment=None
    done=False
    different_segments=False
    for cond, creation_timestamp in zip(pod_conditions,deployment_creation_time):
        # cond[0].type == Initialized
        # cond[1].type == Ready
        # cond[2].type == ContainersReady
        # cond[3].type == PodScheduled
        init.append(creation_timestamp)
        ready.append(cond[3].last_transition_time)
        latency.append((cond[3].last_transition_time-creation_timestamp).total_seconds())

        init_float.append(creation_timestamp.timestamp())
        ready_float.append(cond[3].last_transition_time.timestamp())
        latency_float.append((cond[3].last_transition_time-creation_timestamp).total_seconds())

        print("pod {}: ready: {} - init: {} = {} seconds".format(pod_names[i], ready[i], init[i], latency[i]))

        if hostnames[i] in GOOD:
            segment = True
            print("Pod is placed in Good segment")
            segment_count = segment_count + 1
        else:
            segment = False
        if previous_segment != None and not done:
            if segment != previous_segment:
               different_segments=True
               done=True
        previous_segment = segment
        save_to_csv(file_name, pod_names[i], hostnames[i], init[i], ready[i], latency[i], segment)
        i = i + 1
    
    print("Statistics ")
    print("Num pods: {}".format(pods))
    print("Good segment: {}".format(segment_count))
    print("Bad segment: {}".format(pods - segment_count))

    # Calculate standard deviation
    # print("Standard Deviation init: {}".format(datetime.fromtimestamp(statistics.stdev(init_float))))
    # print("Standard Deviation ready: {}".format(datetime.fromtimestamp(statistics.stdev(ready_float))))
    # print("Standard Deviation latency: {}".format(datetime.fromtimestamp(statistics.stdev(latency_float))))

    save_to_csv(file_name, "total", "total",
                datetime.fromtimestamp(mean(init_float)),
                datetime.fromtimestamp(mean(ready_float)),
                datetime.fromtimestamp(mean(latency_float)),
                segment_count/pods)
    f = open("cross-segmentation", "w")
    if different_segments:
        f.write('yes')
    else:
        f.write('no')
    f.close()

if __name__ == "__main__":
    main()
