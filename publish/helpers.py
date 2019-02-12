import logging
import os
import sys

#######################################################################
# Logging
from publish import ENV_NAME_VERBOSITY_LEVEL, exceptions


class NoOutput:
    def write(self) -> None:
        pass


VERBOSITY_PACKAGES = {
    'urllib3': 4,
    'asyncio': 5,
}
"""
Dictionary that define thresholds of verbosity for packages.
If verbosity (eq. number of Vs for CLI command) is bellowed the number, the logging for the package will be ignored.
"""


def setup_logging(verbosity: int) -> None:
    """
    Setups the logging package based on passed verbosity
    :param verbosity: Verbosity level
    :return:
    """
    if ENV_NAME_VERBOSITY_LEVEL in os.environ:
        try:
            verbosity = max(verbosity, int(os.environ[ENV_NAME_VERBOSITY_LEVEL]))
        except ValueError:
            raise exceptions.IpfsPublishException(f'The env. variable {ENV_NAME_VERBOSITY_LEVEL} has to hold integer!')

    if verbosity == -1:
        sys.stdout = NoOutput()
        sys.stderr = NoOutput()
        return

    if verbosity == 0:
        logging_level = logging.ERROR
    elif verbosity == 1:
        logging_level = logging.INFO
    else:
        logging_level = logging.DEBUG

    logging.basicConfig(stream=sys.stderr, level=logging_level)

    for package, threshold_verbosity in VERBOSITY_PACKAGES.items():
        if verbosity >= threshold_verbosity:
            logging.getLogger(package).setLevel(logging.DEBUG)
        else:
            logging.getLogger(package).setLevel(logging.ERROR)


#######################################################################
# Misc

def flatten(obj: dict):
    """
    Flatten nested dictionaries, it does not namespace the keys, so possible
    conflicts can arise. Conflicts are not allowed, so exception is raised if a
    key should be overwritten.

    :param obj:
    :raises KeyError: If there is already existing key in the new dict
    :return:
    """

    def _flatten(obj: dict, new_obj):
        for k, v in obj.items():
            if isinstance(v, dict):
                _flatten(v, new_obj)
            else:
                if k in new_obj:
                    KeyError(f'Key \'{k}\' is already present in the dict!')

                new_obj[k] = v

        return new_obj

    return _flatten(obj, {})
