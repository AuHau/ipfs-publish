import datetime
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
    IPNS_KEYS_NAME_PREFIX, IPNS_KEYS_TYPE, helpers

logger = logging.getLogger('publish.publishing')

repo_class = typing.Union[typing.Type['GithubRepo'], typing.Type['GenericRepo']]
repo_instance = typing.Union['GithubRepo', 'GenericRepo']

DEFAULT_BRANCH_PLACEHOLDER = '<default branch>'


def get_name_from_url(url: str) -> str:
    """
    Converts URL into string, with removing https:// and any non-alphabet character with _
    :param url:
    :return:
    """
    return re.sub(r'\W', '_', url.replace('https://', '')).lower()


def validate_name(name: str, config: config_module.Config) -> bool:
    """
    Validate that name is not already present in the configuration.

    :param name:
    :param config:
    :return:
    """
    return name.lower() not in config.repos


LIFETIME_SYNTAX_REGEX = r'(?:(\d+)(h|m|s)(?!.*\2))'
"""
Regex validating lifetime syntax, examples:
1h -> TRUE
1M -> TRUE
1s -> TRUE
5h2m1s -> TRUE
1m2m -> FALSE
1h 2m -> FALSE
"""

LIFETIME_SYNTAX_CHECK_REGEX = f'^{LIFETIME_SYNTAX_REGEX}+?$'
LIFETIME_MAPPING = {
    'h': 'hours',
    'm': 'minutes',
    's': 'seconds',
}


def convert_lifetime(value: str) -> datetime.timedelta:
    """
    Converts lifetime string into timedelta object
    :param value:
    :return:
    """
    if re.match(LIFETIME_SYNTAX_CHECK_REGEX, value, re.IGNORECASE) is None:
        raise exceptions.PublishingException('Unknown lifetime syntax!')

    matches = re.findall(LIFETIME_SYNTAX_REGEX, value, re.IGNORECASE)
    base = datetime.timedelta()
    for match in matches:
        unit = LIFETIME_MAPPING[match[1].lower()]

        base += datetime.timedelta(**{unit: int(match[0])})

    return base


def validate_time_span(lifetime: str):
    """
    Function validating lifetime syntax
    :param lifetime:
    :return:
    """
    try:
        convert_lifetime(lifetime)
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


def validate_repo(url: str) -> bool:
    """
    Validate Git repository which is supposed to be placed on passed URL.
    Validated are two points: validity of the URL and being able to access the Git repo.

    Checking accessibility of the repo is done using `git ls-remote`, hence the repo must not be protected with
    password.

    :param url:
    :return:
    """
    if not validate_url(url):
        return False

    result = subprocess.run('git -c core.askpass=\'echo\' ls-remote ' + url, shell=True, capture_output=True)
    if result.returncode != 0:
        logger.error(f'Error while fetching Git\'s remote refs! {result.stderr.decode("utf-8")}')

    return result.returncode == 0


def validate_branch(git_url: str, name: str) -> bool:
    """
    Validate that branch name exists in the Git repository defined by git_url.

    :param git_url:
    :param name:
    :return:
    """
    if name == DEFAULT_BRANCH_PLACEHOLDER:
        return True

    result = subprocess.run('git -c core.askpass=\'echo\' ls-remote ' + git_url, shell=True, capture_output=True)
    if result.returncode != 0:
        raise exceptions.RepoException(f'Error while fetching Git\'s remote refs! {result.stderr.decode("utf-8")}')

    refs_list = result.stdout.decode("utf-8").split('\n')
    regex = re.compile(r'refs/heads/(.*)')

    for entry in refs_list:
        match = regex.search(entry)

        if match is not None and match.group(1) == name:
            return True

    return False


def is_github_url(url: str) -> bool:
    """
    Validate if passed URL is GitHub's url.

    :param url:
    :return:
    """
    return 'github' in url.lower()


def get_repo_class(url: str) -> repo_class:
    """
    For Git repo's URL it returns appropriate class that should represents the repo.
    :param url:
    :return:
    """
    if is_github_url(url):
        return GithubRepo

    return GenericRepo


def bootstrap_repo(config: config_module.Config, git_repo_url=None, **kwargs) -> repo_instance:
    """
    Initiate the interactive bootstrap process of creating new Repo's instance

    :param config:
    :param git_repo_url:
    :param kwargs:
    :return:
    """
    if git_repo_url is None:
        git_repo_url = inquirer.shortcuts.text('Git URL of the repo', validate=lambda _, x: validate_repo(x))

    if is_github_url(git_repo_url):
        return GithubRepo.bootstrap_repo(config, git_repo_url=git_repo_url, **kwargs)

    return GenericRepo.bootstrap_repo(config, git_repo_url=git_repo_url, **kwargs)


class GenericRepo:
    """
    Generic Repo's class that represent and store all information about Git repository that can be placed on any
    Git's provider.

    It allows to publish repo's content to IPFS and IPNS.
    """

    _TOML_MAPPING = {
        'name': None,
        'git_repo_url': None,
        'branch': None,
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
    """
    Mapping that maps the repo's properties into TOML's config sections.
    """

    name: str = None
    """
    Defines name of repo under which it will be represented in the IPFS Publish name/configuration etc.
    """

    git_repo_url: str = None
    """
    Defines where the Git repo is placed and from where it will be clonned.
    """

    branch: typing.Optional[str] = None
    """
    Defines what branch should be checked out.
    """

    secret: str = None
    """
    Defines random string secret, that is used to secure the webhook calls from attacker who would try to triger publish
    events on its own.
    """

    ipns_addr: str = ''
    """
    IPNS address in format "/ipns/<hash>", that defines the address where the repo is published.
    """

    ipns_key: str = ''
    """
    Defines name of the key that will be used for publishing IPNS record
    """

    ipns_lifetime: str = '24h'
    """
    Defines the lifetime of IPNS entries
    """

    pin: bool = True
    """
    Defines if the published content is pinned to the IPFS node
    """

    last_ipfs_addr: typing.Optional[str] = None
    """
    Stores the last IPFS address of the published address in format "/ipfs/<hash>/" 
    """

    publish_dir: str = '/'
    """
    Defines a path inside the repo that will be published. Default is the root of the repo.
    """

    build_bin: typing.Optional[str] = None
    """
    Binary that is invoked prior the publishing to IPFS.
    """

    after_publish_bin: typing.Optional[str] = None
    """
    Binary that is invoked after the content of the repo is published to IPFS. The binary gets as argument
    the IPFS address that it was published under. 
    """

    def __init__(self, config: config_module.Config, name: str, git_repo_url: str, secret: str,
                 branch: typing.Optional[str] = None,
                 ipns_addr: typing.Optional[str] = None, ipns_key: typing.Optional[str] = None, ipns_lifetime='24h',
                 republish=False, pin=True, last_ipfs_addr=None, publish_dir: str = '/',
                 build_bin=None, after_publish_bin=None, ipns_ttl='15m'):
        self.name = name
        self.git_repo_url = git_repo_url
        self.branch = branch
        self.secret = secret
        self.config = config

        # IPFS setting
        self.pin = pin
        self.republish = republish
        self.ipns_key = ipns_key
        self.last_ipfs_addr = last_ipfs_addr
        self.ipns_lifetime = ipns_lifetime
        self.ipns_addr = ipns_addr
        self.ipns_ttl = ipns_ttl

        # Build etc. setting
        self.publish_dir = publish_dir
        self.build_bin = build_bin
        self.after_publish_bin = after_publish_bin

    @property
    def webhook_url(self) -> str:
        """
        Returns URL with FQDN for the webhook invocation.
        :return:
        """
        return f'{self.config.webhook_base}/publish/{self.name}?secret={self.secret}'

    def _run_bin(self, cwd: pathlib.Path, cmd: str, *args):
        """
        Execute binary with arguments in specified directory.

        :param cwd: Directory in which the binary will be invoked
        :param cmd: Binary definition invoked with shell
        :param args:
        :raises exceptions.RepoException: If the binary exited with non-zero status
        :return:
        """
        os.chdir(str(cwd))

        r = subprocess.run(f'{cmd} {" ".join(args)}', shell=True, capture_output=True)

        if r.returncode != 0:
            r.stderr and logger.debug(f'STDERR: {r.stderr.decode("utf-8")}')
            r.stdout and logger.debug(f'STDOUT: {r.stdout.decode("utf-8")}')
            raise exceptions.RepoException(f'\'{cmd}\' binary exited with non-zero code!')

    def publish_repo(self) -> None:
        """
        Main method that handles publishing of the repo to IPFS.

        :return:
        """
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

    def publish_name(self) -> None:
        """
        Main method that handles publishing of the IPFS addr into IPNS.
        :return:
        """
        if self.last_ipfs_addr is None:
            return

        logger.info('Updating IPNS name')
        ipfs = self.config.ipfs
        ipfs.name_publish(self.last_ipfs_addr, key=self.ipns_key, ttl=self.ipns_ttl)
        logger.info('IPNS successfully published')

    def _clone_repo(self) -> pathlib.Path:
        """
        Method that will clone the repo defined by git_repo_url into temporary directory and returns the path.
        :return: Path to the root of the cloned repo
        """
        path = tempfile.mkdtemp()
        logger.info(f'Cloning repo: \'{self.git_repo_url}\' to {path}')

        if self.branch:
            git.Repo.clone_from(self.git_repo_url, path, branch=self.branch)
        else:
            git.Repo.clone_from(self.git_repo_url, path)

        return pathlib.Path(path).resolve()

    def _remove_ignored_files(self, path: pathlib.Path):
        """
        Reads the ignore file and removes the ignored files based on glob from the directory and all subdirectories.
        Also removes the ignore file itself and .git folder.

        :param path:
        :return:
        """
        shutil.rmtree(path / '.git')
        ignore_file = path / PUBLISH_IGNORE_FILENAME

        if not ignore_file.exists():
            return

        entries = ignore_file.read_text()
        for entry in entries.split('\n'):
            self._remove_glob(path, entry)

        ignore_file.unlink()

    def _remove_glob(self, path: pathlib.Path, glob: str):
        """
        Removes all files from path that matches the glob string.

        :param path:
        :param glob:
        :return:
        """
        for path_to_delete in path.glob(glob):
            path_to_delete = path_to_delete.resolve()
            if not path_to_delete.exists():
                continue

            if path not in path_to_delete.parents:
                raise exceptions.RepoException(
                    f'Trying to delete file outside the repo temporary directory! {path_to_delete}')

            if path_to_delete.is_file():
                path_to_delete.unlink()
            else:
                shutil.rmtree(str(path_to_delete))

    @staticmethod
    def _cleanup_repo(path):
        """
        Removes the cloned repo from path.

        :param path:
        :return:
        """
        logging.info(f'Cleaning up path: {path}')
        shutil.rmtree(path)

    def to_toml_dict(self) -> dict:
        """
        Serialize the instance into dictionary that is saved to TOML config.
        :return:
        """
        out = {}
        for attr, section in self._TOML_MAPPING.items():
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
    def from_toml_dict(cls, data: dict, config: config_module.Config) -> 'GenericRepo':
        """
        Deserialize the passed data dict of TOML config into instance
        :param data:
        :param config:
        :return:
        """

        try:
            return cls(config=config, **helpers.flatten(data))
        except TypeError:
            raise exceptions.RepoException('Passed repo\'s data are not valid for creating valid Repo instance!')

    @classmethod
    def bootstrap_property(cls, name: str, category: str, message: str, value: typing.Any = None,
                           default: typing.Any = None,
                           validate: typing.Callable = None):
        if value is not None:
            if validate is not None and not validate(None, value):
                raise exceptions.RepoException(f'Invalid {name}: {value}!')

            return value

        return getattr(inquirer.shortcuts, category)(message, validate=validate, default=default)

    @classmethod
    def bootstrap_repo(cls, config: config_module.Config, name=None, git_repo_url=None, branch=None, secret=None,
                       ipns_key=None, ipns_lifetime=None, pin=None, republish=None, after_publish_bin=None,
                       build_bin=None, publish_dir: typing.Optional[str] = None, ipns_ttl=None) -> 'GenericRepo':
        """
        Method that interactively bootstraps the repository by asking interactive questions.

        :param ipns_ttl:
        :param config:
        :param name:
        :param git_repo_url:
        :param branch:
        :param secret:
        :param ipns_key:
        :param ipns_lifetime:
        :param pin:
        :param republish:
        :param after_publish_bin:
        :param build_bin:
        :param publish_dir:
        :return:
        """

        git_repo_url = cls.bootstrap_property('Git repo URL', 'text', 'Git URL of the repo', git_repo_url,
                                              validate=lambda _, x: validate_repo(x))

        name = cls.bootstrap_property('Name', 'text', 'Name of the new repo', name,
                                      default=get_name_from_url(git_repo_url),
                                      validate=lambda _, x: validate_name(x, config)).lower()

        branch = cls.bootstrap_property('Branch name', 'text', 'Do you want to check-out specific branch?', branch,
                                        default=DEFAULT_BRANCH_PLACEHOLDER,
                                        validate=lambda _, x: validate_branch(git_repo_url, x))
        if branch == DEFAULT_BRANCH_PLACEHOLDER:
            branch = None

        ipns_key, ipns_addr = bootstrap_ipns(config, name, ipns_key)

        if secret is None:
            secret = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits) for _ in range(DEFAULT_LENGTH_OF_SECRET))

        pin = cls.bootstrap_property('Pin flag', 'confirm', 'Do you want to pin the published IPFS objects?', pin,
                                     default=True)

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
        if not validate_time_span(ipns_lifetime):
            raise exceptions.RepoException('Passed lifetime is not valid! Supported units are: h(our), m(inute), '
                                           's(seconds)!')

        ipns_ttl = ipns_ttl or '15m'
        if not validate_time_span(ipns_ttl):
            raise exceptions.RepoException('Passed ttl is not valid! Supported units are: h(our), m(inute), '
                                           's(seconds)!')

        if ipns_key is None and after_publish_bin is None:
            raise exceptions.RepoException(
                'You have choose not to use IPNS and you also have not specified any after publish command. '
                'This does not make sense! What do you want to do with this setting?! I have no idea, so aborting!')

        return cls(config=config, name=name, git_repo_url=git_repo_url, branch=branch, secret=secret, pin=pin,
                   publish_dir=publish_dir,
                   ipns_key=ipns_key, ipns_addr=ipns_addr, build_bin=build_bin, after_publish_bin=after_publish_bin,
                   republish=republish, ipns_lifetime=ipns_lifetime, ipns_ttl=ipns_ttl)


def bootstrap_ipns(config: config_module.Config, name: str, ipns_key: str = None) -> typing.Tuple[str, str]:
    """
    Functions that handle bootstraping of IPNS informations.

    :param config:
    :param name:
    :param ipns_key:
    :return:
    """

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
    """
    Special case of Repo specific to GitHub hosted repos.
    """

    def __init__(self, git_repo_url, **kwargs):
        if not is_github_url(git_repo_url):
            raise exceptions.RepoException('The passed Git repo URL is not related to GitHub!')

        super().__init__(git_repo_url=git_repo_url, **kwargs)

    @property
    def webhook_url(self):
        return f'{self.config.webhook_base}/publish/{self.name}'
