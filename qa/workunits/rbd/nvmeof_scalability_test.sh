#!/bin/bash -xe


GATEWAYS=$1 # exmaple "nvmeof.a,nvmeof.b"
DELAY="${SCALING_DELAYS:-50}"

if [ -z "$GATEWAYS" ]; then
    echo "At least one gateway needs to be defined for scalability test"
    exit 1
fi

pip3 install yq

# downscaling (remove $GATEWAYS)
echo "[nvmeof] Removing ${GATEWAYS}"
ceph orch ls nvmeof --export > /tmp/nvmeof-gw.yaml
ls /tmp/nvmeof-gw.yaml
ceph nvme-gw show mypool '' # (assert all deployed) 
cat /tmp/nvmeof-gw.yaml
yq "del(.placement.hosts[] | select(. | test(\".*($(echo $GATEWAYS | sed 's/,/|/g'))\")))" /tmp/nvmeof-gw.yaml > /tmp/nvmeof-gw-new.yaml
ceph orch apply -i /tmp/nvmeof-gw-new.yaml
sleep $DELAY

# upscaling (bring up all originally deployed daemons)
ceph nvme-gw show mypool '' 
ceph orch ls
ceph orch ps
ceph orch apply -i /tmp/nvmeof-gw.yaml 
# ceph orch daemon start nvmeof.a
sleep $DELAY
ceph nvme-gw show mypool '' # (assert all deployed)  
ceph orch ls
ceph orch ps

echo "[nvmeof] scalability test passed for ${GATEWAYS}"
