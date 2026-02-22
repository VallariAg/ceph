# -*- coding: utf-8 -*-
# This file is moved from the original work of "nvmeof-top" tool in:
# https://github.com/pcuzner/ceph-nvmeof-top 
# by Paul Cuzner <pcuzner@ibm.com>
import threading
import time
import logging
import grpc
import asyncio
import json

from .. import mgr
from mgr_module import HandleCommandResult
from ..cli import DBCLICommand

from .nvmeof_client import NVMeoFClient
from .nvmeof_cli import NvmeofGatewaysConfig
from .nvmeof_conf import get_pool_group_name

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def get_collector(session_id: str):
    MAX_SESSION_TTL = 60 * 60
    return mgr.get_nvmeof_collector(session_id, MAX_SESSION_TTL)

def get_lbg_gws_map(service_name: str): # TODO: uncomment
    # pool_group = ['mypool', 'mygroup']
    pool_group = get_pool_group_name(service_name)
    if not pool_group:
        logger.error("Error getting pool name and group name of the service")
        return {}
    logger.info(f"VALLARI_DEBUG: {pool_group=}")
    pool, group = pool_group
    try:
        cmd = {
            'prefix': 'nvme-gw show', 
            'pool': pool, 
            'group': group, 
            'format': 'json'
        }
        ret_status, out, _ = mgr.mon_command(cmd)
        logger.info(f"VALLARI_DEBUG: {ret_status=} {out=}")
        if ret_status == 0 and out is not None:
            lbg_gws_map = {}
            gws_info = json.loads(out)
            for gw in gws_info["Created Gateways:"]:
                gw_id = str(gw["gw-id"]).removeprefix("client.")
                gw_lbg = int(gw["anagrp-id"])
                lbg_gws_map[gw_lbg] = gw_id
            return lbg_gws_map
        return {}
    except Exception:
        logger.exception('Failed to get nvme-gw show command')
        return {}

class NVMeoFTopTool:
    headers = []
    template = ""

    def __init__(self, args: dict, client: NVMeoFClient, data_collector):
        self.client = client
        self.args = args
        self.server_addr = client.gateway_addr
        self.collector: NvmeofTopCollector = data_collector
        self.reverse_sort = args.get('sort_descending', False)
        self.sort_key = args.get('sort_by')
        self.group = args.get('group')
   
    def run(self) -> None:
        self.collector.initialise(self)
        if not self.collector.ready:
            status_code = self.collector.health.rc
            return (status_code, f"nvmeof-top has encountered an error: {self.collector.health.msg}")

        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        t.join()

        if not self.collector.ready:
            status_code = self.collector.health.rc
            return (status_code, self.collector.health.msg)
        
        try:
            rt_stdout = self.to_stdout()
            rt_stdout += "\n ---- "
            return (0, rt_stdout)
        except Exception as ex:
            logger.exception(ex)
            return (8, str(ex))

    
    def _run(self):
        pass

    def to_stdout(self):
        pass


class NVMeoFTopCPU(NVMeoFTopTool):
    reactors_headers = ['Gateway', 'Thread Name', 'Busy Rate%', 'Idle Rate%']
    reactors_template = "{:<30}   {:<30}   {:>20}   {:>20}\n"

    def __init__(self, args: dict, client: NVMeoFClient, data_collector):
        super().__init__(args, client, data_collector)
        self.gws_service = args.get('service', None)

    def _run(self):
        if self.collector.ready:
            asyncio.run(self.collector.collect_cpu_data())

    def to_stdout(self):
        sort_pos = NVMeoFTopCPU.reactors_headers.index(self.sort_key)
        reactor_data = self.collector.get_reactor_data(sort_pos=sort_pos, 
                                                       reverse_sort=self.reverse_sort)
        rows = []
        if self.args.get('with_timestamp'):
            tstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.collector.timestamp))
            rows.append(f"{tstamp} (delay: {self.collector.delay})\n")
        
        if not self.args.get('no_header'):
            rows.append(NVMeoFTopCPU.reactors_template.format(*NVMeoFTopCPU.reactors_headers))
        for reactor in reactor_data:
            rows.append(NVMeoFTopCPU.reactors_template.format(*reactor))
        rows.append("\n")

        return ''.join(rows)  

class NVMeoFTopIO(NVMeoFTopTool):
    subsystem_summary_headers = ['Subsystem', 'Namespaces',]
                                #   'Total IOPS', 'Throughput']
    summary_headers = ['Gateway', 'Load Balancing Group', 'Total Subsystems', 'Total Namespaces']

    ns_headers = ['NSID', 'RBD Image', 'IOPS', 'r/s', 'rMB/s', 'r_await', 'rareq-sz', 'w/s', 'wMB/s', 'w_await', 'wareq-sz', 'LBGrp', 'QoS']
    ns_template = "{:>4}   {:<40}   {:>7}   {:>6}   {:>6}   {:>7}   {:>8}   {:>6}   {:>6}   {:>7}   {:>8}   {:^5}   {:>3}\n"

    def __init__(self, args: dict, client: NVMeoFClient, data_collector):
        super().__init__(args, client, data_collector)
        self.subsystem_nqn = args.get('subsystem')

    def _run(self):
        if self.collector.ready:
            asyncio.run(self.collector.collect_io_data())

    def to_stdout(self):
        sort_pos = NVMeoFTopIO.ns_headers.index(self.sort_key)
        ns_data = self.collector.get_sorted_namespaces(sort_pos=sort_pos, 
                                                        reverse_sort=self.reverse_sort)
        subsystem_summary_data = self.collector.get_subsystem_summary_data()
        overall_summary_data = self.collector.get_overall_summary_data()

        rows = []
        if self.args.get('with_timestamp'):
            tstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.collector.timestamp))
            rows.append(f"{tstamp} (delay: {self.collector.delay})\n")
        if self.args.get('summary'):
            summary_row = ""
            for index, header in enumerate(NVMeoFTopIO.summary_headers):
                summary_row += f"{header}: {overall_summary_data[index]}  "
            rows.append(summary_row + "\n")
            subsys_summary_row = ""
            for index, header in enumerate(NVMeoFTopIO.subsystem_summary_headers):
                subsys_summary_row += f"{header}: {subsystem_summary_data[index]}  "
            rows.append(subsys_summary_row + "\n\n")
        if not self.args.get('no_header'):
            rows.append(NVMeoFTopIO.ns_template.format(*NVMeoFTopIO.ns_headers))
        if ns_data:
            for ns in ns_data:
                rows.append(NVMeoFTopIO.ns_template.format(*ns))
        else:
            rows.append("<no namespaces defined>\n")

        return ''.join(rows) 


@DBCLICommand.Read('nvmeof top cpu', poll=True)
def nvmeof_top_cpu(_, service: str = '',
                server_addr: str = '', group: str = '',
                descending: bool = False, sort_by: str = 'Thread Name',
                with_timestamp: bool = False,
                no_header: bool = False,
                session_id: str = None):
    '''
    NVMeoF Top CPU Tool
    --period [-p] <delay> (default 1s, max 3600s)
    --server-addr <ip>
    --group '<group_name>'
    --sort-by '<header>'
    --descending
    --with-timestamp 
    --print-header
    '''
    args = {
        'service': service,
        'with_timestamp': with_timestamp,
        'no_header': no_header,
        'sort_descending': descending,
        'sort_by': sort_by,
        'server_addr': server_addr,
        'group': group,
    }
    try:
        gateway_client = NVMeoFClient(group, server_addr)
        data_collector = get_collector(session_id)

        top_tool = NVMeoFTopCPU(args, gateway_client, data_collector) 
        rc, output = top_tool.run()
        return HandleCommandResult(stdout=output, retval=rc) 
    except Exception as exc:
        logger.exception(exc)
        return HandleCommandResult(stderr=str(exc), retval=8)

@DBCLICommand.Read('nvmeof top io', poll=True)
def nvmeof_top_io(_, subsystem: str = '',
                server_addr: str = '', group: str = '',
                descending: bool = False, sort_by: str = 'NSID',
                with_timestamp: bool = False,
                summary: bool = False, no_header: bool = False,
                session_id: str = None):
    '''
    NVMeoF Top IO Tool
    --period [-p] <delay> (default 1s, max 3600s)
    --subsystem '<nqn>'
    --server-addr <ip>
    --group '<group_name>'
    --descending
    --sort-by '<header>'
    --with-timestamp 
    --summary
    --no-header
    '''
    args = {
        'subsystem': subsystem,
        'with_timestamp': with_timestamp,
        'summary': summary,
        'no_header': no_header,
        'sort_descending': descending,
        'sort_by': sort_by,
        'server_addr': server_addr,
        'group': group,
    }
    try:
        if not subsystem:
            err_message = "Required argument '--subsystem' missing"
            return HandleCommandResult(stderr=err_message, retval=8)
        gateway_client = NVMeoFClient(group, server_addr)
        data_collector = get_collector(session_id)

        top_tool = NVMeoFTopIO(args, gateway_client, data_collector) 
        rc, output = top_tool.run()
        return HandleCommandResult(stdout=output, retval=rc)
    except Exception as exc:
        logger.exception(exc)
        return HandleCommandResult(stderr=str(exc), retval=8)


class Health:
    def __init__(self):
        self.rc = 0
        self.msg = ''


class Counter: 
    def __init__(self):
        self.current = 0.0
        self.last = 0.0

    def update(self, new_value: float):
        """Update the stats maintaining current and last"""
        self.last = self.current
        self.current = new_value

    def rate(self, interval: float):
        """Calculate the per second change rate"""
        return (self.current - self.last) / interval


class PerformanceStats:
    def __init__(self, bdev: str, delay: int):
        self.bdev = bdev
        self.read_ops = Counter()
        self.read_bytes = Counter()
        self.read_secs = Counter()
        self.write_ops = Counter()
        self.write_bytes = Counter()
        self.write_secs = Counter()

        self.read_ops_rate = 0
        self.write_ops_rate = 0
        self.read_bytes_rate = 0
        self.write_bytes_rate = 0
        self.total_ops_rate = 0
        self.total_bytes_rate = 0
        self.rareq_sz = 0.0
        self.wareq_sz = 0.0
        self.r_await = 0.0
        self.w_await = 0.0

    def calculate(self, delay: int):
        self.read_ops_rate = self.read_ops.rate(delay)
        self.read_bytes_rate = self.read_bytes.rate(delay)
        self.read_secs_rate = self.read_secs.rate(delay)
        self.write_ops_rate = self.write_ops.rate(delay)
        self.write_bytes_rate = self.write_bytes.rate(delay)
        self.write_secs_rate = self.write_secs.rate(delay)

        self.total_ops_rate = self.read_ops_rate + self.write_ops_rate
        self.total_bytes_rate = self.read_bytes_rate + self.write_bytes_rate

        if self.read_ops_rate:
            self.rareq_sz = (int(self.read_bytes_rate / self.read_ops_rate) / 1024)
            self.r_await = ((self.read_secs_rate / self.read_ops_rate) * 1000)  # for ms
        else:
            self.rareq_sz = 0.0
            self.r_await = 0.0
        if self.write_ops_rate:
            self.wareq_sz = (int(self.write_bytes_rate / self.write_ops_rate) / 1024)
            self.w_await = ((self.write_secs_rate / self.write_ops_rate) * 1000)  # for ms
        else:
            self.wareq_sz = 0.0
            self.w_await = 0.0


class ReactorStats:
    def __init__(self, thread: str):
        self.thread = thread
        self.tick_rate = Counter()
        self.busy = Counter()
        self.idle = Counter()

        self.busy_secs = Counter()
        self.idle_secs = Counter()

        self.busy_rate = 0.0
        self.idle_rate = 0.0

    def calculate(self, delay: int):
        self.busy_rate = self.busy_secs.rate(delay)
        self.idle_rate = self.idle_secs.rate(delay)


class NvmeofTopCollector:
    def __init__(self):
        self.cmd_handler = None
        self.subsystem_nqn = ''
        self.server_addr = ''
        self.delay = 1000
        self.namespaces = {}
        self.lbg_gw = {}
        self.subsystems = None
        self.reactor_stats = {}
        self.iostats = {}
        self.iostats_lock = threading.Lock()
        self.gw_info = None
        self.timestamp = time.time()
        self.health = Health()

    @property
    def nqn_list(self):
        return [subsys.nqn for subsys in self.subsystems.subsystems]

    @property
    def ready(self) -> bool:
        return self.health.rc == 0

    @property
    def total_namespaces_defined(self) -> int:
        return len(self.namespaces[self.subsystem_nqn])

    # @property
    # def namespaces_bdevs(self) -> int:
    #     return [ns.bdev_name for ns in self.namespaces[self.subsystem_nqn]]

    @property
    def total_subsystems(self) -> int:
        return len(self.nqn_list)
    
    @property
    def total_namespaces_overall(self):
        total = 0
        for subsys in self.subsystems.subsystems:
            total += subsys.namespace_count
        return total

    # @property
    # def total_iops(self):
    #     return int(sum([stats.total_ops_rate for _, stats in self.iostats[self.server_addr].items()]))

    # @property
    # def total_bandwidth(self):
    #     return sum([stats.total_bytes_rate for _, stats in self.iostats[self.server_addr].items()])

    @property
    def max_namespaces(self):
        for subsys in self.subsystems.subsystems:
            if subsys.nqn == self.subsystem_nqn:
                return subsys.max_namespaces
        logger.error("Request for max namespaces could not find a match against the NQN! Returning 0")
        return 0
    
    @property
    def load_balancing_group(self):
        logger.info(f"VALLARI_DEBUG: {self.gw_info=}")
        return self.gw_info.load_balancing_group

    def log_connection(self):
        logger.info(f"Connected to {self.server_addr}")

    def get_sorted_namespaces(self, sort_pos: int, reverse_sort: bool):
        logger.info("get_sorted_namespaces")
        ns_data = []
        for ns in self.namespaces[self.subsystem_nqn]:

            ns_info = f"{ns.rbd_pool_name}/{ns.rbd_image_name}"
            bdev_name = ns.bdev_name

            if not self.cmd_handler.args.get('server_addr'):
                lbg = ns.load_balancing_group
                daemon_name = self.lbg_gw[lbg]
                perf_stats = self.iostats[daemon_name][bdev_name]
            else:
                perf_stats = self.iostats[self.client.daemon_name][bdev_name]
            perf_stats.calculate(self.delay)

            ns_data.append((
                ns.nsid,
                ns_info,
                int(perf_stats.total_ops_rate),
                int(perf_stats.read_ops_rate),
                f"{self.bytes_to_MB(perf_stats.read_bytes_rate):3.2f}",
                f"{perf_stats.r_await:3.2f}",
                f"{perf_stats.rareq_sz:4.2f}",
                int(perf_stats.write_ops_rate),
                f"{self.bytes_to_MB(perf_stats.write_bytes_rate):3.2f}",
                f"{perf_stats.w_await:3.2f}",
                f"{perf_stats.wareq_sz:4.2f}",
                self.lb_group(ns.load_balancing_group),
                self.qos_enabled(ns)
            ))

        ns_data.sort(key=lambda t: t[sort_pos], reverse=reverse_sort)
        return ns_data
    
    def get_reactor_data(self, sort_pos: int, reverse_sort: bool):
        logger.info("get_reactor_data")
        reactor_data = []
        for gw_addr in self.reactor_stats:
            for thread_name in self.reactor_stats[gw_addr]:
                thread_stats = self.reactor_stats[gw_addr][thread_name]
                thread_stats.calculate(self.delay)
                reactor_data.append((
                    gw_addr,
                    thread_stats.thread,
                    f"{thread_stats.busy_rate:3.2f}",
                    f"{thread_stats.idle_rate:3.2f}",
                ))
        reactor_data.sort(key=lambda t: t[sort_pos], reverse=reverse_sort)
        return reactor_data

    def get_subsystem_summary_data(self):
        return [
            self.subsystem_nqn, 
            f'{self.total_namespaces_defined} / {self.max_namespaces}', 
            # self.total_iops, 
            # f'{(self.total_bandwidth / 1024**2):>7.2f} MiB/s'
        ]

    def get_overall_summary_data(self):
        return [
            self.server_addr,
            self.load_balancing_group,
            self.total_subsystems,
            self.total_namespaces_overall,
        ]

    def qos_enabled(self, ns) -> str:
        if (ns.rw_ios_per_second or ns.rw_mbytes_per_second or ns.r_mbytes_per_second or ns.w_mbytes_per_second):
            return 'Yes'
        return 'No'
    
    def lb_group(self, grp_id: int):
        """Provide a meaningful default when load-balancing is not in use"""
        return "N/A" if grp_id == 0 else f"{grp_id}"

    def bytes_to_MB(self, bytes: int, si: int = 1024):
        """Simple conversion of bytes to with MiB or MB"""
        return (bytes / si) / si

    # grpc methods
    def call_grpc_api(self, method_name, request, client = None):
        logger.debug(f"calling gprc method {method_name}")
        if not client:
            client = self.client
        try:
            func = getattr(client.stub, method_name)
            data = func(request)
        except grpc._channel._InactiveRpcError:
            self.health.rc = 8
            self.health.msg = f"RPC endpoint unavailable at {client.gateway_addr}"
            logger.error(f"gprc call to {method_name} failed: {self.health.msg}")
            return None

        self.health.msg = f"{method_name} success"
        logger.debug(f"call to {method_name} successful")
        return data

    def _get_namespaces_iostat(self, client):
        # gateway_addr = client.gateway_addr
        daemon_name = client.daemon_name
        
        logger.info(f"fetching iostats for namespaces from {daemon_name}")
        with self.iostats_lock:
            logger.info('iostats lock acquired')
            # if ns.bdev_name not in self.iostats:
            #     self.iostats[ns.bdev_name] = PerformanceStats(ns.bdev_name, self.delay)
            logger.info('calling list_namespaces_io_stats')
            stats = self.call_grpc_api('list_namespaces_io_stats',
                                       NVMeoFClient.pb2.list_namespaces_io_stats_req())
            if daemon_name not in self.iostats:
                self.iostats[daemon_name] = {}
            
            logger.info(stats)

            for ns in stats.namespaces:
                bdev_name = ns.bdev_name
                logger.info(f"VALLARI_DEBUG_SHOW {bdev_name}: {ns}")
                if bdev_name not in self.iostats[daemon_name]:
                    logger.info(f"VALLARI_DEBUG_SHOW: add PerformanceStats")
                    self.iostats[daemon_name][bdev_name] = PerformanceStats(bdev_name, self.delay)                

                ns = dict(ns)
                logger.info(f"VALLARI_DEBUG_SHOW: {ns=}")
                
                iostats = self.iostats[daemon_name][bdev_name]
                iostats.read_ops.update(ns.get('num_read_ops', 0))
                iostats.read_bytes.update(ns.get('bytes_read', 0))
                iostats.read_secs.update((ns.get('read_latency_ticks', 0) / stats.tick_rate))
                iostats.write_ops.update(ns.get('num_write_ops', 0))
                iostats.write_bytes.update(ns.get('bytes_written', 0))
                iostats.write_secs.update((ns.get('write_latency_ticks', 0) / stats.tick_rate))
            logger.info(f"VALLARI_DEBUG_SHOW: {self.iostats}")

    def _get_ns_iostats(self, ns):
        logger.debug(f"fetching iostats for namespace {ns.nsid}")
        with self.iostats_lock:
            logger.debug('iostats lock acquired')
            if ns.bdev_name not in self.iostats:
                self.iostats[ns.bdev_name] = PerformanceStats(ns.bdev_name, self.delay)
            logger.debug('calling namespace_get_io_stats')
            stats = self.call_grpc_api('namespace_get_io_stats',
                                       NVMeoFClient.pb2.namespace_get_io_stats_req(
                                           subsystem_nqn=self.subsystem_nqn,
                                           nsid=ns.nsid))
            logger.debug(stats)

            iostats = self.iostats[ns.bdev_name]
            iostats.read_ops.update(stats.num_read_ops)
            iostats.read_bytes.update(stats.bytes_read)
            iostats.read_secs.update((stats.read_latency_ticks / stats.tick_rate))
            iostats.write_ops.update(stats.num_write_ops)
            iostats.write_bytes.update(stats.bytes_written)
            iostats.write_secs.update((stats.write_latency_ticks / stats.tick_rate))

    def _get_namespaces(self, subsystem_nqn):
        return self.call_grpc_api('list_namespaces', NVMeoFClient.pb2.list_namespaces_req(subsystem=subsystem_nqn))

    def _get_threads_stats(self, client):
        gateway_addr = client.gateway_addr
        logger.debug(f"fetching iostats for {gateway_addr}")
        with self.iostats_lock:
            logger.debug('calling get_thread_stats')
            stats = self.call_grpc_api('get_thread_stats', 
                                       NVMeoFClient.pb2.get_thread_stats_req(), client)
            logger.debug(f'calling get_thread_stats {stats=}')
            
            if gateway_addr not in self.reactor_stats:
                self.reactor_stats[gateway_addr] = {}
            tick_rate = stats.tick_rate
            for thread in stats.threads:
                name = thread.name
                if name not in self.reactor_stats[gateway_addr]:
                    self.reactor_stats[gateway_addr][name] = ReactorStats(thread.name)
                reactor_data = self.reactor_stats[gateway_addr][name]
                reactor_data.busy_secs.update(thread.busy / tick_rate)
                reactor_data.idle_secs.update(thread.idle / tick_rate)
                reactor_data.tick_rate.update(tick_rate)

    def _get_subsystems(self):
        return self.call_grpc_api('list_subsystems', NVMeoFClient.pb2.list_subsystems_req(subsystem_nqn=self.subsystem_nqn))
    
    def _get_gateway(self, client):
        return self.call_grpc_api('get_gateway_info', NVMeoFClient.pb2.get_gateway_info_req(), client)

    def _get_all_subsystems(self):
        return self.call_grpc_api('list_subsystems', NVMeoFClient.pb2.list_subsystems_req())

    # collector methods
    def initialise(self, cmd_handler):
        self.cmd_handler = cmd_handler
        self.server_addr = cmd_handler.server_addr
        self.client = cmd_handler.client

        now = time.time()
        self.delay = (now - self.timestamp)
        self.timestamp = now

        self.gw_info = self._get_gateway(self.client)
        if self.health.rc > 0:
            logger.error(f"Call to {self.server_addr} failed, RC={self.health.rc}, MSG={self.health.msg}")
            self.health.rc = 8
            self.health.msg = f"Unable to connect to {self.server_addr}, pass an available gateway as --server-addr"
            return

        self.log_connection()

    async def collect_cpu_data(self):
        tasks = []
        service_name = self.cmd_handler.gws_service
        group = self.cmd_handler.group
        if service_name:
            gw_conf = NvmeofGatewaysConfig.get_gateways_config()
            if service_name not in gw_conf["gateways"]:
                self.health.rc = 8
                self.health.msg = f'Service {service_name} not found'
                return
            for gw in gw_conf["gateways"][service_name]:
                client = NVMeoFClient(group, gw["service_url"])
                r = asyncio.create_task(asyncio.to_thread(self._get_threads_stats, client))
                tasks.append(r)
        else:
            r = asyncio.create_task(asyncio.to_thread(self._get_threads_stats, self.client))
            tasks.append(r)
        await asyncio.gather(*tasks)
        logger.debug("collect_cpu_data tasks completed")

    async def collect_io_data(self):
        self.subsystem_nqn = self.cmd_handler.subsystem_nqn

        self.subsystems = self._get_all_subsystems()
        if self.subsystems.status > 0:
            logger.error(f"Call to list_subsystems failed, RC={self.subsystems.status}, MSG={self.subsystems.error_message}")
            self.health.rc = 8
            self.health.msg = "Unable to retrieve a list of subsystems"
            return

        if self.total_subsystems == 0:
            self.health.rc = 8
            self.health.msg = 'No subsystems found'
            return

        if self.subsystem_nqn:
            if self.subsystem_nqn not in self.nqn_list:
                logger.error("nqn provided is not present on the gateway")
                self.health.rc = 12
                self.health.msg = "Subsystem NQN provided not found"
                return

        namespace_info = self._get_namespaces(self.subsystem_nqn)
        if not self.ready:
            return

        self.namespaces[self.subsystem_nqn] = namespace_info.namespaces
        logger.debug(f"Subsystem '{self.subsystem_nqn}' has {self.total_namespaces_defined} namespaces")

        tasks = []
        # LBG_MAP = lbg: server_addr
        # io_stats = server_addr: bdev: stats
        # namespaces 
        # for ns in self.namespaces[self.subsystem_nqn]:
        #     t = asyncio.create_task(asyncio.to_thread(self._get_ns_iostats, ns))
        #     tasks.append(t)
        group = self.cmd_handler.group
        if not self.cmd_handler.args.get('server_addr'):
            service_name = self.client.service_name
            gw_conf = NvmeofGatewaysConfig.get_gateways_config()
            if service_name not in gw_conf["gateways"]:
                self.health.rc = 8
                self.health.msg = f'Service {service_name} not found'
                return
            for gw in gw_conf["gateways"][service_name]:
                client = NVMeoFClient(group, gw["service_url"])
                self.lbg_gw = get_lbg_gws_map(service_name)
                logger.info(f"VALLARI_DEBUG: {self.lbg_gw}")
                r = asyncio.create_task(asyncio.to_thread(self._get_namespaces_iostat, client))
                tasks.append(r)
        else:
            r = asyncio.create_task(asyncio.to_thread(self._get_namespaces_iostat, self.client))
            tasks.append(r)

        await asyncio.gather(*tasks)
        logger.debug("collect_io_data tasks completed")

