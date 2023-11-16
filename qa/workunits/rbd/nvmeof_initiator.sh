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
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_bdev --pool $RBD_POOL --image $RBD_IMAGE --bdev $NVMEOF_BDEV
sudo podman images
sudo podman ps
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_subsystem --subnqn $NVMEOF_NQN --serial $NVMEOF_SERIAL
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT add_namespace --subnqn $NVMEOF_NQN --bdev $NVMEOF_BDEV
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_listener -n $NVMEOF_NQN -g client.$NVMEOF_GATEWAY_NAME -a $NVMEOF_GATEWAY_IP_ADDRESS -s $NVMEOF_PORT
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT add_host --subnqn $NVMEOF_NQN --host "*"
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT get_subsystems
sudo lsmod | grep nvme
sudo nvme list
