# -*- coding: utf-8 -*-
# import errno
# import json
from typing import Dict, Tuple
import threading
import time
import logging
import requests
import sys
import grpc
import asyncio
from packaging import version

from mgr_module import CLIReadCommand, HandleCommandResult
from ..controllers.prometheus import Prometheus
from .nvmeof_client import NVMeoFClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class NVMeoFTop:
    text_headers = ['NSID', 'RBD pool/image', 'IOPS', 'r/s', 'rMB/s', 'r_await', 'rareq-sz', 'w/s', 'wMB/s', 'w_await', 'wareq-sz', 'LBGrp', 'QoS']
    text_template = "{:>4}   {:<40}   {:>7}   {:>6}   {:>6}   {:>7}   {:>8}   {:>6}   {:>6}   {:>7}   {:>8}   {:^5}   {:>3}\n"
    ns_description_types = ['rbd', 'vmware']

    def __init__(self, args: dict, client: NVMeoFClient):
        self.client = client
        self.args = args
        self.delay = args.get('delay')
        self.subsystem_nqn = args.get('subsystem')
        self.collector: DataCollector
        self.prometheus_source = args.get('prometheus_source')
        # self.ui_loop: urwid.MainLoop

        # these variables are used to hold the UI objects
        # self.header: Header
        # self.cpustats: CPUStats
        # self.subsystem: SubsystemInfo
        # self.namespaces: NamespaceTable

        # self.cpu_per_core = False
        # self.ui = None
        # self.components = None
        # self.options: Options
        self.sort_key = 'NSID'
        # self.refresh_paused = False
        # self.min_refresh_interval = 1
        self.reverse_sort = False
        self.status_code = 0

        # self.help: HelpInformation
        # self.read_latency_threshold = 0
        # self.write_latency_threshold = 0
        # self.ns_description_ptr = 0

    def to_stdout(self):
        """Dump namespace performance stats to stdout"""
        logger.debug("writing stats to stdout")
        sort_pos = NVMeoFTop.text_headers.index(self.sort_key)
        with self.collector.lock:
            logger.info("VALLARI_DEBUG: collector.loc")
            ns_data = self.collector.get_sorted_namespaces(sort_pos=sort_pos)

        rows = []
        logger.info(f"VALLARI_DEBUG: {ns_data=}")
        if self.args.get('with_timestamp'):
            tstamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.collector.timestamp))
            rows.append(f"{tstamp}\n")
        if not self.args.get('no_headings'):
            rows.append(NVMeoFTop.text_template.format(*NVMeoFTop.text_headers))
        if ns_data:
            # ns_data.sort(key=lambda x: x.nsid, reverse=False)
            for ns in ns_data:
                # row = self.build_ns_row(ns)
                rows.append(NVMeoFTop.text_template.format(*ns))
        else:
            rows.append("<no namespaces defined>\n")

        return ''.join(rows) 

    def batch_mode(self) -> None:
        logger.info(f"Running in batch mode querying {self.args.get('subsystem')}")
        rt_stdout = ""
        try:
            if not self.collector.ready:
                self.status_code = self.collector.health.rc
                return self.collector.health.msg 
                # abort(self.collector.health.rc, self.collector.health.msg)

            # if self.collector.samples_ready:
            rt_stdout += self.to_stdout()
        except KeyboardInterrupt:
            logger.info("nvmeof-top stopped by user")

        rt_stdout += "\n ---- "
        return rt_stdout

    def run(self) -> None:
        self.collector = DataCollector(self)
        logger.info(f"nvmeof-top running with a {self.collector.__class__.__name__} collector")

        self.collector.initialise()
        if not self.collector.ready:
            self.status_code = self.collector.health.rc
            return (self.status_code, f"nvmeof-top has encountered an error: {self.collector.health.msg}")
            # abort(self.collector.health.rc, self.collector.health.msg)

        t = threading.Thread(target=self.collector.run, daemon=True)
        t.start()

        assert self.args.get('subsystem')
        return (self.status_code, self.batch_mode())


@CLIReadCommand('nvmeof top', poll=True)
def nvmeof_top(_, subsystem: str, server_addr: str, group: str, refresh: bool,
            delay: int = 5, count: int = 0, duration: int = 30, 
            with_timestamp: bool = False, no_headings: bool = False,
            disable_prometheus_source: bool = False):
    '''
    NVMe-oF Top Tool
    --subsystem 

    (boolean)
    --with-timestamp 
    --no-headings

    --duration 20 (seconds)
    --delay 20 (seconds)
    --count 10
    '''
    args = {
        'subsystem': subsystem,
        'delay': delay,
        'count': count,
        'duration': duration,
        'with_timestamp': with_timestamp,
        'no_headings': no_headings, 
        # 'skip_version_check': skip_version_check,
        # TODO: temporary args to use in NVMeoFClient
        'server_addr': server_addr,
        'group': group,
        'prometheus_source': not disable_prometheus_source,
    }
    logger.info(f"VALLARI_DEBUG: new loop???")
    # logger.info(f"VALLARI_DEBUG: what is here {self=}")
    if server_addr and group:
        gateway_client = NVMeoFClient(gw_group=group, traddr=server_addr) # TODO: gw_group? traddr?
    elif server_addr:
        gateway_client = NVMeoFClient(traddr=server_addr) # TODO: gw_group? traddr?
    else:
        gateway_client = NVMeoFClient()

    top_tool = NVMeoFTop(args, gateway_client) 
    rc, output = top_tool.run()
    return HandleCommandResult(stdout=output, retval=rc)



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


class ThreadCPUStats:
    def __init__(self, thread_name: str):
        self.name = thread_name

        # values stored by the counter object should be the value / tick_rate
        self.busy = Counter()

        self.busy_rate = 0.0

    def calculate(self, delay: int) -> None:
        self.busy_rate = self.busy.rate(delay)


class Collector:

    def __init__(self, parent):
        self.parent = parent
        self.client = self.parent.client
        self.subsystem_nqn = self.parent.subsystem_nqn
        self.namespaces = []
        self.subsystems = None
        self.cpustats_enabled = False
        self.thread_stats = {}
        self.iostats = {}
        self.iostats_lock = threading.Lock()
        self.lock = threading.Lock()
        self.gw_info = None
        self.timestamp = time.time()
        self.health = Health()
        self.prometheus_source = self.parent.prometheus_source

    # @property
    # def total_iops(self):
    #     return int(sum([stats.total_ops_rate for _, stats in self.iostats.items()]))

    @property
    def nqn_list(self):
        return [get_value(subsys, 'nqn') for subsys in self.subsystems]

    @property
    def total_namespaces(self):
        return sum([get_value(subsys, 'namespace_count')  for subsys in self.subsystems])

    # @property
    # def total_bandwidth(self):
    #     return sum([stats.total_bytes_rate for _, stats in self.iostats.items()])

    @property
    def ready(self) -> bool:
        return self.health.rc == 0

    @property
    def total_namespaces_defined(self) -> int:
        return len(self.namespaces)

    @property
    def total_subsystems(self) -> int:
        return len(self.nqn_list)

    # @property
    # def reactor_cores(self) -> int:
    #     return len(self.thread_stats.keys())

    def get_ns_info(self, ns, ns_type) -> str:
        if ns_type == 'rbd':
            if self.prometheus_source:
                return f'{ns["rbd_name"]}/{ns["pool_name"]}'
            else:
                return f"{ns.rbd_pool_name}/{ns.rbd_image_name}" 
        elif ns_type == 'vmware':
            return f"eui.{get_value(ns, 'uuid').replace('-', '')}"

        logger.error(f"requested an unknown ns type: {ns_type}")
        return 'Unknown'

    def log_connection(self):
        logger.info(f"Connected to {self.parent.args.get('server_addr')}")
        logger.info(f"Gateway has {self.total_subsystems} subsystems defined")

    def get_sorted_namespaces(self, sort_pos: int, ns_type: str = 'rbd'):
        ns_data = []
        logger.info(f"VALLARI_DEBUG: before calculate {self.namespaces=}") 
        for ns in self.namespaces:

            ns_info = self.get_ns_info(ns, ns_type)

            bdev_name = get_value(ns, 'bdev_name')
            nsid = get_value(ns, 'nsid')
            if self.prometheus_source:
                lbg = ns['anagrpid']
            else:
                lbg = ns.load_balancing_group 
            
            logger.info(f"VALLARI_DEBUG: {self.iostats}")

            perf_stats = self.iostats[bdev_name]
            logger.info(f"VALLARI_DEBUG: before calculate {perf_stats=}")
            perf_stats.calculate(self.parent.delay)
            logger.info(f"VALLARI_DEBUG: after calculate {perf_stats=}")

            ns_data.append((
                nsid,
                ns_info,
                int(perf_stats.total_ops_rate),
                int(perf_stats.read_ops_rate),
                f"{bytes_to_MB(perf_stats.read_bytes_rate):3.2f}",
                f"{perf_stats.r_await:3.2f}",
                f"{perf_stats.rareq_sz:4.2f}",
                int(perf_stats.write_ops_rate),
                f"{bytes_to_MB(perf_stats.write_bytes_rate):3.2f}",
                f"{perf_stats.w_await:3.2f}",
                f"{perf_stats.wareq_sz:4.2f}",
                lb_group(lbg),
                self.qos_enabled(ns)
            ))

        ns_data.sort(key=lambda t: t[sort_pos], reverse=self.parent.reverse_sort)
        return ns_data

    # def get_cpu_stats(self) -> Dict[str, ThreadCPUStats]:
    #     for name, stats in self.thread_stats.items():
    #         stats.calculate(self.parent.delay)
    #     return self.thread_stats

    def qos_enabled(self, ns) -> str:
        if self.prometheus_source:
            return "TODO"
        else:
            if (ns.rw_ios_per_second or ns.rw_mbytes_per_second or ns.r_mbytes_per_second or ns.w_mbytes_per_second):
                return 'Yes'
            return 'No'

    def initialise(self):
        raise NotImplementedError(f"class {self.__class__.__name__} is missing initialise() method")

    def run(self):
        raise NotImplementedError(f"class {self.__class__.__name__} is missing run() method")


class DataCollector(Collector):
    event = threading.Event()

    def initialise(self):
        # self.set_gw_info()
        # if self.health.rc > 0:
        #     logger.error('Unable to retrieve gataway information')
        #     return

        # if self.parent.args.get('skip_version_check'):
        #     logger.info('Skipped version check requested. Potential for grpc inconsistency')
        # else:
        #     gw_ok, msg = valid_gw_version(self.gw_info.version)
        #     if not gw_ok:
        #         logger.error(msg)
        #         self.health.rc = 8
        #         self.health.msg = msg
        #         return
        #     else:
        #         logger.debug(f"Gateway version {self.gw_info.version} passed version check")

        self.subsystems = self._get_all_subsystems()
        if self.health.rc != 0:
            return
        # if self.subsystems.status > 0:
        #     logger.error(f"Call to list_subsystems failed, RC={self.subsystems.status}, MSG={self.subsystems.error_message}")
        #     self.health.rc = 8
        #     self.health.msg = "Unable to retrieve a list of subsystems"
        #     return

        if self.total_subsystems == 0:
            self.health.rc = 8
            self.health.msg = 'No subsystems found'
            return

        # check if the nqn exists if it has been provided
        if self.parent.subsystem_nqn:
            if self.parent.subsystem_nqn not in self.nqn_list:
                logger.error("nqn provided is not present on the gateway")
                self.health.rc = 12
                self.health.msg = "Subsystem NQN provided not found"
                return

        self.log_connection()

    def call_grpc_api(self, method_name, request):
        logger.debug(f"calling gprc method {method_name}")
        try:
            func = getattr(self.client.stub, method_name)
            data = func(request)
        except grpc._channel._InactiveRpcError:
            self.health.rc = 8
            self.health.msg = f"RPC endpoint unavailable at {self.client.server}"
            logger.error(f"gprc call to {method_name} failed: {self.health.msg}")
            return None

        self.health.msg = f"{method_name} success"
        logger.debug(f"call to {method_name} successful")
        return data
    
    def call_prometheus_api(self, metric, filters: dict = {}):
        query = metric
        metric_filters = [] # TODO: add instance=""
        for label, value in filters.items():
            metric_filters += [label + '="' + value + '"']
        if metric_filters:
            query += '{' + ','.join(metric_filters) + '}'
        params={'query': query}
        logger.info(f"VALLARI_DEBUG prometheus_params: {params}")
        # url = f"http://localhost:9095/api/v1/query" # TODO: prometheus url and port?
        # resp = requests.get('http://localhost:9095/api/v1/query', params={'query': query})
        try:
            prometheus = Prometheus()
            logger.info(f"VALLARI_DEBUG prometheus: {prometheus}")
            # params['query'] = params.pop('params')
            data = prometheus.prometheus_proxy('GET', '/query', params=params)
            # data = prometheus.get_prometeus_query_data(params=query)
            logger.info(f"VALLARI_DEBUG prometheus_data: {data}")
            return data["result"]
            # resp = requests.get(url)
            # data = resp.json()
        except Exception as exc:
            logger.exception(exc)
            self.health.rc = 8
            self.health.msg = f"Prometheus unavailable!"
            return None
        # if data["status"] == "success":
        #     return data["data"]["result"]

    # def set_gw_info(self):
    #     """Grab the gateway metadata"""
    #     if self.prometheus_source:
    #         pass
    #     else:
    #         self.gw_info = self.call_grpc_api('get_gateway_info', NVMeoFClient.pb2.get_gateway_info_req())
    #         logger.debug(f"VALLARI_DEBUG self.gw_info: {self.gw_info}")

    async def collect_data(self):
        # if not self._sample_count == self._min_sample_count:
        #     self._sample_count += 1
        # namespace_info = self._get_namespaces()
        self.namespaces = self._get_namespaces()
        if not self.ready:
            return

        # TODO namespace_info.status should be 0
        # self.namespaces = namespace_info.namespaces
        logger.debug(f"Subsystem '{self.subsystem_nqn}' has {self.total_namespaces_defined} namespaces")

        tasks = []
        for ns in self.namespaces:
            t = asyncio.create_task(asyncio.to_thread(self._get_ns_iostats, ns))
            tasks.append(t)

        subsystem_task = asyncio.create_task(asyncio.to_thread(self._get_all_subsystems))
        # connections_task = asyncio.create_task(asyncio.to_thread(self._get_connections))
        tasks.extend([subsystem_task])

        await asyncio.gather(*tasks)

        # python 3.11+ code
        # async with asyncio.TaskGroup() as tg:
        #     for ns in self.namespaces:
        #         tg.create_task(asyncio.to_thread(self._get_ns_iostats, ns))

        #     subsystem_task = tg.create_task(asyncio.to_thread(self._get_all_subsystems))
        #     connections_task = tg.create_task(asyncio.to_thread(self._get_connections))

        self.subsystems = subsystem_task.result()
        # self.connection_info = connections_task.result()

        logger.debug("tasks completed")

    def _get_ns_iostats(self, ns):
        logger.debug(f"fetching iostats for namespace {get_value(ns, 'nsid')}")
        with self.iostats_lock:
            logger.debug('iostats lock acquired')
            if self.prometheus_source:
                if ns['bdev_name'] not in self.iostats:
                    self.iostats[ns['bdev_name']] = PerformanceStats(ns['bdev_name'], self.parent.delay)
                logger.debug('calling prometheus ceph_nvmeof_bdev_* metrics')
                metrics = {
                    'read_ops': 'ceph_nvmeof_bdev_reads_completed_total',
                    'write_ops': 'ceph_nvmeof_bdev_writes_completed_total',
                    'read_bytes': 'ceph_nvmeof_bdev_read_bytes_total',
                    'write_bytes': 'ceph_nvmeof_bdev_written_bytes_total',
                    'read_secs': 'ceph_bdev_read_seconds_total',
                    'write_secs': 'ceph_bdev_write_seconds_total',
                }
                iostats = self.iostats[ns['bdev_name']]
                for iostat_attr, metric in metrics.items():
                    data = self.call_prometheus_api(metric, {"bdev_name": ns['bdev_name']})
                    if data:
                        value = float(data[0]["value"][1])
                        getattr(iostats, iostat_attr).update(value)
                    else:
                        logger.info('VALLARI_DEBUG no ns_iostat data!')
            else:
                if ns.bdev_name not in self.iostats:
                    self.iostats[ns.bdev_name] = PerformanceStats(ns.bdev_name, self.parent.delay)
                logger.debug('calling namespace_get_io_stats')
                stats = self.call_grpc_api('namespace_get_io_stats', NVMeoFClient.pb2.namespace_get_io_stats_req(
                                            subsystem_nqn=self.parent.subsystem_nqn,
                                            nsid=ns.nsid))
                iostats = self.iostats[ns.bdev_name]
                iostats.read_ops.update(stats.num_read_ops)
                iostats.read_bytes.update(stats.bytes_read)
                iostats.read_secs.update((stats.read_latency_ticks / stats.tick_rate))
                iostats.write_ops.update(stats.num_write_ops)
                iostats.write_bytes.update(stats.bytes_written)
                iostats.write_secs.update((stats.write_latency_ticks / stats.tick_rate))

    def _get_namespaces(self):
        if self.prometheus_source:
            result = []
            namespaces = self.call_prometheus_api(
                'ceph_nvmeof_subsystem_namespace_metadata{nqn="' + self.subsystem_nqn +
                '"}==on(instance, bdev_name)group_left(pool_name, rbd_name)ceph_nvmeof_bdev_metadata'
            )
            if not namespaces:
                logger.info('VALLARI_DEBUG no namespaces!')
                return []
            for ns in namespaces:
                # if ns["value"][1] == "1":
                result += [ns["metric"]]
            return result
        else:
            return self.call_grpc_api('list_namespaces', NVMeoFClient.pb2.list_namespaces_req(subsystem=self.subsystem_nqn)).namespaces

    # def _get_subsystems(self):
    #     if self.prometheus_source:
    #         result = []
    #         subsystems = self.call_prometheus_api('ceph_nvmeof_subsystem_metadata')
    #         for subsys in subsystems:
    #             # if subsys["value"][1] == "1":
    #             result += subsys["metric"]
    #         return result
    #     else:
    #         return self.call_grpc_api('list_subsystems', NVMeoFClient.pb2.list_subsystems_req(subsystem_nqn=self.subsystem_nqn))

    def _get_all_subsystems(self):
        if self.prometheus_source:
            result = []
            subsystems = self.call_prometheus_api('ceph_nvmeof_subsystem_namespace_count')
            if not subsystems:
                logger.info('VALLARI_DEBUG no subsystems!')
                return []
            for subsys in subsystems:
                # if subsys["value"][1] == "1":
                subsystem_data = subsys["metric"]
                subsystem_data["namespace_count"] = subsys["value"][1]
                result += [subsystem_data]
            return result
        else:
            resp = self.call_grpc_api('list_subsystems', NVMeoFClient.pb2.list_subsystems_req())
            if resp.status > 0:
                logger.error(f"Call to list_subsystems failed, RC={resp.status}, MSG={resp.error_message}")
                self.health.rc = 8
                self.health.msg = "Unable to retrieve a list of subsystems"
                return
            return resp.subsystems

    # def _get_connections(self):
    #     return self.call_grpc_api('list_connections', NVMeoFClient.pb2.list_connections_req(subsystem=self.subsystem_nqn))

    # def get_cpu_stats(self):
    #     raise NotImplementedError

    async def start(self):
        logger.info("VALLARI_DEBUG: collector.start")
        # while not self.event.is_set():
        for i in range(2):
            start = time.time()
            await self.collect_data()
            logger.info(f"data collection took (round {i+1}): {(time.time() - start):3.3f} secs")

            if not self.ready:
                logger.error("Error encounted during data collection, terminating async loop")
                return
            self.timestamp = time.time()
            logger.debug(f"nqn_list is : {self.nqn_list}")
            if i == 0:
                logger.info("VALLARI_DEBUG: going to sleep")
                await asyncio.sleep(self.parent.delay)  
                logger.info("VALLARI_DEBUG: slept!")

    def run(self):
        logger.info("VALLARI_DEBUG: DataCollector.run")
        if self.ready:
            with self.lock:
                logger.info("VALLARI_DEBUG: collector.start.locked")
                asyncio.run(self.start())
                logger.info("VALLARI_DEBUG: collector.start.locked sleep over")

    # async def start(self):
    #     # while not self.event.is_set():
    #     with self.lock:
    #         start = time.time()
    #         await self.collect_data()
    #         logger.info(f"data collection took: {(time.time() - start):3.3f} secs")

    #         if not self.ready:
    #             logger.error("Error encounted during data collection, terminating async loop")
    #             return
    #         self.timestamp = time.time()
    #         # logger.debug(f"event loop waiting for {self.parent.delay}s")
    #         logger.debug(f"nqn_list is : {self.nqn_list}")
    #         time.sleep(self.parent.delay)

    # def run(self):
    #     if self.ready:
    #         asyncio.run(self.start())


# utils

def abort(rc: int, msg: str):
    logger.critical(f"nvmeof-top has encountered an error: {msg}")
    # print(msg)
    # sys.exit(rc)

def lb_group(grp_id: int):
    """Provide a meaningful default when load-balancing is not in use"""
    return "N/A" if grp_id == 0 else f"{grp_id}"


def bytes_to_MB(bytes: int, si: int = 1024):
    """Simple conversion of bytes to with MiB or MB"""
    return (bytes / si) / si


def valid_gw_version(gw_version_str: str) -> Tuple[bool, str]:
    min_version = version.Version('1.0.0')
    try:
        gw_version = version.Version(gw_version_str)
    except version.InvalidVersion:
        return False, 'Missing or invalid version - unable to check compatibility'
    if gw_version >= min_version:
        return True, 'OK'
    return False, f"Incompatible gateway version. nvmeof-top requires {min_version} or above"


def get_value(obj, attr):
    if isinstance(obj, dict):
        return obj[attr]
    else:
        return getattr(obj, attr)