from kubernetes import client, config, watch
from kubernetes.config import ConfigException
from urllib3.exceptions import ProtocolError
import os, fcntl,subprocess,yaml,concurrent.futures
from config import file_path

try:
   config.load_incluster_config()
except ConfigException:
   config.load_kube_config()

core_api_instance = client.CoreV1Api()
policy_api_instance = client.NetworkingV1Api()

def pods():
    w = watch.Watch()
    try:
        for event in w.stream(core_api_instance.list_namespaced_pod, namespace = "test"):#, timeout_seconds=0):
            updatedPod = event["object"]
            podName = updatedPod.metadata.name
            labels = updatedPod.metadata.labels
            filename="{}/data/{}.yaml".format(file_path, podName)

            if event['type'] =="MODIFIED" and updatedPod.metadata.deletion_timestamp == None: # Avoid the MODIFIED on delete

                for cond in updatedPod.status.conditions:
                    if cond.type == "PodScheduled" and cond.status == "True":
                        if not os.path.exists(filename): 
                            node_name=f"{updatedPod.spec.node_name}"
                            u_pod = {}
                            u_pod['apiVersion'] = 'v1'
                            u_pod['kind'] = 'Pod'
                            u_pod['metadata'] = {
                                'name': podName,
                                'namespace': 'test',
                                'labels': labels
                            }
                            u_pod['spec']={
                                'nodeName':node_name
                            } 
                            yaml_content = yaml.dump(u_pod, default_flow_style=False, sort_keys=False)
                            os.makedirs(os.path.dirname(filename), exist_ok=True)
                            with open(filename, 'w+') as f:
                                fcntl.flock(f, fcntl.LOCK_EX)
                                f.write(yaml_content)
                                fcntl.flock(f, fcntl.LOCK_UN)
                        else:
                            continue

            elif event['type'] == "DELETED":
                os.system('rm -f {}/data/{}.yaml'.format(file_path, podName))

    except ProtocolError:
        print("watchPodEvents ProtocolError, continuing..")

def policies():
    w = watch.Watch()
    try:
        for event in w.stream(policy_api_instance.list_namespaced_network_policy, namespace = "test"):#, timeout_seconds=0):
            NewPol = event["object"]
            PolName = NewPol.metadata.name
            if PolName == "default-deny":
                print (f'Policy {PolName}')
                continue
            if event['type'] =="ADDED":
                filename="{}/data/{}.yaml".format(file_path, PolName)
                
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                cmd = ["kubectl", "get", "networkpolicy", PolName, "-n", "test", "-o", "yaml"]
                yaml_content = subprocess.check_output(cmd, text=True)

                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    f.write(yaml_content)
                    fcntl.flock(f, fcntl.LOCK_UN)

            elif event['type'] =="DELETED":
                os.system('rm -f {}/data/{}.yaml'.format(file_path, PolName))
    except ProtocolError:
      print("watchPolicyEvents ProtocolError, continuing..")

def services():
    w = watch.Watch()
    try:
        for event in w.stream(core_api_instance.list_namespaced_service, namespace = "test", timeout_seconds=0):
            svc = event["object"]
            svcName = svc.metadata.name

            if event['type'] =="ADDED":
                filename="{}/data/{}.yaml".format(file_path, svcName)
                os.makedirs(os.path.dirname(filename), exist_ok=True)

                cmd = ["kubectl", "get", "svc", svcName, "-n", "test", "-o", "yaml"]
                yaml_content = subprocess.check_output(cmd, text=True)

                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'w+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    f.write(yaml_content)
                    fcntl.flock(f, fcntl.LOCK_UN)

            elif event['type'] =="DELETED":
                os.system('rm -f {}/data/{}.yaml'.format(file_path, svcName))
    except ProtocolError:
      print("watchServiceEvents ProtocolError, continuing..")

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor() as executor:
        p = executor.submit(pods)
        n = executor.submit(policies)
        m = executor.submit(services)

