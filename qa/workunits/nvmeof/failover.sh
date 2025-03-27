#!/bin/bash -xe

sleep 300 # 60 * 5

ceph orch daemon stop nvmeof.nvmeof.a
ceph orch daemon stop nvmeof.nvmeof.b

sleep 300 # 60 * 5
