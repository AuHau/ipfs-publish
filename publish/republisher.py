import datetime
import logging
import re
from time import sleep

from publish import exceptions, config as config_module

logger = logging.getLogger('publish.republisher')

SLEEP_BETWEEN_CHECKS = 30  # seconds
ACCEPTED_DELTA_FOR_PUBLISHING = datetime.timedelta(minutes=15)

LIFETIME_SYNTAX_REGEX = r'(?:(\d+)(h|m|s)(?!.*\2)\s?)+?'
LIFETIME_MAPPING = {
    'h': 'hours',
    'm': 'minutes',
    's': 'seconds',
}


def convert_lifetime(value, ):
    matches = re.findall(LIFETIME_SYNTAX_REGEX, value, re.IGNORECASE)

    # If nothing matches ==> unknown syntax ==> fallback to DateTime parsing
    if not matches:
        raise exceptions.PublishingException('Unknown lifetime syntax!')

    base = datetime.timedelta()
    for match in matches:
        unit = LIFETIME_MAPPING[match[1].lower()]

        base += datetime.timedelta(**{unit: int(match[0])})

    return base


def should_repo_publish(repo, last_publishes):
    if repo.name not in last_publishes:
        return True

    diff = datetime.datetime.now() - last_publishes[repo.name]
    return diff <= ACCEPTED_DELTA_FOR_PUBLISHING


def republishing():
    config = config_module.Config.get_instance()
    last_publishes = {}

    while True:
        for repo in config.repos.values():
            if repo.republish and should_repo_publish(repo, last_publishes):
                logger.info(f'Publishing repo {repo.name}')
                repo.publish_name()
                last_publishes[repo.name] = datetime.datetime.now()

        sleep(30)


def start_publishing():
    try:
        republishing()
    except KeyboardInterrupt:
        logging.info('Recieved SIGINT, terminating republisher service')


if __name__ == '__main__':
    start_publishing()
