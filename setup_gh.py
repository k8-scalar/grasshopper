from openstack.create_master_and_workerSG import create_master_and_workerSG
from openstack.detach_defaultSG import detach_defaultSG


def setup_gh():
    create_master_and_workerSG()
    detach_defaultSG()


if __name__ == "__main__":
    setup_gh()
