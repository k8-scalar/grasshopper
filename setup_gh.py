from openstackfiles.create_master_and_workerSG import create_master_and_workerSG
from openstackfiles.detach_defaultSG import detach_defaultSG
from openstackfiles.openstack_client import OpenStackClient


def setup_gh():
    # Initialize OpenStack client
    OpenStackClient()

    # Create masterSG and workerSG
    create_master_and_workerSG()

    # Detach defaultSG from all instances
    detach_defaultSG()


if __name__ == "__main__":
    setup_gh()
