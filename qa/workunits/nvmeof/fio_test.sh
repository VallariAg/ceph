#!/bin/bash -ex

sudo yum -y install fio
sudo yum -y install sysstat

namespace_range_start=
namespace_range_end=
random_devices_count=
rbd_iostat=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --start_ns)
            namespace_range_start=$2
            shift 2
            ;;
        --end_ns)
            namespace_range_end=$2
            shift 2
            ;;
        --random_devices)
            random_devices_count=$2
            shift 2
            ;;
        --rbd_iostat)
            rbd_iostat=true
            shift
            ;;
        *)
            exit 100	# Internal error
            ;;
    esac
done

fio_file=$(mktemp -t nvmeof-fio-XXXX)
all_drives_list=$(sudo nvme list --output-format=json | 
    jq -r '.Devices[].Subsystems[] | select(.Controllers | all(.ModelNumber == "Ceph bdev Controller")) | .Namespaces | sort_by(.NSID) | .[] | .NameSpace')

# When the script is passed --start_ns and --end_ns (example: `nvmeof_fio_test.sh --start_ns 1 --end_ns 3`), 
# then fio runs on namespaces only in the defined range (which is 1 to 3 here). 
# So if `nvme list` has 5 namespaces with "SPDK Controller", then fio will 
# run on first 3 namespaces here.
if [ "$namespace_range_start" ] || [ "$namespace_range_end" ]; then
    selected_drives=$(echo "${all_drives_list[@]}" | sed -n "${namespace_range_start},${namespace_range_end}p")
elif [ "$random_devices_count" ]; then 
    selected_drives=$(echo "${all_drives_list[@]}" | shuf -n $random_devices_count)
else
    selected_drives="${all_drives_list[@]}"
fi


RUNTIME=${RUNTIME:-600}
filename=$(echo "$selected_drives" | sed -z 's/\n/:\/dev\//g' | sed 's/:\/dev\/$//')
filename="/dev/$filename"

FIO_NVME=${TESTDIR:-$(mktemp -d)}/archive/fio-nvme
mkdir -p $FIO_NVME
fio_file="$FIO_NVME/temp_fio.ini"

# List of iodepth values
iodepth_values=(1 2 4 8 16 20 24 28 32 40 48)

# Output CSV
csv_output="$FIO_NVME/fio_results_4_dev_strong_same_sub.csv"
echo "iodepth,job1_iops_mean,job1_clat_ns_mean,job2_iops_mean,job2_clat_ns_mean,job3_iops_mean,job3_clat_ns_mean,job4_iops_mean,job4_clat_ns_mean" > $csv_output
#echo "iodepth,job1_iops_mean,job1_clat_ns_mean" >  $csv_output

# Run fio for each iodepth
for depth in "${iodepth_values[@]}"; do
    echo "Running fio with iodepth=$depth"

    json_file="${FIO_NVME}/fio_output_iodepth_${depth}.json"

    # Create a temporary fio job file with current iodepth
    cat > $FIO_NVME/temp_fio.ini <<EOF
[global]
ioengine=libaio
invalidate=0
rw=randwrite
runtime=90
time_based=1
ramp_time=30
numjobs=1
direct=1
bs=4096B
iodepth=$depth
end_fsync=0
norandommap=1

EOF

counter=1
for i in $selected_drives; do
  echo "[job$counter]" >> "$fio_file"
  echo "filename=/dev/$i" >> "$fio_file"
  echo "" >> "$fio_file"  # Adds a blank line
  counter=$((counter+1))
done

    cat $FIO_NVME/temp_fio.ini 
    # Run fio and save output
    fio --output-format=json $FIO_NVME/temp_fio.ini > "$json_file"

    # Extract write.iops_mean and write.clat_ns.mean for each job
    job1_iops_mean=$(jq '.jobs[0].write.iops_mean' "$json_file")
    job1_clat=$(jq '.jobs[0].write.clat_ns.mean' "$json_file")
    
    job2_iops_mean=$(jq '.jobs[1].write.iops_mean' "$json_file")
    job2_clat=$(jq '.jobs[1].write.clat_ns.mean' "$json_file")
    
    job3_iops_mean=$(jq '.jobs[2].write.iops_mean' "$json_file")
    job3_clat=$(jq '.jobs[2].write.clat_ns.mean' "$json_file")
    
    job4_iops_mean=$(jq '.jobs[3].write.iops_mean' "$json_file")
    job4_clat=$(jq '.jobs[3].write.clat_ns.mean' "$json_file")

    # Append results to CSV file
    echo "$depth,$job1_iops_mean,$job1_clat,$job2_iops_mean,$job2_clat,$job3_iops_mean,$job3_clat,$job4_iops_mean,$job4_clat" >> "$csv_output"
#    echo "$depth,$job1_iops_mean,$job1_clat" >> "$csv_output"
done

echo "Done. Results saved to $csv_output"


# cat $fio_file

# status_log() {
#     POOL="${RBD_POOL:-mypool}"
#     GROUP="${NVMEOF_GROUP:-mygroup0}"
#     ceph -s
#     ceph orch host ls
#     ceph orch ls 
#     ceph orch ps
#     ceph health detail
#     ceph nvme-gw show $POOL $GROUP
#     sudo nvme list
#     sudo nvme list | wc -l
#     sudo nvme list-subsys
#     for device in $selected_drives; do
#         echo "Processing device: $device"
#         sudo nvme list-subsys /dev/$device
#         sudo nvme id-ns /dev/$device
#     done
    
# }


# echo "[nvmeof.fio] starting fio test..."

# if [ -n "$IOSTAT_INTERVAL" ]; then
#     iostat_count=$(( RUNTIME / IOSTAT_INTERVAL ))
#     iostat -d -p $selected_drives $IOSTAT_INTERVAL $iostat_count -h &
# fi
# if [ "$rbd_iostat" = true  ]; then
#     iterations=$(( RUNTIME / 5 ))
#     timeout 20 rbd perf image iostat $RBD_POOL --iterations $iterations &
# fi
# fio --showcmd $fio_file

# set +e 
# sudo fio $fio_file
# if [ $? -ne 0 ]; then
#     echo "[nvmeof.fio]: fio failed!" 
#     status_log
#     exit 1
# fi


echo "[nvmeof.fio] fio test successful!"
