from openstack import create_master_and_workerSG, detach_defaultSG


def setup_gh():
    create_master_and_workerSG()
    detach_defaultSG()


if __name__ == "__main__":
    setup_gh()
