import hmac
import logging
import pathlib
import shutil
import tempfile

import git

from publish import config as config_module, exceptions, PUBLISH_IGNORE_FILENAME

logger = logging.getLogger('publish.publishing')


def get_name_from_url(url):  # type: (str) -> str
    return url.replace('https://', '')


class Repo:

    def __init__(self, name, git_repo_url, secret, ipns_key, config, ipns_lifetime='24h', republish=False, pin=True,
                 last_hash=None):
        self.name = name
        self.git_repo_url = git_repo_url
        self.secret = secret
        self.ipns_key = ipns_key
        self.republish = republish
        self.pin = pin
        self.config = config  # type: config_module.Config
        self.last_hash = last_hash
        self.ipns_lifetime = ipns_lifetime

    @property
    def is_github(self):
        return 'github' in self.git_repo_url

    def publish_repo(self):
        path = self._clone_repo()
        self._remove_ignored_files(path)

        ipfs = self.config.ipfs
        if not self.config['keep_pinned_previous_versions'] and self.last_hash is not None:
            logger.info('Unpinning hash: {}'.format(self.last_hash))
            ipfs.pin_rm(self.last_hash)

        result = ipfs.add(str(path), recursive=True, pin=self.pin)
        self.last_hash = '/ipfs/{}/'.format(result[-1]['Hash'])
        logger.info('Repo successfully added to IPFS with hash: {}'.format(self.last_hash))

        self.publish_name()
        self._cleanup_repo(path)

    def publish_name(self):
        if self.last_hash is None:
            return

        logger.info('Updating IPNS name')
        ipfs = self.config.ipfs
        ipfs.name_publish(self.last_hash)
        logger.info('IPNS successfully published')

    def _clone_repo(self):
        path = tempfile.mkdtemp()
        logger.info('Cloning repo: \'{}\' to {}'.format(self.git_repo_url, path))

        git.Repo.clone_from(self.git_repo_url, path)

        return pathlib.Path(path)

    def _remove_ignored_files(self, path):
        shutil.rmtree(path / '.git')
        ignore_file = path / PUBLISH_IGNORE_FILENAME

        if not ignore_file.exists():
            return

        entries = ignore_file.read_text()
        for entry in entries.split('\n'):
            self._remove_glob(path, entry)

        ignore_file.unlink()

    def _remove_glob(self, path, glob):
        for file in path.glob(glob):
            file.unlink()

    def is_data_signed_correctly(self, data, signature):
        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(self.secret, msg=data, digestmod='sha1')

        if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
            return False

        return True

    @classmethod
    def from_toml(cls, data, config):
        try:
            return cls(config=config, **data)
        except TypeError:
            raise exceptions.RepoException('Passed repo\'s data are not valid for creating valid Repo instance!')

    @staticmethod
    def _cleanup_repo(path):
        logging.info('Cleaning up path: {}'.format(path))
        shutil.rmtree(path)
