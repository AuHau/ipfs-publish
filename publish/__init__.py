from pbr.version import VersionInfo

VERSION = VersionInfo('publish').semantic_version()
__version__ = VERSION.release_string()

APP_NAME = 'ipfs_publish'
CONFIG_PATH_ENV_NAME = 'IPFS_PUBLISH_CONFIG'
PUBLISH_IGNORE_FILENAME = '.ipfs_publish_ignore'
DEFAULT_LENGTH_OF_SECRET = 25
IPNS_KEYS_NAME_PREFIX = 'ipfs_publish'
IPNS_KEYS_TYPE = 'rsa'
