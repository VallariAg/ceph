#!/bin/bash

set -ex


source /etc/ceph/nvmeof.env

# Set these in job yaml
RBD_POOL="${RBD_POOL:-mypool}"
RBD_IMAGE_PREFIX="${RBD_IMAGE_PREFIX:-myimage}"

HOSTNAME=$(hostname)
sudo podman images
sudo podman ps
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT --format json subsystem list

IFS=',' read -ra gateway_ips <<< "$NVMEOF_GATEWAY_IP_ADDRESSES"
IFS=',' read -ra gateway_names <<< "$NVMEOF_GATEWAY_NAMES"

list_subsystems () { 
   for i in "${!gateway_ips[@]}"
    do
        ip="${gateway_ips[i]}"
        sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $ip --server-port $NVMEOF_SRPORT --format json subsystem list
    done
}

list_subsystems

# add all subsystems
for i in $(seq 1 $NVMEOF_SUBSYSTEMS_COUNT); do
    subsystem_nqn="${NVMEOF_SUBSYSTEMS_PREFIX}${i}"
    sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT subsystem add --subsystem $subsystem_nqn
done

list_subsystems

# add all gateway listeners 
for i in "${!gateway_ips[@]}"
do
    ip="${gateway_ips[i]}"
    name="${gateway_names[i]}"
    for j in $(seq 1 $NVMEOF_SUBSYSTEMS_COUNT); do
        subsystem_nqn="${NVMEOF_SUBSYSTEMS_PREFIX}${j}"
        echo "Adding gateway listener $index with IP ${ip} and name ${name}"
        sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $ip --server-port $NVMEOF_SRPORT listener add --subsystem $subsystem_nqn --gateway-name client.$name --traddr $ip --trsvcid $NVMEOF_PORT
    done
done

list_subsystems

# add all hosts
for i in $(seq 1 $NVMEOF_SUBSYSTEMS_COUNT); do
    subsystem_nqn="${NVMEOF_SUBSYSTEMS_PREFIX}${i}"
    sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT host add --subsystem $subsystem_nqn --host "*"
done

list_subsystems

# add all namespaces
image_index=1
for i in $(seq 1 $NVMEOF_SUBSYSTEMS_COUNT); do
    subsystem_nqn="${NVMEOF_SUBSYSTEMS_PREFIX}${i}"
    for ns in $(seq 1 $NVMEOF_NAMESPACES_COUNT); do
        image="${RBD_IMAGE_PREFIX}${image_index}"
        sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT namespace add --subsystem $subsystem_nqn --rbd-pool $RBD_POOL --rbd-image $image
        ((image_index++))
    done
done

list_subsystems
# list subsystems
# for i in "${!gateway_ips[@]}"
# do
#     ip="${gateway_ips[i]}"
#     sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $ip --server-port $NVMEOF_SRPORT --format json subsystem list
# done

rados -p mypool listomapvals $(rados -p mypool ls | grep nvmeof)


sudo modprobe nvme-fabrics
sudo modprobe nvme-tcp
sudo dnf install nvme-cli -y
sudo lsmod | grep nvme

DISCOVERY_PORT="8009"
sudo nvme discover -t tcp -a $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS -s $DISCOVERY_PORT
sudo nvme connect-all -t tcp --traddr $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS -l 1800
nvme list
sudo nvme list-subsys
sudo nvme list-subsys --output-format=json
dmesg -T | tail -n 200

list_subsystems

echo "[nvmeof] Subsystem setup done"
