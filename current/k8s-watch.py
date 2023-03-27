from kubernetes import client, config, watch
from kubernetes.config import ConfigException
from urllib3.exceptions import ProtocolError
import concurrent.futures
import os
from contextlib import contextmanager
from time import process_time

# Configure the client to use in-cluster config or local kube config file
try:
   config.load_incluster_config()
except ConfigException:
   config.load_kube_config()

core_api_instance = client.CoreV1Api()
policy_api_instance = client.NetworkingV1Api()

@contextmanager
def timing_processtime(description: str) -> None:
    start = process_time()
    yield
    ellapsed_time = process_time() - start
    print(f"{description}: {ellapsed_time}")


def pods():
    w = watch.Watch()
    try:
        for event in w.stream(core_api_instance.list_namespaced_pod, namespace = "test", timeout_seconds=0):
            updatedPod = event["object"]
            podName = updatedPod.metadata.name
            filename="/home/ubuntu/current/data/{}.yaml".format(podName)

            if event['type'] =="MODIFIED" and updatedPod.metadata.deletion_timestamp == None: # Avoid the MODIFIED on delete
                for cond in updatedPod.status.conditions:
                    if cond.type == "PodScheduled" and cond.status == "True":
                        if not os.path.exists(filename): #to avoid duplicates since modified is repeated on \
                            os.makedirs(os.path.dirname(filename), exist_ok=True)
                            with open(filename, 'w+') as f:
                                os.system("kubectl  get pod {} -n test -o yaml > {}".format(podName, filename))
                            os.system('cp -a {} /home/ubuntu/current/src_dir/'.format(filename))
                            print (f'Pod {podName} added on node {updatedPod.spec.node_name}')
                        else:
                            continue

            elif event['type'] == "DELETED":
                print (f'Pod {podName} has been romoved from the cluster')
                os.system('rm -f /home/ubuntu/current/data/{}.yaml'.format(podName))

    except ProtocolError:
        print("watchPodEvents ProtocolError, continuing..")

def policies():
    w = watch.Watch()
    try:
        for event in w.stream(policy_api_instance.list_namespaced_network_policy, namespace = "test", timeout_seconds=0):
            NewPol = event["object"]
            PolName = NewPol.metadata.name
            if PolName == "default-deny":
                print (f'Policy {PolName}')
                continue
            #with timing_processtime("Time taken: "):
            if event['type'] =="ADDED":
                print (f'Policy {PolName} added on on the cluster')
                filename="/home/ubuntu/current/data/{}.yaml".format(PolName)
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w+') as f:
                    os.system("kubectl  get networkpolicy {} -n test -o yaml > {}".format(PolName, filename))
                os.system('cp -a {} /home/ubuntu/current/src_dir/'.format(filename))
            elif event['type'] =="DELETED":
                print (f'Policy {PolName} has been romoved from the cluster')
                os.system('rm -f /home/ubuntu/current/data/{}.yaml'.format(PolName))
    except ProtocolError:
      print("watchPolicyEvents ProtocolError, continuing..")


def services():
    w = watch.Watch()
    try:
        for event in w.stream(core_api_instance.list_namespaced_service, namespace = "test", timeout_seconds=0):
            svc = event["object"]
            svcName = svc.metadata.name

            #with timing_processtime("Time taken: "):
            if event['type'] =="ADDED":
                print (f'Service {svcName} added on on the cluster')
                filename="/home/ubuntu/current/data/{}.yaml".format(svcName)
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w+') as f:
                    os.system("kubectl  get svc {} -n test -o yaml > {}".format(svcName, filename))
                os.system('cp -a {} /home/ubuntu/current/src_dir/'.format(filename))
            elif event['type'] =="DELETED":
                print (f'Service {svcName} has been romoved from the cluster')
                os.system('rm -f /home/ubuntu/current/data/{}.yaml'.format(svcName))
    except ProtocolError:
      print("watchServiceEvents ProtocolError, continuing..")

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor() as executor:
        p = executor.submit(pods)
        n = executor.submit(policies)
        m = executor.submit(services)

