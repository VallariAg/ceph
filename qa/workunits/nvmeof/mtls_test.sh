#!/bin/bash

set -ex
source /etc/ceph/nvmeof.env

# install yq
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /tmp/yq && chmod +x /tmp/yq

subjectAltName=$(echo "$NVMEOF_GATEWAY_IP_ADDRESSES" | sed 's/,/,IP:/g')

# create certs and keys
# sudo openssl req -x509 -newkey rsa:4096 -nodes -keyout /etc/ceph/server.key -out /etc/ceph/server.crt -days 3650 -subj /CN=my.server -addext "subjectAltName=IP:$subjectAltName"
# sudo openssl req -x509 -newkey rsa:4096 -nodes -keyout /etc/ceph/client.key -out /etc/ceph/client.crt -days 3650 -subj '/CN=client1'

# deploy with mtls
ceph orch ls nvmeof --export > /tmp/gw-conf-original.yaml
# cp /tmp/gw-conf-without-mtls.yaml /tmp/gw-conf-with-mtls.yaml
sudo /tmp/yq ".spec.enable_auth=true | \
    .spec.root_ca_cert=\"mountcert\" | \
    .spec.client_cert = load_str(\"/etc/ceph/client.crt\") | \
    .spec.client_key = load_str(\"/etc/ceph/client.key\") | \
    .spec.server_cert = load_str(\"/etc/ceph/server.crt\") | \
    .spec.server_key = load_str(\"/etc/ceph/server.key\")" /tmp/gw-conf-original.yaml > /tmp/gw-conf-with-mtls.yaml
# /tmp/yq '.spec.enable_auth=true | .spec.root_ca_cert="mountcert"' -i /tmp/gw-conf-with-mtls.yaml

# output=$(sudo cat /etc/ceph/server.key)
# echo $output
# output=$output /tmp/yq e '.spec.certificate = strenv(output)' nvmeof-test.yaml
cat /tmp/gw-conf-with-mtls.yaml 

ceph orch rm nvmeof.mypool.mygroup0
sleep 100
ceph orch apply -i /tmp/gw-conf-with-mtls.yaml

sleep 100
ceph orch ps
ceph orch ls --refresh

IFS=',' read -ra gateway_ips <<< "$NVMEOF_GATEWAY_IP_ADDRESSES"

for i in "${!gateway_ips[@]}"
do
    ip="${gateway_ips[i]}"
    sudo podman run -v /etc/ceph/server.crt:/server.crt:z -v /etc/ceph/client.crt:/client.crt:z \
        -v /etc/ceph/client.key:/client.key:z  \
        -it $NVMEOF_CLI_IMAGE --server-address $ip --server-port $NVMEOF_SRPORT \
        --client-key /client.key --client-cert /client.crt --server-cert /server.crt --format json subsystem list
done
# test


# remove mtls
# yq '.spec.enable_auth=false' -i /tmp/gw-conf-without-mtls.yaml
# ceph orch rm nvmeof.mypool
# ceph orch apply -i /tmp/gw-conf-with-mtls.yaml
# ceph orch reconfig nvmeof.mypool

# test
# podman run -v /etc/ceph/server.crt:/server.crt:z -v /etc/ceph/client.crt:/client.crt:z \
# -v /etc/ceph/client.key:/client.key:z  \
# -it $NVMEOF_CLI_IMAGE --server-address $NVMEOF_DEFAULT_GATEWAY_IP_ADDRESS --server-port $NVMEOF_SRPORT gw into