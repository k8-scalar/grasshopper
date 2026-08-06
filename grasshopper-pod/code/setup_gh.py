from openstackfiles.attach_defaultSG import attach_defaultSG
from openstackfiles.create_master_and_workerSG import create_master_and_workerSG


def setup_gh():
    """
    Bootstrap only - does NOT detach "default" from workers. That's a
    separate, later step (see openstackfiles/detach_defaultSG.py) that's only
    safe once Grasshopper is deployed and has actually processed whatever
    NetworkPolicies (e.g. Typha's) open the dynamic rules real traffic needs -
    confirmed live: detaching before that point leaves a real ingress gap -
    see "Why default has to stay on workers until step 6" in README_v2.md.
    """
    # (Re-)attach defaultSG to every worker first, in case a previous
    # Grasshopper deployment on this cluster already detached it - a fresh
    # bootstrap run can't assume "default" is still there.
    attach_defaultSG()

    # Create masterSG and workerSG
    create_master_and_workerSG()


if __name__ == "__main__":
    setup_gh()
