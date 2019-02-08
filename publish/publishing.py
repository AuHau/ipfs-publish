import logging
import os
import pathlib
import re
import secrets
import shutil
import string
import subprocess
import tempfile
import typing

import click
import git
import inquirer
import ipfsapi

from publish import config as config_module, exceptions, PUBLISH_IGNORE_FILENAME, DEFAULT_LENGTH_OF_SECRET, \
    IPNS_KEYS_NAME_PREFIX, IPNS_KEYS_TYPE, helpers, republisher

logger = logging.getLogger('publish.publishing')


def get_name_from_url(url):  # type: (str) -> str
    return re.sub(r'\W', '_', url.replace('https://', ''))


def validate_name(name, config):
    return name.lower() not in config.repos


def validate_lifetime(lifetime):
    try:
        republisher.convert_lifetime(lifetime)
        return True
    except exceptions.PublishingException:
        return False


def validate_url(url):
    """
    Attribution goes to Django project.

    :param url:
    :return:
    """
    regex = re.compile(
        r'^(?:http)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return re.match(regex, url) is not None


def validate_repo(url):
    if not validate_url(url):
        return False

    result = subprocess.run('git -c core.askpass=\'echo\' ls-remote ' + url, shell=True, capture_output=True)
    if result.returncode != 0:
        print('\nError! ' + result.stderr.decode('utf-8'))

    return result.returncode == 0


def is_github_url(url):
    return 'github' in url.lower()


def get_repo_class(url):
    if is_github_url(url):
        return GithubRepo

    return GenericRepo


def bootstrap_repo(config: config_module.Config, git_repo_url=None, **kwargs):
    if git_repo_url is None:
        git_repo_url = inquirer.shortcuts.text('Git URL of the repo', validate=lambda _, x: validate_repo(x))

    if is_github_url(git_repo_url):
        return GithubRepo.bootstrap_repo(config, git_repo_url=git_repo_url, **kwargs)

    return GenericRepo.bootstrap_repo(config, git_repo_url=git_repo_url, **kwargs)


class GenericRepo:
    TOML_MAPPING = {
        'name': None,
        'git_repo_url': None,
        'secret': None,
        'publish_dir': None,
        'last_ipfs_addr': None,
        'pin': None,
        'build_bin': 'execute',
        'after_publish_bin': 'execute',
        'republish': 'ipns',
        'ipns_key': 'ipns',
        'ipns_addr': 'ipns',
        'ipns_lifetime': 'ipns',
    }

    def __init__(self, config: config_module.Config, name: str, git_repo_url: str, secret: str,
                 ipns_addr: typing.Optional[str] = None, ipns_key: typing.Optional[str] = None, ipns_lifetime='24h',
                 republish=False, pin=True, last_ipfs_addr=None, publish_dir: str = '/',
                 build_bin=None, after_publish_bin=None):
        self.name = name
        self.git_repo_url = git_repo_url
        self.secret = secret
        self.config = config

        # IPFS setting
        self.pin = pin
        self.republish = republish
        self.ipns_key = ipns_key
        self.last_ipfs_addr = last_ipfs_addr
        self.ipns_lifetime = ipns_lifetime
        self.ipns_addr = ipns_addr

        # Build etc. setting
        self.publish_dir = publish_dir
        self.build_bin = build_bin
        self.after_publish_bin = after_publish_bin

    @property
    def webhook_url(self):
        return f'{self.config.webhook_base}/publish/{self.name}?secret={self.secret}'

    def _run_bin(self, cwd, cmd, *args):
        os.chdir(cwd)

        r = subprocess.run(f'{cmd} {" ".join(args)}', shell=True, capture_output=True)

        if r.returncode != 0:
            r.stderr and logger.debug(f'STDERR: {r.stderr.decode("utf-8")}')
            r.stdout and logger.debug(f'STDOUT: {r.stdout.decode("utf-8")}')
            raise exceptions.RepoException(f'\'{cmd}\' binary exited with non-zero code!')

    def publish_repo(self):
        path = self._clone_repo()

        if self.build_bin is not None:
            self._run_bin(path, self.build_bin)

        self._remove_ignored_files(path)

        ipfs = self.config.ipfs
        if not self.config['keep_pinned_previous_versions'] and self.last_ipfs_addr is not None:
            logger.info(f'Unpinning hash: {self.last_ipfs_addr}')
            ipfs.pin_rm(self.last_ipfs_addr)

        publish_dir = path / (self.publish_dir[1:] if self.publish_dir.startswith('/') else self.publish_dir)
        logger.info(f'Adding directory {publish_dir} to IPFS')
        result = ipfs.add(str(publish_dir), recursive=True, pin=self.pin)
        self.last_ipfs_addr = f'/ipfs/{result[-1]["Hash"]}/'
        logger.info(f'Repo successfully added to IPFS with hash: {self.last_ipfs_addr}')

        if self.ipns_key is not None:
            self.publish_name()

        if self.after_publish_bin is not None:
            self._run_bin(path, self.after_publish_bin, self.last_ipfs_addr)

        self._cleanup_repo(path)

    def publish_name(self):
        if self.last_ipfs_addr is None:
            return

        logger.info('Updating IPNS name')
        ipfs = self.config.ipfs
        ipfs.name_publish(self.last_ipfs_addr, key=self.ipns_key)
        logger.info('IPNS successfully published')

    def _clone_repo(self):
        path = tempfile.mkdtemp()
        logger.info(f'Cloning repo: \'{self.git_repo_url}\' to {path}')

        git.Repo.clone_from(self.git_repo_url, path)

        return pathlib.Path(path).resolve()

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
        for path_to_delete in path.glob(glob):
            path_to_delete = path_to_delete.resolve()
            if not path_to_delete.exists():
                continue

            if path not in path_to_delete.parents:
                raise exceptions.RepoException(f'Trying to delete file outside the repo temporary directory! {path_to_delete}')

            if path_to_delete.is_file():
                path_to_delete.unlink()
            else:
                shutil.rmtree(str(path_to_delete))

    @staticmethod
    def _cleanup_repo(path):
        logging.info(f'Cleaning up path: {path}')
        shutil.rmtree(path)

    def to_toml_dict(self) -> dict:
        out = {}
        for attr, section in self.TOML_MAPPING.items():
            value = getattr(self, attr, None)

            if section is None:
                if value is not None:
                    out[attr] = value
            else:
                if section not in out:
                    out[section] = {}

                if value is not None:
                    out[section][attr] = value

        return out

    @classmethod
    def from_toml_dict(cls, data, config):

        try:
            return cls(config=config, **helpers.flatten(data))
        except TypeError:
            raise exceptions.RepoException('Passed repo\'s data are not valid for creating valid Repo instance!')

    @classmethod
    def bootstrap_repo(cls, config: config_module.Config, name=None, git_repo_url=None, secret=None, ipns_key=None,
                       ipns_lifetime=None, pin=None, republish=None, after_publish_bin=None, build_bin=None,
                       publish_dir: typing.Optional[str] = None) -> 'GenericRepo':

        if git_repo_url is None:
            git_repo_url = inquirer.shortcuts.text('Git URL of the repo', validate=lambda _, x: validate_repo(x))

        if name is None:
            name = inquirer.shortcuts.text('Name of the new repo', default=get_name_from_url(git_repo_url),
                                           validate=lambda _, x: validate_name(x, config)).lower()
        else:
            name = name.lower()

        if name in config.repos:
            raise exceptions.RepoException('Repo with this name already exists! (Names are case insensitive!)')

        ipns_key, ipns_addr = bootstrap_ipns(config, name, ipns_key)

        if secret is None:
            secret = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits) for _ in range(DEFAULT_LENGTH_OF_SECRET))

        if republish is None:
            republish = inquirer.shortcuts.confirm('Do you want to periodically republish the IPNS object?',
                                                   default=True)

        if pin is None:
            pin = inquirer.shortcuts.confirm('Do you want to pin the published IPFS objects?', default=True)

        if build_bin is None:
            build_bin = inquirer.shortcuts.text('Path to build binary, if you want to do some pre-processing '
                                                'before publishing', default='')

        if after_publish_bin is None:
            after_publish_bin = inquirer.shortcuts.text('Path to after-publish binary, if you want to do some '
                                                        'actions after publishing', default='')

        if publish_dir is None:
            publish_dir = inquirer.shortcuts.text('Directory to be published inside the repo. Path related to the root '
                                                  'of the repo', default='/')

        ipns_lifetime = ipns_lifetime or '24h'
        if not validate_lifetime(ipns_lifetime):
            raise exceptions.RepoException('Passed lifetime is not valid! Supported units are: h(our), m(inute), '
                                           's(seconds)!')

        if ipns_key is None and after_publish_bin is None:
            raise exceptions.RepoException(
                'You have choose not to use IPNS and you also have not specified any after publish command. '
                'This does not make sense! What do you want to do with this setting?! I have no idea, so aborting!')

        return cls(config=config, name=name, git_repo_url=git_repo_url, secret=secret, pin=pin, publish_dir=publish_dir,
                   ipns_key=ipns_key, ipns_addr=ipns_addr, build_bin=build_bin, after_publish_bin=after_publish_bin,
                   republish=republish, ipns_lifetime=ipns_lifetime)


def bootstrap_ipns(config: config_module.Config, name: str, ipns_key: str = None) -> typing.Tuple[str, str]:
    ipns_addr = None
    if ipns_key is None:
        wanna_ipns = inquirer.shortcuts.confirm('Do you want to publish to IPNS?', default=True)

        if wanna_ipns:
            ipns_key = f'{IPNS_KEYS_NAME_PREFIX}_{name}'

            try:
                out = config.ipfs.key_gen(ipns_key, IPNS_KEYS_TYPE)
            except ipfsapi.exceptions.Error:
                use_existing = inquirer.shortcuts.confirm(f'There is already IPNS key with name \'{ipns_key}\', '
                                                          f'do you want to use it?', default=True)

                if use_existing:
                    keys = config.ipfs.key_list()
                    out = next((x for x in keys['Keys'] if x['Name'] == ipns_key), None)

                    if out is None:
                        raise exceptions.RepoException('We were not able to generate or fetch the IPNS key')
                else:
                    while True:
                        ipns_key = inquirer.shortcuts.text('Then please provide non-existing name for the IPNS key')

                        try:
                            out = config.ipfs.key_gen(ipns_key, IPNS_KEYS_TYPE)
                            break
                        except ipfsapi.exceptions.Error:
                            click.echo('There is already existing key with this name!')
                            continue

            ipns_addr = f'/ipns/{out["Id"]}/'
    else:
        keys = config.ipfs.key_list()
        key_object = next((x for x in keys['Keys'] if x['Name'] == ipns_key), None)
        if key_object is None:
            logger.info('The passed IPNS key name \'{}\' was not found, generating new key with this name')
            key_object = config.ipfs.key_gen(ipns_key, IPNS_KEYS_TYPE)

        ipns_addr = f'/ipns/{key_object["Id"]}/'

    return ipns_key, ipns_addr


class GithubRepo(GenericRepo):

    def __init__(self, git_repo_url, **kwargs):
        if not is_github_url(git_repo_url):
            raise exceptions.RepoException('The passed Git repo URL is not related to GitHub!')

        super().__init__(git_repo_url=git_repo_url, **kwargs)

    @property
    def webhook_url(self):
        return f'{self.config.webhook_base}/publish/{self.name}'
