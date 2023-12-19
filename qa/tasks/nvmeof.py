import logging
import json
from textwrap import dedent
from io import StringIO
from teuthology.task import Task
from teuthology.orchestra import run
from teuthology import misc as teuthology
from teuthology.exceptions import ConfigError
from tasks.util import get_remote_for_role
from tasks.cephadm import _shell
from tempfile import NamedTemporaryFile
from teuthology.parallel import parallel
from teuthology.packaging import install_package, remove_package

log = logging.getLogger(__name__)

conf_file = '/etc/ceph/nvmeof.env'
SPDK_CONTROLLER = "SPDK bdev Controller"

class Nvmeof(Task):
    """
    Setup nvmeof gateway on client and then share gateway config to target host.

        - nvmeof:
            client: client.0
            gateway_image: default
            rbd:
                pool_name: mypool
                image_name: myimage
                rbd_size: 1024 # MBs
            gateway_config:
                source: host.a 
                target: client.2
                vars:
                    cli_image: latest
                    
    """

    def setup(self):
        super(Nvmeof, self).setup()
        try:
            self.client = self.config['client']
        except KeyError:
            raise ConfigError('nvmeof requires a client to connect with')

        self.cluster_name, type_, self.client_id = teuthology.split_role(self.client)
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
        self.gateway_image = self.config.get('gateway_image', 'default')

        rbd_config = self.config.get('rbd', {})
        self.poolname = rbd_config.get('pool_name', 'mypool')
        self.rbd_image_name = rbd_config.get('image_name', 'myimage')
        self.rbd_size = rbd_config.get('rbd_size', 1024*8) # (1024*8) MBs = 2GBs

        gateway_config = self.config.get('gateway_config', {})
        conf_vars = gateway_config.get('vars', {})
        self.cli_image = conf_vars.get('cli_image', 'latest')
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
                         if teuthology.is_type('nvmeof', self.cluster_name)(r)]:
                c_, _, id_ = teuthology.split_role(role)
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
            gateway_name = daemon.name()
        conf_data = dedent(f"""
            NVMEOF_GATEWAY_IP_ADDRESS={ip_address}
            NVMEOF_GATEWAY_NAME={gateway_name}
            NVMEOF_CLI_IMAGE="quay.io/ceph/nvmeof-cli:{self.cli_image}"
            NVMEOF_POOL={self.poolname}
            NVMEOF_RBD_IMAGE={self.rbd_image_name}
            NVMEOF_RBD_SIZE={self.rbd_size}
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
        log.info(f"[nvmeof]: nvme discover -t tcp -a $IP -s {DISCOVERY_PORT}")
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "discover", "-t", "tcp", 
            "-a", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), "-s", DISCOVERY_PORT
        ])
        expected_discovery_stdout = "subtype: nvme subsystem"
        assert expected_discovery_stdout in stdout, f"Expected stdout: {expected_discovery_stdout}, but got: {stdout}"
        log.info(f"[nvmeof]: run_discovery successful!")

    def run_connect(self):
        log.info(f"[nvmeof]: nvme connect -t tcp --traddr $NVMEOF_GATEWAY_IP_ADDRESS -s $NVMEOF_PORT -n $NVMEOF_NQN")
        self._run_cmd(args=[
            "sudo", "nvme", "connect", "-t", "tcp", 
            "--traddr", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), 
            "-s",  run.Raw('$NVMEOF_PORT'), 
            "-n",  run.Raw('$NVMEOF_NQN')
        ])
        log.info(f"[nvmeof]: nvme list")
        _, stdout, _ = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = SPDK_CONTROLLER
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        log.info(f"[nvmeof]: run_connect successful!")

    def run_disconnect_all(self):
        log.info(f"[nvmeof]: nvme disconnect-all")
        self._run_cmd(args=["sudo", "nvme", "disconnect-all"])
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "list"
        ])
        removed_controller = SPDK_CONTROLLER
        assert removed_controller not in stdout, f"Expected stdout: no {removed_controller}, but got: {stdout}"
        log.info(f"[nvmeof]: run_disconnect_all successful!")

    def run_connect_all(self):
        log.info(f"[nvmeof]: nvme connect-all --traddr=$NVMEOF_GATEWAY_IP_ADDRESS --transport=tcp")
        self._run_cmd(args=[
            "sudo", "nvme", "connect-all", run.Raw('--traddr=$NVMEOF_GATEWAY_IP_ADDRESS'), "--transport=tcp", 
        ])
        _, stdout, _ = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = SPDK_CONTROLLER
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        log.info(f"[nvmeof]: run_connect_all successful!")

    def run_list_subsys(self, expected_count):
        log.info(f"[nvmeof]: nvme list-subsys --output-format=json")
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "list-subsys", "--output-format=json", 
        ])
        subsys_output = json.loads(stdout)
        subsys_list = subsys_output[0]["Subsystems"]
        assert expected_count == len(subsys_list), f"Expected subsystems: {expected_count}, but got: {len(subsys_list)}"
        log.info(f"[nvmeof]: run_list_subsys successful!")


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
        cmd.run_list_subsys(expected_count=2)
        cmd.run_disconnect_all()
        cmd.run_list_subsys(expected_count=1)
        cmd.run_connect_all()
        self.test_device_size(cmd)

    def test_device_size(self, cmd):
        log.info(f"[nvmeof]: testing device size")
        nvme_model = SPDK_CONTROLLER
        _, nvme_size_bytes, _ = cmd._run_cmd(args=[
            "sudo", "nvme", "list", "--output-format=json", run.Raw("|"),
            "jq", "-r", f'.Devices | .[] | select(.ModelNumber == "{nvme_model}") | .PhysicalSize',
        ])
        _, rbd_image_size_bytes, _ = cmd._run_cmd(args=[
            'rbd', 'info', '--format=json', run.Raw('$NVMEOF_POOL/$NVMEOF_RBD_IMAGE'), run.Raw("|"),
            "jq", "-r", '.size',
        ])
        assert rbd_image_size_bytes == nvme_size_bytes, f"Expected RBD Image Size: {rbd_image_size_bytes}, nvme size: {nvme_size_bytes}"
        log.info(f"[nvmeof]: test_device_size successful!")


class FIO_Test(Nvmeof):
    """

    IO tests for nvmeof

        - nvmeof.fio_test:
            client: client.2
            conf:
                runtime: 600
    """
    name = 'nvmeof.fio_test'

    def begin(self):
        cmd = NvmeCommands(self.remote)
        cmd.run_connect_all()
        rbd_test_dir = teuthology.get_testdir(self.ctx) + "/nvmeof_fio_test"
        log.info(self.config.get('conf'))
        self.run_fio(self.config.get('conf'), rbd_test_dir)
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
        config['ioengine'] = config.get('ioengine', 'libaio')
        config['bsrange'] = config.get('bsrange', '4k-64k')
        config['numjobs'] = config.get('numjobs', '1')
        config['size'] = config.get('size', '1G')
        config['runtime'] = config.get('runtime', '600') # 10 mins
        config['rw'] = config.get('rw', 'randrw')
        config['filename'] = self._get_device_path()
        return config


    def write_fio_config(self, config):
        """
        Default:
        fio --name=nvmeof-fio-test --ioengine=libaio --filename /dev/nvme1n1 --rw=randrw /
            --bsrange=4k-64k --size=1G --numjobs=4 --time_based --runtime=600 --verify=md5 --verify_fatal=1
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
        fio_config.write('filename={rbd_dev}\n'.format(rbd_dev=config['filename']))
        fio_config.write('verify=md5\n')
        fio_config.write('verify_fatal=1\n')
        fio_config.close()
        self.remote.put_file(fio_config.name,fio_config.name)
        return fio_config

    def run_fio(self, config, rbd_test_dir):
        config = self._set_config_defaults(config)
        fio_version ='3.35'
        host_name=self.remote.shortname
        ioengine_pkg = None
        try:
            log.info("[nvmeof]: Running nvmeof fio test on {host_name}".format(host_name=host_name))
            if config['ioengine'] == 'libaio':
                system_type = teuthology.get_system_type(self.remote)
                ioengine_pkg = 'libaio-devel' if system_type == 'rpm' else 'libaio-dev'
                log.info("[nvmeof]: Installing {ioengine_pkg} on {system_type}".format(ioengine_pkg=ioengine_pkg, system_type=system_type))
                install_package(ioengine_pkg, self.remote)
            fio_config = self.write_fio_config(config)

            fio = "https://github.com/axboe/fio/archive/fio-" + fio_version + ".tar.gz"
            self.remote.run(args=['mkdir', run.Raw(rbd_test_dir),])
            self.remote.run(args=['cd' , run.Raw(rbd_test_dir),
                             run.Raw(';'), 'wget', fio, run.Raw(';'), run.Raw('tar -xvf fio*tar.gz'), run.Raw(';'),
                             run.Raw('cd fio-fio*'), run.Raw(';'), './configure', run.Raw(';'), 'make'])
            self.remote.run(args=[run.Raw('{tdir}/fio-fio-{v}/fio --showcmd {f}'.format(tdir=rbd_test_dir,v=fio_version,f=fio_config.name))])
            self.remote.run(args=['sudo', run.Raw('{tdir}/fio-fio-{v}/fio {f}'.format(tdir=rbd_test_dir,v=fio_version,f=fio_config.name))])
        finally:
            self.remote.run(args=['rm','-rf', run.Raw(rbd_test_dir)])
            if ioengine_pkg:
                remove_package(ioengine_pkg, self.remote)


task = Nvmeof
basic_tests = BasicTests
fio_test = FIO_Test
