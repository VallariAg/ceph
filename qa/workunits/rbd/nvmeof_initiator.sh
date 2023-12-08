#!/bin/bash

set -ex

sudo modprobe nvme-fabrics
sudo modprobe nvme-tcp
sudo dnf install nvme-cli -y

# import NVMEOF_GATEWAY_IP_ADDRESS and NVMEOF_GATEWAY_NAME=nvmeof.poolname.smithiXXX.abcde
source /etc/ceph/nvmeof.env

HOSTNAME=$(hostname)
# NVMEOF_RBD_IMAGE="myimage"
# RBD_SIZE=$((1024*8)) #8GiB
# NVMEOF_BDEV="mybdev"
# NVMEOF_SERIAL="SPDK00000000000001"
# NVMEOF_NQN="nqn.2016-06.io.spdk:cnode1"
# NVMEOF_PORT="4420"
# NVMEOF_SRPORT="5500"
# DISCOVERY_PORT="8009"

# rbd create $NVMEOF_POOL/$NVMEOF_RBD_IMAGE --size $RBD_SIZE
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_bdev --pool $NVMEOF_POOL --image $NVMEOF_RBD_IMAGE --bdev $NVMEOF_BDEV
sudo podman images
sudo podman ps
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_subsystem --subnqn $NVMEOF_NQN --serial $NVMEOF_SERIAL
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT add_namespace --subnqn $NVMEOF_NQN --bdev $NVMEOF_BDEV
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT create_listener -n $NVMEOF_NQN -g client.$NVMEOF_GATEWAY_NAME -a $NVMEOF_GATEWAY_IP_ADDRESS -s $NVMEOF_PORT
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT add_host --subnqn $NVMEOF_NQN --host "*"
sudo podman run -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT get_subsystems
sudo lsmod | grep nvme
sudo nvme list
# sudo nvme discover -t tcp -a $NVMEOF_GATEWAY_IP_ADDRESS -s $DISCOVERY_PORT
# sudo nvme connect -t tcp --traddr $NVMEOF_GATEWAY_IP_ADDRESS -s $PORT -n $NVMEOF_NQN
# sudo nvme list

# echo "testing nvmeof initiator..."

# nvme_model="SPDK bdev Controller"

# echo "Test 1: create initiator - starting"
# if ! sudo nvme list | grep -q "$nvme_model"; then
#   echo "nvmeof initiator not created!"
#   exit 1
# fi
# echo "Test 1: create initiator - passed!"


# echo "Test 2: device size - starting"
# image_size_in_bytes=$(($RBD_SIZE * 1024 * 1024))
# nvme_size=$(sudo nvme list --output-format=json | \
#         jq -r ".Devices | .[] | select(.ModelNumber == \"$nvme_model\") | .PhysicalSize")
# if [ "$image_size_in_bytes" != "$nvme_size" ]; then
#   echo "block device size do not match!"
#   exit 1
# fi
# echo "Test 2: device size - passed!"


# echo "Test 3: basic IO - starting"
# nvme_drive=$(sudo nvme list --output-format=json | \
#         jq -r ".Devices | .[] | select(.ModelNumber == \"$nvme_model\") | .DevicePath")
# io_input_file="/tmp/nvmeof_test_input"
# echo "Hello world" > $io_input_file
# truncate -s 2k $io_input_file
# sudo dd if=$io_input_file of=$nvme_drive oflag=direct count=1 bs=2k #write
# io_output_file="/tmp/nvmeof_test_output"
# sudo dd if=$nvme_drive of=$io_output_file iflag=direct count=1 bs=2k #read
# if ! cmp $io_input_file $io_output_file; then
#   echo "nvmeof initiator - io test failed!"
#   exit 1
# fi
# sudo rm -f $io_input_file $io_output_file
# echo "Test 3: basic IO - passed!"


# echo "nvmeof initiator tests passed!"
