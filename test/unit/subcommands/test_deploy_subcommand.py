from functools import partial
from unittest.mock import MagicMock

from genty import genty, genty_dataset

from app.subcommands.deploy_subcommand import DeploySubcommand
from app.util.network import Network
from test.framework.base_unit_test_case import BaseUnitTestCase


@genty
class TestDeploySubcommand(BaseUnitTestCase):
    def setUp(self):
        super().setUp()
        self.patch('app.subcommands.deploy_subcommand.fs.compress_directory')

    def test_binaries_tar_raises_exception_if_running_from_source(self):
        deploy_subcommand = DeploySubcommand()
        with self.assertRaisesRegex(SystemExit, '1'):
            deploy_subcommand._binaries_tar('python main.py deploy', '~/.clusterrunner/dist')

    def test_binaries_doesnt_raise_exception_if_running_from_bin(self):
        self.patch('os.path.isfile').return_value = True
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._binaries_tar('clusterrunner', '~/.clusterrunner/dist')

    def test_deploy_binaries_and_conf_deploys_both_conf_and_binary_for_remote_host(self):
        mock_DeployTarget = self.patch('app.subcommands.deploy_subcommand.DeployTarget')
        mock_DeployTarget_instance = mock_DeployTarget.return_value
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._deploy_binaries_and_conf(
            'remote_host', 'username', 'exec', '/path/to/exec', '/path/to/conf')
        self.assertTrue(mock_DeployTarget_instance.deploy_binary.called)
        self.assertTrue(mock_DeployTarget_instance.deploy_conf.called)

    def test_deploy_binaries_and_conf_doesnt_deploy_conf_if_localhost_with_same_in_use_conf(self):
        self.patch('os.path.expanduser').return_value = '/home'
        mock_DeployTarget = self.patch('app.subcommands.deploy_subcommand.DeployTarget')
        mock_DeployTarget_instance = mock_DeployTarget.return_value
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._deploy_binaries_and_conf(
            'localhost', 'username', 'exec', '/path/to/exec', '/home/.clusterrunner/clusterrunner.conf')
        self.assertFalse(mock_DeployTarget_instance.deploy_conf.called)

    def test_deploy_binaries_and_conf_deploys_conf_if_localhost_with_diff_in_use_conf(self):
        self.patch('os.path.expanduser').return_value = '/home'
        mock_DeployTarget = self.patch('app.subcommands.deploy_subcommand.DeployTarget')
        mock_DeployTarget_instance = mock_DeployTarget.return_value
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._deploy_binaries_and_conf(
            'localhost',
            'username',
            'exec',
            '/path/to/exec',
            '/home/.clusterrunner/clusterrunner_prime.conf'
        )
        self.assertTrue(mock_DeployTarget_instance.deploy_conf.called)

    def test_deploy_binaries_and_conf_deploys_binaries_if_localhost_and_different_executable_path_in_use(self):
        self.patch('os.path.expanduser').return_value = '/home'
        mock_DeployTarget = self.patch('app.subcommands.deploy_subcommand.DeployTarget')
        mock_DeployTarget_instance = mock_DeployTarget.return_value
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._deploy_binaries_and_conf(
            'localhost',
            'username',
            '/home/.clusterrunner/dist/clusterrunner_rime',
            '/home/.clusterrunner/clusterrunner.tgz',
            '/clusterrunner.conf'
        )
        self.assertTrue(mock_DeployTarget_instance.deploy_binary.called)

    def test_deploy_binaries_and_conf_doesnt_deploy_binaries_if_localhost_and_same_executable_path_in_use(self):
        self.patch('os.path.expanduser').return_value = '/home'
        mock_DeployTarget = self.patch('app.subcommands.deploy_subcommand.DeployTarget')
        mock_DeployTarget_instance = mock_DeployTarget.return_value
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._deploy_binaries_and_conf(
            'localhost',
            'username',
            '/home/.clusterrunner/dist/clusterrunner',
            '/home/.clusterrunner/clusterrunner.tgz',
            '/clusterrunner.conf'
        )
        self.assertFalse(mock_DeployTarget_instance.deploy_binary.called)

    def test_non_registered_slaves_returns_empty_list_if_all_registered(self):
        registered_hosts = ['host_1', 'host_2']
        slaves_to_validate = ['host_1', 'host_2']

        def rsa_key(*args, **kwargs):
            if args[0] == 'host_1':
                return 'rsa_key_1'
            elif args[0] == 'host_2':
                return 'rsa_key_2'
            else:
                return 'blah'

        old_rsa_key = Network.rsa_key
        Network.rsa_key = rsa_key
        deploy_subcommand = DeploySubcommand()
        non_registered = deploy_subcommand._non_registered_slaves(registered_hosts, slaves_to_validate)
        Network.rsa_key = old_rsa_key
        self.assertEquals(0, len(non_registered))

    def test_non_registered_slaves_returns_non_registered_slaves(self):
        registered_hosts = ['host_1', 'host_3']
        slaves_to_validate = ['host_1', 'host_2', 'host_3', 'host_4']

        def rsa_key(*args, **kwargs):
            if args[0] == 'host_1':
                return 'rsa_key_1'
            elif args[0] == 'host_2':
                return 'rsa_key_2'
            elif args[0] == 'host_3':
                return 'rsa_key_3'
            elif args[0] == 'host_4':
                return 'rsa_key_4'
            else:
                return 'blah'

        self.patch('app.util.network.Network.rsa_key', new=rsa_key)
        deploy_subcommand = DeploySubcommand()
        non_registered = deploy_subcommand._non_registered_slaves(registered_hosts, slaves_to_validate)
        self.assertEquals(len(non_registered), 2)
        self.assertTrue('host_2' in non_registered)
        self.assertTrue('host_4' in non_registered)

    def test_non_registered_slaves_returns_empty_list_with_slaves_with_same_rsa_keys_but_different_names(self):
        registered_hosts = ['host_1_alias', 'host_2_alias']
        slaves_to_validate = ['host_1', 'host_2']

        def rsa_key(*args, **kwargs):
            if args[0] == 'host_1':
                return 'rsa_key_1'
            elif args[0] == 'host_2':
                return 'rsa_key_2'
            elif args[0] == 'host_1_alias':
                return 'rsa_key_1'
            elif args[0] == 'host_2_alias':
                return 'rsa_key_2'
            else:
                return 'blah'

        self.patch('app.util.network.Network.rsa_key', new=rsa_key)
        deploy_subcommand = DeploySubcommand()
        non_registered = deploy_subcommand._non_registered_slaves(registered_hosts, slaves_to_validate)
        self.assertEquals(0, len(non_registered))

    @genty_dataset(
        (['slave_host_1', 'slave_host_2'], ['slave_host_1', 'slave_host_2'], True),
        (['slave_host_1', 'slave_host_2'], ['slave_host_3', 'slave_host_2'], False),
        (['slave_host_1'], ['slave_host_1', 'slave_host_2'], False),
    )
    def test_validate_deployment_checks_each_slave_is_connected(self, slaves_to_validate, connected_slaves, is_valid):
        deploy_subcommand = DeploySubcommand()
        deploy_subcommand._registered_slave_hostnames = MagicMock(return_value=connected_slaves)
        deploy_subcommand._SLAVE_REGISTRY_TIMEOUT_SEC = 1
        deploy_subcommand._non_registered_slaves = MagicMock()
        validate = partial(deploy_subcommand._validate_successful_deployment, 'master_host_url', slaves_to_validate)
        if not is_valid:
            with self.assertRaises(SystemExit):
                validate()
        else:
            validate()
