from contextlib import contextmanager
from time import process_time
import subprocess
import time

@contextmanager
def timing_processtime(description: str) -> None:
    start = process_time()
    yield
    ellapsed_time = process_time() - start
    print(f"{description}: {ellapsed_time}\n")


def apply_events(file_name: str, description: str):
    print(description)
    command = f"kubectl apply -f {file_name}"
    subprocess.run(command, shell=True)
    print('\n')
    
def scale_events(deployment_name: str, replicas: int, description: str):
    print(description)
    command = f"kubectl scale deployment {deployment_name} -n test --replicas={replicas}"
    subprocess.run(command, shell=True)
    print('\n')

#create ns test if not existing
namespace = "test"
check_command = f"kubectl get ns {namespace} --no-headers --output=jsonpath={{.metadata.name}} 2>/dev/null"

try:
    subprocess.check_output(check_command, shell=True)
    print(f"Namespace '{namespace}' already exists.")
except subprocess.CalledProcessError:
    create_command = f"kubectl create ns {namespace}"
    subprocess.run(create_command, shell=True)
    print(f"Namespace '{namespace}' created.")


# Can time these commands but
# The timing here is only for applying these resources. It does not take GH config in consideration
apply_events("deployment_S.yaml", "Step 1")
apply_events("networkPolicy_S.yaml", "Step 2")
time.sleep(1)

apply_events("networkPolicy_T.yaml", "Step 3")
apply_events("deployment_T.yaml", "Step 4")
time.sleep(1)

scale_events("pod-s", 2, "Step 5")
time.sleep(1)

scale_events("pod-t", 2, "Step 6")
time.sleep(1)

apply_events("networkPolicy_S2.yaml", "Step 8")
time.sleep(1)

apply_events("networkPolicy_V.yaml", "Step 9")
apply_events("deployment_V.yaml", "Step 10")
time.sleep(1)

scale_events("pod-s", 3, "Step11")
time.sleep(1)

apply_events("deployment_S2.yaml", "Step 12")
