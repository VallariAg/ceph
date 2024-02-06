#!/bin/bash -ex

sudo yum -y install fio
sudo yum -y install sysstat

fio_file=$(mktemp -t nvmeof-fio-XXXX)
all_drives_list=$(sudo nvme list --output-format=json | jq -r '.Devices | .[] | select(.ModelNumber == "SPDK bdev Controller") | .DevicePath')

# When the script is passed two arguments (example: `nvmeof_fio_test.sh 1 3`), 
# then fio runs on namespaces only in the defined range (which is 1 to 3 here). 
# So if `nvme list` has 5 namespaces with "SPDK Controller", then fio will 
# run on first 3 namespaces here.
if [ "$#" -eq 2 ]; then
    start=$1
    end=$2
    selected_drives=$(echo "${all_drives_list[@]}" | sed -n "${start},${end}p")
else
    selected_drives="${all_drives_list[@]}"
fi


RUNTIME=${RUNTIME:-600}
# IOSTAT_INTERVAL=10


cat >> $fio_file <<EOF
[nvmeof-fio-test]
ioengine=${IO_ENGINE:-sync}
bsrange=${BS_RANGE:-4k-64k}
numjobs=${NUM_OF_JOBS:-1}
size=${SIZE:-1G}
time_based=1
runtime=$RUNTIME
rw=${RW:-randrw}
filename=$(echo "$selected_drives" | tr '\n' ':' | sed 's/:$//')
verify=md5
verify_fatal=1
EOF

fio --showcmd $fio_file
sudo fio $fio_file &

if [ -n "$IOSTAT_INTERVAL" ]; then
    iostat_count=$(( RUNTIME / IOSTAT_INTERVAL ))
    iostat -d -p $selected_drives $IOSTAT_INTERVAL $iostat_count -h 
fi
wait

echo "[nvmeof] fio test successful!"
