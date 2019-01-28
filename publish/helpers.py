import logging
import sys


#######################################################################
# Logging
class NoOutput:
    def write(self):
        pass


VERBOSITY_PACKAGES = {
    'urllib3': 5,
}


def setup_logging(verbosity):
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

    if verbosity > 2:
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
