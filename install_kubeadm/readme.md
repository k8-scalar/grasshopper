## Direct/Native routing

For native routing you need to disable source destination checking by disabling port security of each node in your cluster

You do this as follows

To disable **port security** via the **OpenStack Dashboard (Horizon)**, follow these steps:

### Steps to Disable Port Security in OpenStack via the Dashboard (Horizon):

1. **Log in to the OpenStack Dashboard (Horizon)**:
   - Open a browser and navigate to your OpenStack Horizon dashboard.
   - Log in using your credentials.

2. **Navigate to the "Network" Tab**:
   - On the left-hand side of the dashboard, find and click on **"Network"**.
   - Under the "Network" section, click on **"Networks"**.

3. **Select the Desired Network**:
   - From the list of networks, click on the name of the network to which the instance is connected, or where you want to create a new port.

4. **Manage Ports**:
   - In the network details page, you will see a **"Ports"** tab. Click on it.
   - Here, you'll see a list of ports that are associated with this network.

5. **Create a New Port** (or Modify an Existing One):
   - If you want to create a new port with port security disabled, click on the **"Create Port"** button.
   - If you want to modify an existing port, click on the **"Edit"** button next to the port you want to update.

6. **Disable Port Security**:
   - When creating or editing a port, scroll down to the **"Port Security"** option.
   - Uncheck the box labeled **"Enable Port Security"** to disable port security.

7. **Save**:
   - After you’ve unchecked "Enable Port Security," click **"Create"** (for new ports) or **"Save"** (for existing ports) to apply the changes.

8. **Attach the Port to an Instance**:
   - If you've created a new port, you can attach it to an instance. 
   - Go to **"Project" → "Compute" → "Instances"**, select the instance, and attach the port using the "Attach Interface" option.

   If you disabled port security on an existing port already attached to an instance, the changes will take effect immediately.

### Verifying:
After creating or editing the port, you can return to the **"Ports"** tab in the network section to verify that **Port Security** is disabled. It will show as `False` for the port security status of the selected port.

This is how you disable the source/destination check equivalent (port security) via OpenStack's Horizon dashboard.

## Install cluster

execute `chmod -R 750 *.sh`

edit `./run.sh` to set appropriate values for the `nfs_account` variable, and the `subnet` and `nodes` 

execute `./run.sh`. Answer 'y' to all prompts. If the installation halts, enter q or hit the enter key.

wait till the tigerastatus shows only available services

then copy the outputted kubeadm join command into a safe place


then go to every worker node to execute the copied kubeadm join command. Execute it in sudo mode by placing `sudo` before the command  
