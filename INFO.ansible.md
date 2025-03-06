# aro-e2e

# Azure Red Hat OpenShift (ARO) Cluster Provisioning with Ansible

This repository provides Ansible playbooks and roles to automate the provisioning of an Azure Red Hat OpenShift (ARO) cluster. Follow the steps below to set up and manage your ARO cluster efficiently.

## Prerequisites

Before you begin, ensure you have the following:

1. **Azure Subscription**: An active Azure subscription is required to create resources.

2. **Service Principal**: An Azure Service Principal with sufficient permissions to manage ARO resources.

3. **Azure CLI**: Install the Azure CLI to interact with Azure services:

   **On RHEL/Fedora:**

   ```bash
   sudo dnf install azure-cli
   ```

   **On Ubuntu/Debian:**

   ```bash
   curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
   ```

## Setup Instructions

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/openshift/aro-e2e.git
   cd aro-e2e
   ```

2. **Configure Azure Credentials**:

   Authenticate using azure-cli, selecting your chosen subscription if necessary:

   ```bash
   az login
   ```

3. **Build the Image via Makefile**:

   ```bash
   make ansible-image
   ```

## Configuration Options

1. **Environment**:

   The Makefile accepts environment variables for tuning and configuration. Alternatively, it is possible to pass parameters directly to `make cluster` if needed, discussed later.

   See ./ansible/README.md for some additional detail.

   e.g.

   ```bash
   CLUSTERPREFIX=aro-example
   LOCATION=centralindia
   CLUSTERPATTERN=udr
   # - `basic`: Simplest cluster, nothing fancy
   # - `private`: Simple cluster with apiserver and ingress visibility set to private.
   # - `enc`: Encryption-at-host enabled
   # - `udr`: UserDefinedRouting with a blackhole Route Table
   # - `byok`: Disk encryption using bring-your-own-key
   # For other possible values, see ./ansible/hosts.yaml
   ```

   Private clusters, including CLUSTERPATTERN=private and CLUSTERPATTERN=udr, will cause the creation of a jumphost to access the cluster API.
   Your local SSH public key will be passed to the jumphost, then ansible will use your corresponding private key to connect to it. If your local SSH configuration differs from defaults, the Makefile supports modification through variables SSH_CONFIG_DIR and SSH_KEY_BASENAME.

## Provisioning and testing

1. **Run the Playbook via Makefile**:

   Execute the Ansible playbook to provision the ARO cluster:

   ```bash
   make cluster
   ```

   Append parameters as required, e.g. if not exported as env:

   ```bash
   make cluster CLUSTERPREFIX=aro-example
   ```

## Running the Playbook manually via container runtime

   ```bash
   podman run \
     --rm \
     -it \
     --network=host \
     --mount type=tmpfs,dst=/opt/app-root/src/.azure/cliextensions \
     -v ${AZURE_CONFIG_DIR:-~/.azure}:/opt/app-root/src/.azure \
     -v ./ansible:/ansible \
     -v ${HOME}/.ssh/:/root/.ssh \
     -v ./ansible_collections/azureredhatopenshift/cluster/:/opt/app-root/src/.local/share/pipx/venvs/ansible/lib/python3.11/site-packages/ansible_collections/azureredhatopenshift/cluster \
     aro-ansible:example \
       -i inventory/upgrades.yaml \
       -l udr \
       -e location=eastus \
       -e CLUSTERPREFIX=aro-example \
       -e CLEANUP=False \
       -e SSH_KEY_BASENAME=id_rsa \
        \
       deploy.playbook.yaml
   ```

   In place of `aro-ansible:example`, use the container image built at step 3 above.

## Day-2 and clean-up

1. **Accessing the cluster**:
   On successful cluster creation, obtain its admin kubeconfig (details provided in the output of make at successful completion):

   ```shell
   az aro get-admin-kubeconfig -n {{ name }} -g {{ resource_group }} -f {{ name }}_{{ resource_group }}.kubeconfig
   export KUBECONFIG={{ name }}_{{ resource_group }}.kubeconfig
   ```

   If you created a private or UDR cluster, create a SOCKS5 tunnel via SSH on the jumphost VM, and edit the kubeconfig to point to it:

   ```shell
   yq '.clusters[0].cluster.proxy-url="socks5://localhost:8002"' {{ name }}_{{ resource_group }}.kubeconfig > {{ name }}_{{ resource_group }}.socks5.kubeconfig
   export KUBECONFIG={{ name }}_{{ resource_group }}.socks5.kubeconfig
   ssh arosre@{{ jumphost_vm_public_ip }} -D 8002 -q -N &
   ```

2. **Clean Up**:

   To delete the cluster:

   ```shell
   make cluster-cleanup {{ ... }}
   ```

   Append the same arguments to `make cluster-cleanup` as you used for `make cluster` run, or ensure the same env is exported.

## Troubleshooting

TBC

## Additional Resources

- **Ansible Documentation**: [https://docs.ansible.com/](https://docs.ansible.com/)

- **Azure Red Hat OpenShift Documentation**: [https://docs.microsoft.com/en-us/azure/openshift/](https://docs.microsoft.com/en-us/azure/openshift/)

- **Private Clusters**: <https://learn.microsoft.com/en-us/azure/openshift/howto-create-private-cluster-4x>

- **Multiple Public IPs**: <https://learn.microsoft.com/en-us/azure/openshift/howto-multiple-ips>

## Contributing

We welcome contributions to enhance these playbooks. Please fork the repository and submit a pull request with your improvements.

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
