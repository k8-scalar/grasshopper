import subprocess


def is_openstack():
    """
    Checks if the OpenStack command-line client is installed and accessible.

    This function attempts to run the `openstack --version` command to determine
    if the OpenStack CLI is available on the system. If the command executes
    successfully, it returns True. If the command is not found or cannot be
    executed, it returns False.

    Returns:
        bool: True if the OpenStack CLI is installed and accessible, False otherwise.
    """
    try:
        result = subprocess.run(
            ["openstack", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
