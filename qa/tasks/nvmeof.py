import logging
from textwrap import dedent
from io import StringIO
from teuthology.task import Task
from teuthology.orchestra import run
from teuthology import misc as teuthology
from teuthology.exceptions import ConfigError
from tasks.util import get_remote_for_role
from tasks.cephadm import _shell

log = logging.getLogger(__name__)

conf_file = '/etc/ceph/nvmeof.env'

class Nvmeof(Task):
    """
    Setup nvmeof gateway on client and then share gateway config to target host.

        - nvmeof:
            image: default
            client: client.0
            gateway_config:
                source: host.a 
                target: client.1
                vars:
                    pool_name: mypool
                    image_name: myimage
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
        self.nvmeof_image = self.config.get('image', 'default')
        gateway_config = self.config.get('gateway_config', {})
        extra_conf = gateway_config.get('vars', {})
        self.poolname = extra_conf.get('pool_name', 'mypool')
        self.imagename = extra_conf.get('image_name', 'myimage')
        self.bdev = extra_conf.get('bdev', 'mybdev')
        self.serial = extra_conf.get('serial', 'SPDK00000000000001')
        self.nqn = extra_conf.get('nqn', 'nqn.2016-06.io.spdk:cnode1')
        self.port = extra_conf.get('port', '4420')
        self.srport = extra_conf.get('srport', '5500')

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
            image = self.nvmeof_image
            if (image != "default"):
                log.info(f'[nvmeof]: ceph config set mgr mgr/cephadm/container_image_nvmeof quay.io/ceph/nvmeof:{image}')
                _shell(self.ctx, self.cluster_name, self.remote, [
                    'ceph', 'config', 'set', 'mgr', 
                    'mgr/cephadm/container_image_nvmeof',
                    f'quay.io/ceph/nvmeof:{image}'
                ])

            poolname = self.poolname
            imagename = self.imagename

            log.info('[nvmeof]: ceph osd pool create mypool')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'ceph', 'osd', 'pool', 'create', poolname
            ])

            log.info('[nvmeof]: rbd pool init -p mypool')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'rbd', 'pool', 'init', poolname
            ])

            log.info('[nvmeof]: ceph orch apply nvmeof mypool')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'ceph', 'orch', 'apply', 'nvmeof', poolname, 
                '--placement', str(len(nodes)) + ';' + ';'.join(nodes)
            ])

            log.info('[nvmeof]: rbd create mypool/myimage --size 8Gi')
            _shell(self.ctx, self.cluster_name, self.remote, [
                'rbd', 'create', f'{poolname}/{imagename}', '--size', '8Gi'
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
            NVMEOF_CLI_IMAGE="quay.io/ceph/nvmeof-cli:latest"
            NVMEOF_POOL={self.poolname}
            NVMEOF_RBD_IMAGE={self.imagename}
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


class BasicTests(Nvmeof):
    """
    Basic nvmeof tests in which following commands are tested:
    1. discovery 
    2. connect-all
    3. connect
    4. disconnect-all

        - nvmeof.basic_tests:
            client: client.1
    """
    name = 'nvmeof.basic_tests'

    def setup(self):
        super(BasicTests, self).setup()
    
    def _run_cmd(self, args):
        r = self.remote.run(args=['source', conf_file, run.Raw('&&')] + args, 
                            stdout=StringIO(), stderr=StringIO())
        stdout = r.stdout.getvalue()
        stderr = r.stderr.getvalue()
        return r, stdout, stderr

    def begin(self):
        self.test_nvmeof_discovery()
        self.test_nvmeof_connect()
        self.test_nvmeof_disconnect_all()
        self.test_nvmeof_connect_all()

    def test_nvmeof_discovery(self):
        DISCOVERY_PORT="8009"
        log.info(f"[nvmeof test]: nvme discover -t tcp -a $IP -s {DISCOVERY_PORT}")
        _, stdout, stderr = self._run_cmd(args=[
            "sudo", "nvme", "discover", "-t", "tcp", 
            "-a", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), "-s", DISCOVERY_PORT
        ])
        expected_discovery_stdout = "subtype: nvme subsystem"
        expected_discovery_stderr = ""
        assert expected_discovery_stdout in stdout, f"Expected stdout: {expected_discovery_stdout}, but got: {stdout}"
        assert expected_discovery_stderr == stderr, f"Expected stderr: {expected_discovery_stderr}, but got: {stderr}"
        log.info(f"[nvmeof test]: test_nvmeof_discovery successful!")

    def test_nvmeof_connect(self):
        log.info(f"[nvmeof test]: nvme connect -t tcp --traddr $NVMEOF_GATEWAY_IP_ADDRESS -s $NVMEOF_PORT -n $NVMEOF_NQN")
        _, stdout_, stderr_ = self._run_cmd(args=[
            "sudo", "nvme", "connect", "-t", "tcp", 
            "--traddr", run.Raw('$NVMEOF_GATEWAY_IP_ADDRESS'), 
            "-s",  run.Raw('$NVMEOF_PORT'), 
            "-n",  run.Raw('$NVMEOF_NQN')
        ])
        log.info("stderr_ of connect '%s'" % stderr_)
        log.info("stdout_ of connect '%s'" % stdout_)
        log.info(f"[nvmeof test]: nvme list")
        _, stdout, stderr = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = "SPDK bdev Controller"
        expected_connect_stderr = ""
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        assert expected_connect_stderr == stderr, f"Expected stderr: {expected_connect_stderr}, but got: {stderr}"
        log.info(f"[nvmeof test]: test_nvmeof_connect successful!")

    def test_nvmeof_disconnect_all(self):
        log.info(f"[nvmeof test]: nvme disconnect-all")
        self._run_cmd(args=["sudo", "nvme", "disconnect-all"])
        _, stdout, _ = self._run_cmd(args=[
            "sudo", "nvme", "list", run.Raw('|'), "wc", "-l" 
        ])
        assert 2 == int(stdout.strip()), f"Expected stdout: 2, but got: {int(stdout.strip())}"
        log.info(f"[nvmeof test]: test_nvmeof_disconnect_all successful!")

    def test_nvmeof_connect_all(self):
        log.info(f"[nvmeof test]: nvme connect-all --traddr=$NVMEOF_GATEWAY_IP_ADDRESS --transport=tcp")
        self._run_cmd(args=[
            "sudo", "nvme", "connect-all", run.Raw('--traddr=$NVMEOF_GATEWAY_IP_ADDRESS'), "--transport=tcp", 
        ])
        _, stdout, stderr = self._run_cmd(args=["sudo", "nvme", "list"])
        expected_connect_stdout = "SPDK bdev Controller"
        expected_connect_stderr = ""
        assert expected_connect_stdout in stdout, f"Expected stdout: {expected_connect_stdout}, but got: {stdout}"
        assert expected_connect_stderr == stderr, f"Expected stderr: {expected_connect_stderr}, but got: {stderr}"
        log.info(f"[nvmeof test]: test_nvmeof_connect_all successful!")


task = Nvmeof
basic_tests = BasicTests