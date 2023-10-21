#!/bin/bash -ex

# sudo modprobe nvme-fabrics
# sudo modprobe nvme-tcp

GATEWAY=$(cat /etc/ceph/nvmeof.cfg |grep 'gateway_addr' | awk -F'[, ]' '{print $3}')
IP=$(cat /etc/ceph/nvmeof.cfg |grep 'ip_address' | awk -F'[, ]' '{print $3}')
HOSTNAME=$(hostname)

echo -e "<---- exec.client.0---- HOST/IP -- $HOSTNAME/$IP ---->"

#IP=`cat /etc/ceph/iscsi-gateway.cfg |grep 'trusted_ip_list' | awk -F'[, ]' '{print $3}'`
#sudo podman run -it quay.io/ceph/nvmeof-cli:0.0.3 --server-address $IP --server-port 5500 create_bdev --pool nvmeofpool --image myimage --bdev nvmeof
IMAGE="quay.io/ceph/nvmeof-cli:0.0.3"
POOL="mypool"
MIMAGE="myimage"
BDEV="mybdev"
SERIAL="SPDK00000000000001"
NQN="nqn.2016-06.io.spdk:cnode1"
PORT="4420"
SRPORT="5500"
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT create_bdev --pool $POOL --image $MIMAGE --bdev $BDEV
sudo podman images
sudo podman ps
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT create_subsystem --subnqn $NQN --serial $SERIAL
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT add_namespace --subnqn $NQN --bdev $BDEV
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT create_listener -n $NQN -g client.$GATEWAY -a $IP -s $PORT
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT add_host --subnqn $NQN --host "*"
sudo podman run -it $IMAGE --server-address $IP --server-port $SRPORT get_subsystems
sudo lsmod | grep nvme
sudo nvme list
sudo nvme connect -t tcp --traddr $IP -s $PORT -n $NQN
sudo nvme list

echo "testing nvmeof controller..."

if ! sudo nvme list | grep -q "SPDK bdev Controller"; then
  echo "nvmeof controller not created!"
  exit 1
fi

echo "nvmeof controller created: success!"