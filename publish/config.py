import logging
import os
import pathlib
import typing

import ipfsapi
import toml

from publish import CONFIG_PATH_ENV_NAME, exceptions, publishing

logger = logging.getLogger('publish.config')


class Config:

    DEFAULT_CONFIG_PATH = os.path.expanduser('~/.ipfs_publish.toml')

    MANDATORY_FIELDS = {
        'ipfs': {
            'host',
            'port',
        },
    }

    def __init__(self, path):  # type: (pathlib.Path) -> None
        if not path.exists():
            raise exceptions.ConfigException('The config was not found on this path! {}'.format(path))

        data = toml.load(path)
        self.data, self.repos = self._load_data(data)

        self.loaded_path = path
        self._ipfs = None

    def _load_data(self, data):  # type: (typing.Dict[str, typing.Any]) -> typing.Tuple[dict, typing.Dict[str, publishing.Repo]]
        self._verify_data(data)

        repos = {}
        for key, value in data['repos'].items():
            repo = publishing.Repo.from_toml(value, self)
            repos[repo.name] = repo

        data.pop('repos')
        return data, repos

    def _verify_data(self, data):
        if 'repos' not in data or not isinstance(data['repos'], dict):
            raise exceptions.ConfigException('\'repos\' is required table with all configured repos!')

        def _recursive_check(data, schema):
            if isinstance(schema, set):
                schema = dict.fromkeys(schema, None)

            for mandatory_key, value in schema.items():
                if mandatory_key not in data:
                    raise exceptions.ConfigException('\'{}\' is required configuration!'.format(mandatory_key))

                # Lets recurrently checked nested options
                if value is not None:
                    _recursive_check(data[mandatory_key], value)

        _recursive_check(data, self.MANDATORY_FIELDS)

    def __getitem__(self, item):
        return self.data.get(item)  # TODO: [Q] Is this good idea? Return None instead of KeyError?

    def __setitem__(self, key, value):
        self.data[key] = value

    @property
    def ipfs(self):  # type: () -> ipfsapi.Client
        if self._ipfs is None:
            logger.info('Connecting and caching to IPFS host \'{}\' on port {}'.format(self['ipfs']['host'], self['ipfs']['port']))
            self._ipfs = ipfsapi.connect(self['ipfs']['host'], self['ipfs']['port'])

        return self._ipfs

    @classmethod
    def factory(cls, path=None):  # type: (typing.Optional[pathlib.Path]) -> Config
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
            if CONFIG_PATH_ENV_NAME in os.environ:
                path = pathlib.Path(os.environ[CONFIG_PATH_ENV_NAME])
            else:
                path = pathlib.Path(cls.DEFAULT_CONFIG_PATH)

        logger.info('Loading and caching config from file: {}'.format(path))
        cls._instance = cls(path)
        return cls._instance
