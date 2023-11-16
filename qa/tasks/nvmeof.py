import logging
import json
from textwrap import dedent
from io import StringIO
from teuthology.task import Task
from teuthology.orchestra import run
from teuthology import misc
from teuthology.exceptions import ConfigError
from tasks.util import get_remote_for_role
from tasks.cephadm import _shell
from tempfile import NamedTemporaryFile
from concurrent import futures
from teuthology.packaging import install_package, remove_package

log = logging.getLogger(__name__)

conf_file = '/etc/ceph/nvmeof.env'
SPDK_CONTROLLER = "SPDK bdev Controller"

class Nvmeof(Task):
    """
    Setup nvmeof gateway on client and then share gateway config to target host.

        - nvmeof:
            client: client.0
            version: default
            rbd:
                pool_name: mypool
                image_name: myimage
                rbd_size: 1024
            gateway_config:
                source: host.a 
                target: client.2
                vars:
                    cli_version: latest
                    
    """

    def setup(self):
        super(Nvmeof, self).setup()
        try:
            self.client = self.config['client']
        except KeyError:
            raise ConfigError('nvmeof requires a client to connect with')

        self.cluster_name, type_, self.client_id = misc.split_role(self.client)
        if type_ != 'client':
            msg = 'client role ({0}) must be a client'.format(self.client)
            raise ConfigError(msg)
        self.remote = get_remote_for_role(self.ctx, self.client)

    def begin(self):
        super(Nvmeof, self).begin()
        self._set_defaults()
        self.deploy_nvmeof()
        self.set_gateway_cfg()

    def _set_defaults(self):
        self.gateway_image = self.config.get('version', 'default')

        rbd_config = self.config.get('rbd', {})
        self.poolname = rbd_config.get('pool_name', 'mypool')
        self.rbd_image_name = rbd_config.get('image_name', 'myimage')
        self.rbd_size = rbd_config.get('rbd_size', 1024*8)

        gateway_config = self.config.get('gateway_config', {})
        conf_vars = gateway_config.get('vars', {})
        self.cli_image = conf_vars.get('cli_version', 'latest')
        self.bdev = conf_vars.get('bdev', 'mybdev')
        self.serial = conf_vars.get('serial', 'SPDK00000000000001')
        self.nqn = conf_vars.get('nqn', 'nqn.2016-06.io.spdk:cnode1')
        self.port = conf_vars.get('port', '4420')
        self.srport = conf_vars.get('srport', '5500')

    def deploy_nvmeof(self):
        """
        Deploy nvmeof gateway.
        """
        log.info('[nvmeof]: deploying nvmeof gateway...')
        if not hasattr(self.ctx, 'ceph'):
            self.ctx.ceph = {}
        fsid = self.ctx.ceph[self.cluster_name].fsid

        nodes = []
        daemons = {}

        for remote, roles in self.ctx.cluster.remotes.items():
            for role in [r for r in roles
                         if misc.is_type('nvmeof', self.cluster_name)(r)]:
                c_, _, id_ = misc.split_role(role)
                log.info('Adding %s on %s' % (role, remote.shortname))
                nodes.append(remote.shortname + '=' + id_)
                daemons[role] = (remote, id_)

        if nodes:
            image = self.gateway_image
            if (image != "default"):
                log.info(f'[nvmeof]: ceph config set mgr mgr/cephadm/container_image_nvmeof quay.io/ceph/nvmeof:{image}')
                _shell(self.ctx, self.cluster_name, self.remote, [
                    'ceph', 'config', 'set', 'mgr', 
                    'mgr/cephadm/container_image_nvmeof',
                    f'quay.io/ceph/nvmeof:{image}'
                ])

            poolname = self.poolname
            imagename = self.rbd_image_name

            log.info(f'[nvmeof]: ceph osd pool create {poolname}')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'ceph', 'osd', 'pool', 'create', poolname
            ])

            log.info(f'[nvmeof]: rbd pool init {poolname}')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'rbd', 'pool', 'init', poolname
            ])

            log.info(f'[nvmeof]: ceph orch apply nvmeof {poolname}')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'ceph', 'orch', 'apply', 'nvmeof', poolname, 
                '--placement', str(len(nodes)) + ';' + ';'.join(nodes)
            ])

            log.info(f'[nvmeof]: rbd create {poolname}/{imagename} --size {self.rbd_size}')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'rbd', 'create', f'{poolname}/{imagename}', '--size', f'{self.rbd_size}'
            ])

        for role, i in daemons.items():
            remote, id_ = i
            self.ctx.daemons.register_daemon(
                remote, 'nvmeof', id_,
                cluster=self.cluster_name,
                fsid=fsid,
                logger=log.getChild(role),
                wait=False,
                started=True,
            )
        log.info("[nvmeof]: executed deploy_nvmeof successfully!")
        
    def set_gateway_cfg(self):
        log.info('[nvmeof]: running set_gateway_cfg...')
        gateway_config = self.config.get('gateway_config', {})
        source_host = gateway_config.get('source')
        target_host = gateway_config.get('target')
        if not (source_host and target_host):
            raise ConfigError('gateway_config requires "source" and "target"')
        remote = list(self.ctx.cluster.only(source_host).remotes.keys())[0]
        ip_address = remote.ip_address
        gateway_name = ""
        nvmeof_daemons = self.ctx.daemons.iter_daemons_of_role('nvmeof', cluster=self.cluster_name)
        for daemon in nvmeof_daemons:
            if ip_address == daemon.remote.ip_address:
                gateway_name = daemon.name()
        conf_data = dedent(f"""
            NVMEOF_GATEWAY_IP_ADDRESS={ip_address}
            NVMEOF_GATEWAY_NAME={gateway_name}
            NVMEOF_CLI_IMAGE="quay.io/ceph/nvmeof-cli:{self.cli_image}"
            NVMEOF_BDEV={self.bdev}
            NVMEOF_SERIAL={self.serial}
            NVMEOF_NQN={self.nqn}
            NVMEOF_PORT={self.port}
            NVMEOF_SRPORT={self.srport}
            """)
        target_remote = list(self.ctx.cluster.only(target_host).remotes.keys())[0]
        target_remote.write_file(
            path=conf_file,
            data=conf_data,
            sudo=True
        )
        log.info("[nvmeof]: executed set_gateway_cfg successfully!")


class NvmeCommands():
    def __init__(self, remote) -> None:
        self.remote = remote

    def _run_cmd(self, args):
        r = self.remote.run(args=['source', conf_file, run.Raw('&&')] + args, 
                            stdout=StringIO(), stderr=StringIO())
        stdout = r.stdout.getvalue()
        stderr = r.stderr.getvalue()
        return r, stdout, stderr

    def run_discovery(self):
        DISCOVERY_PORT="8009"
        log.info(f"[nvmeof]: nvme discover -t tcp -a $NVMEOF_GATEWAY_IP_ADDRESS -s {DISCOVERY_PORT}")
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "discover", "-t", "tcp", 
            "-a", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), "-s", DISCOVERY_PORT
        ])
        expected_discovery_stdout = "subtype: nvme subsystem"
        assert expected_discovery_stdout in stdout, f"Expected stdout: {expected_discovery_stdout}, but got: {stdout}"
        log.info("[nvmeof]: run_discovery successful!")

    def run_connect(self):
        log.info("[nvmeof]: nvme connect -t tcp --traddr $NVMEOF_GATEWAY_IP_ADDRESS -s $NVMEOF_PORT -n $NVMEOF_NQN")
        self._run_cmd(args=[
            "sudo", "nvme", "connect", "-t", "tcp", 
            "--traddr", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), 
            "-s",  run.Raw('$NVMEOF_PORT'), 
            "-n",  run.Raw('$NVMEOF_NQN')
        ])
        log.info("[nvmeof]: nvme list")
        _, stdout, _ = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = SPDK_CONTROLLER
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        log.info("[nvmeof]: run_connect successful!")

    def run_disconnect_all(self):
        log.info("[nvmeof]: nvme disconnect-all")
        self._run_cmd(args=["sudo", "nvme", "disconnect-all"])
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "list"
        ])
        removed_controller = SPDK_CONTROLLER
        assert removed_controller not in stdout, f"Expected stdout: no {removed_controller}, but got: {stdout}"
        log.info("[nvmeof]: run_disconnect_all successful!")

    def run_connect_all(self):
        log.info("[nvmeof]: nvme connect-all --traddr=$NVMEOF_GATEWAY_IP_ADDRESS --transport=tcp")
        self._run_cmd(args=[
            "sudo", "nvme", "connect-all", run.Raw('--traddr=$NVMEOF_GATEWAY_IP_ADDRESS'), "--transport=tcp", 
        ])
        _, stdout, _ = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = SPDK_CONTROLLER
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        log.info("[nvmeof]: run_connect_all successful!")

    def run_list_subsys(self, expected_count):
        log.info("[nvmeof]: nvme list-subsys --output-format=json")
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "list-subsys", "--output-format=json", 
        ])
        subsys_output = json.loads(stdout)
        subsys_list = subsys_output[0]["Subsystems"]
        tcp_type_paths = []
        for subsys in subsys_list:
            for path in subsys['Paths']:
                if path['Transport'] == 'tcp':
                    tcp_type_paths += [path]
        assert expected_count == len(tcp_type_paths), f"Expected subsystem paths: {expected_count}, but got: {len(tcp_type_paths)}"
        log.info("[nvmeof]: run_list_subsys successful!")


class BasicTests(Nvmeof):
    """
    Basic nvmeof tests in which following commands are tested:
    1. discovery 
    2. connect-all
    3. connect
    4. disconnect-all
    5. list-subsys

        - nvmeof.basic_tests:
            client: client.1
    """
    name = 'nvmeof.basic_tests'

    def setup(self):
        super(BasicTests, self).setup()

    def begin(self):
        cmd = NvmeCommands(self.remote)
        cmd.run_discovery()
        cmd.run_connect()
        cmd.run_list_subsys(expected_count=1)
        cmd.run_disconnect_all()
        cmd.run_list_subsys(expected_count=0)
        cmd.run_connect_all()
        gateways = self.ctx.daemons.iter_daemons_of_role('nvmeof', cluster=self.cluster_name)
        cmd.run_list_subsys(expected_count=len(gateways))
        self.test_device_size(cmd)

    def test_device_size(self, cmd):
        env = self.config.get('env', {})
        if ("RBD_POOL" not in env) or ("RBD_IMAGE" not in env):
            log.info("[nvmeof]: skipping device size test - pool name and image unkown!")
            return
        pool, image = env["RBD_POOL"], env["RBD_IMAGE"]
        log.info("[nvmeof]: testing device size")
        nvme_model = SPDK_CONTROLLER
        _, nvme_size_bytes, _ = cmd._run_cmd(args=[
            "sudo", "nvme", "list", "--output-format=json", run.Raw("|"),
            "jq", "-r", f'.Devices | .[] | select(.ModelNumber == "{nvme_model}") | .PhysicalSize',
        ])
        _, rbd_image_size_bytes, _ = cmd._run_cmd(args=[
            'rbd', 'info', '--format=json', f'{pool}/{image}', run.Raw("|"),
            "jq", "-r", '.size',
        ])
        assert rbd_image_size_bytes == nvme_size_bytes, f"Expected RBD Image Size: {rbd_image_size_bytes}, nvme size: {nvme_size_bytes}"
        log.info("[nvmeof]: test_device_size successful!")


class FIO_Test(Nvmeof):
    """

    IO tests for nvmeof

        - nvmeof.fio_test:
            client: client.2
            iostat_interval: 10 #sec
            conf:
                runtime: 600
    """
    name = 'nvmeof.fio_test'

    def begin(self):
        cmd = NvmeCommands(self.remote)
        cmd.run_connect_all()
        self.run_fio(self.config.get('conf'))
        cmd.run_disconnect_all()

    def _get_device_path(self):
        log.info("[nvmeof]: getting drive path..")
        nvme_model = SPDK_CONTROLLER
        r = self.remote.run(args=[
            "sudo", "nvme", "list", "--output-format=json", run.Raw("|"),
            "jq", "-r", f'.Devices | .[] | select(.ModelNumber == "{nvme_model}") | .DevicePath',
        ], stdout=StringIO(), stderr=StringIO())
        nvme_device = r.stdout.getvalue().strip()
        if nvme_device:
            return nvme_device

    def _set_config_defaults(self, config):
        config['ioengine'] = config.get('ioengine', 'sync')
        config['bsrange'] = config.get('bsrange', '4k-64k')
        config['numjobs'] = config.get('numjobs', '1')
        config['size'] = config.get('size', '1G')
        config['runtime'] = config.get('runtime', '600') # 10 mins
        config['rw'] = config.get('rw', 'randrw')
        config['drive'] = self._get_device_path()
        return config

    def write_fio_config(self, config):
        """
        Default:
        fio --name=nvmeof-fio-test --ioengine=sync --filename /dev/nvme1n1 --rw=randrw /
            --bsrange=4k-64k --size=1G --numjobs=1 --time_based --runtime=600 --verify=md5 --verify_fatal=1
        """
        fio_config=NamedTemporaryFile(mode='w', prefix='fio_nvmeof_', dir='/tmp/', delete=False)
        fio_config.write('[nvmeof-fio-test]\n')
        fio_config.write('ioengine={ioe}\n'.format(ioe=config['ioengine']))
        fio_config.write('bsrange={bsrange}\n'.format(bsrange=config['bsrange']))
        fio_config.write('numjobs={numjobs}\n'.format(numjobs=config['numjobs']))
        fio_config.write('size={size}\n'.format(size=config['size']))
        fio_config.write('time_based=1\n')
        fio_config.write('runtime={runtime}\n'.format(runtime=config['runtime']))
        fio_config.write('rw={rw}\n'.format(rw=config['rw']))
        fio_config.write('filename={nvme_device}\n'.format(nvme_device=config['drive']))
        fio_config.write('verify=md5\n')
        fio_config.write('verify_fatal=1\n')
        fio_config.close()
        self.remote.put_file(fio_config.name,fio_config.name)
        return fio_config

    def run_fio(self, config):
        ioengine_pkg = None
        config = self._set_config_defaults(config)
        fio_config = self.write_fio_config(config)
        try:
            log.info(f"[nvmeof]: Installing dependencies for fio test on {self.remote.shortname}")
            if config['ioengine'] == 'libaio':
                system_type = misc.get_system_type(self.remote)
                ioengine_pkg = 'libaio-devel' if system_type == 'rpm' else 'libaio-dev'
                log.info(f"[nvmeof]: Installing {ioengine_pkg} on {system_type}")
                install_package(ioengine_pkg, self.remote)
            install_package("fio", self.remote)
            self.remote.run(args=['fio', '--showcmd', fio_config.name])
            fio_cmd = ['sudo', 'fio', fio_config.name]
            if self.config.get('iostat_interval'):
                iostat_interval = self.config.get('iostat_interval')
                iostat_count = int(config['runtime']) // int(iostat_interval) + 10
                iostat_cmd = ['sudo', 'iostat', '-d', '-p', config['drive'], str(iostat_interval), str(iostat_count), '-h']
                install_package("sysstat", self.remote)
                log.info("[nvmeof]: Running fio test and iostat in parallel..")
                with futures.ThreadPoolExecutor(max_workers=2) as executor:
                    executor.submit(self.remote.run, args=iostat_cmd)
                    executor.submit(self.remote.run, args=fio_cmd)
            else:
                log.info("[nvmeof]: Running fio test..")
                self.remote.run(args=fio_cmd)
        finally:
            remove_package("fio", self.remote)
            if ioengine_pkg:
                remove_package(ioengine_pkg, self.remote)


task = Nvmeof
basic_tests = BasicTests
fio_test = FIO_Test
