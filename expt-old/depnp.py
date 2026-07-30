import os
import time

os.system("kubectl apply -f deny-all.yaml")
os.system("kubectl apply -f testpolicy1.yaml")
os.system("kubectl apply -f testpolicy2.yaml")
time.sleep(10)

