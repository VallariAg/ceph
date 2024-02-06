#!/bin/bash

set -ex

sudo modprobe nvme-fabrics
sudo modprobe nvme-tcp
sudo dnf install nvme-cli -y

source /etc/ceph/nvmeof.env

# RBD_POOL and RBD_IMAGE is intended to be set from yaml, 'mypool' and 'myimage' are defaults
RBD_POOL="${RBD_POOL:-mypool}"
RBD_IMAGE="${RBD_IMAGE:-myimage}"

HOSTNAME=$(hostname)
sudo podman images
sudo podman ps
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT subsystem list
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT subsystem add --subsystem $NVMEOF_NQN

# add all namespaces
# for image in `rbd ls $RBD_POOL`; do
for i in $(seq 1 $NVMEOF_NAMESPACES); do
    image="image${i}"
    sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT namespace add --subsystem $NVMEOF_NQN --rbd-pool $RBD_POOL --rbd-image $image
done

# add all gateway listeners
IFS=',' read -ra gateway_ips <<< "$NVMEOF_GATEWAY_IP_ADDRESSES"
IFS=',' read -ra gateway_names <<< "$NVMEOF_GATEWAY_NAMES"
for i in "${!gateway_ips[@]}"
do
    ip="${gateway_ips[i]}"
    name="${gateway_names[i]}"
    echo "Adding gateway listener $index with IP ${ip} and name ${name}"
    sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $ip --server-port $NVMEOF_SRPORT listener add --subsystem $NVMEOF_NQN --gateway-name client.$name --traddr $ip --trsvcid $NVMEOF_PORT
done

sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT host add --subsystem $NVMEOF_NQN --host "*"
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT subsystem list
sudo lsmod | grep nvme
sudo nvme list

echo "[nvmeof] Initiator setup done"