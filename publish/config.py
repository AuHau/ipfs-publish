import json
import logging
import os
import pathlib
import pprint
import typing

import click
import inquirer
import ipfshttpclient
import toml

from publish import ENV_NAME_CONFIG_PATH, exceptions, ENV_NAME_IPFS_HOST, ENV_NAME_IPFS_PORT, ENV_NAME_IPFS_MULTIADDR

logger = logging.getLogger('publish.config')


class Config:
    DEFAULT_CONFIG_PATH = os.path.expanduser('~/.ipfs_publish.toml')

    def __init__(self, path):  # type: (pathlib.Path) -> None
        if not path.exists():
            raise exceptions.ConfigException('The config was not found on this path! {}'.format(path))

        data = toml.load(path)
        logger.debug(f'Loaded configuration:\n{pprint.pformat(data)}')
        self.data, self.repos = self._load_data(data)

        self.loaded_path = path
        self._ipfs = None

    def _load_data(self,
                   data):  # type: (typing.Dict[str, typing.Any]) -> typing.Tuple[dict, typing.Dict[str, publishing.Repo]]
        from publish import publishing

        self._verify_data(data)

        repos: typing.Dict[str, publishing.GenericRepo] = {}
        for value in data.pop('repos', {}).values():
            repo_class = publishing.get_repo_class(value['git_repo_url'])
            repo = repo_class.from_toml_dict(value, self)
            repos[repo.name] = repo

        return data, repos

    def _verify_data(self, data):
        if not data.get('host') or not data.get('port'):
            raise exceptions.ConfigException('\'host\' and \'port\' are required items in configuration file!')

    def save(self):
        data = json.loads(json.dumps(self.data))
        data['repos'] = {}

        for repo in self.repos.values():
            data['repos'][repo.name] = repo.to_toml_dict()

        with self.loaded_path.open('w') as f:
            toml.dump(data, f)

    def __getitem__(self, item):
        return self.data.get(item)  # TODO: [Q] Is this good idea? Return None instead of KeyError?

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def webhook_base(self):
        return 'http://{}{}'.format(self['host'], f':{self["port"]}' if self['port'] != 80 else '')

    @property
    def ipfs(self):  # type: () -> ipfshttpclient.Client
        if self._ipfs is None:
            if self['ipfs'] is not None:
                host = os.environ.get(ENV_NAME_IPFS_HOST) or self['ipfs'].get('host')
                port = os.environ.get(ENV_NAME_IPFS_PORT) or self['ipfs'].get('port')
                multiaddr = os.environ.get(ENV_NAME_IPFS_MULTIADDR) or self['ipfs'].get('multiaddr')
            else:
                multiaddr = os.environ.get(ENV_NAME_IPFS_MULTIADDR)
                host = os.environ.get(ENV_NAME_IPFS_HOST)
                port = os.environ.get(ENV_NAME_IPFS_PORT)

            # Hack to allow cross-platform Docker to reference the Docker host's machine with $HOST_ADDR
            if host.startswith('$'):
                logger.info(f'Resolving host name from environment variable {host}')
                host = os.environ[host[1:]]

            if host == 'localhost':
                host = '127.0.0.1'

            if not multiaddr:
                multiaddr = f'/ip4/{host}/tcp/{port}/http'

            logger.info(f'Connecting and caching to IPFS host \'{multiaddr}\'')
            self._ipfs = ipfshttpclient.connect(multiaddr)

        return self._ipfs

    @classmethod
    def get_instance(cls, path=None):  # type: (typing.Optional[pathlib.Path]) -> Config
        """
        Method that resolves from where the config should be loaded.

        :return:
        """
        if hasattr(cls, '_instance'):
            instance = cls._instance

            if path is not None and instance.loaded_path != path:
                logger.warning('Somebody is trying to load config with different path "{}", but we already have cached'
                               'instance with path "{}"'.format(path, instance.loaded_path))

            return instance

        if path is None:
            if ENV_NAME_CONFIG_PATH in os.environ:
                path = pathlib.Path(os.environ[ENV_NAME_CONFIG_PATH])
            else:
                path = pathlib.Path(cls.DEFAULT_CONFIG_PATH)

        # Default config should exist, if not lets create it.
        if not path.exists():
            logger.info(f'Config on the path {path} was not found! Bootstrapping it there!')
            cls.bootstrap(path)

        logger.info('Loading and caching config from file: {}'.format(path))
        cls._instance = cls(path)
        return cls._instance

    @classmethod
    def bootstrap(cls, path):
        click.echo('Welcome!\nLet\'s bootstrap some basic configuration:')
        host = inquirer.shortcuts.text('Set web server\'s host', default='localhost')
        port = int(inquirer.shortcuts.text('Set web server\'s port', default='8080', validate=lambda _, x: str(x).isdigit()))

        ipfs_multiaddr = inquirer.shortcuts.text('Set IPFS\'s multiaddr', default='/ip4/127.0.0.1/tcp/5001/http')

        with path.open('w') as f:
            toml.dump({'host': host, 'port': port, 'ipfs': {'multiaddr': ipfs_multiaddr }}, f)

        click.echo('Bootstrap successful! Let\'s continue with your original command.\n')
