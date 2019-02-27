from pbr.version import VersionInfo

VERSION = VersionInfo('ipfs-publish').semantic_version()
__version__ = VERSION.release_string()

APP_NAME = 'ipfs_publish'
"""
Constant that defines the basic application then, that is used for appdata
"""

ENV_NAME_CONFIG_PATH: str = 'IPFS_PUBLISH_CONFIG'
"""
Name of environmental variable that holds path to the toml config that should be used.
"""

ENV_NAME_IPFS_HOST: str = 'IPFS_PUBLISH_IPFS_HOST'
"""
Name of environmental variable that defines the hostname of the go-ipfs's daemon's API.
"""

ENV_NAME_IPFS_PORT: str = 'IPFS_PUBLISH_IPFS_PORT'
"""
Name of environmental variable that defines the port of the go-ipfs's daemon's API.
"""

ENV_NAME_VERBOSITY_LEVEL: str = 'IPFS_PUBLISH_VERBOSITY'
"""
Name of environmental variable that can increase the level of logging verbosity.
"""

ENV_NAME_PASS_EXCEPTIONS: str = 'IPFS_PUBLISH_EXCEPTIONS'
"""
Name of environmental variable that disable catching of Exceptions for CLI commands 
"""

PUBLISH_IGNORE_FILENAME: str = '.ipfs_publish_ignore'
"""
Name of the file that is looked up inside the clonned repo, that defines which files should be removed prior publishing
"""

DEFAULT_LENGTH_OF_SECRET: int = 25
"""
Int defining length of generated secret
"""

IPNS_KEYS_NAME_PREFIX: str = 'ipfs_publish'
"""
Prefix that is prepended to generated name used for naming the IPNS key
"""

IPNS_KEYS_TYPE: str = 'rsa'
"""
Type of IPNS key to be generated
"""
