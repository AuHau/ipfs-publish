import datetime
import logging
import pathlib
import pickle
import re
import typing
import time

import appdirs
from publish import exceptions, config as config_module, APP_NAME

logger = logging.getLogger('publish.republisher')

SLEEP_BETWEEN_CHECKS = 60  # seconds
ACCEPTED_DELTA_FOR_PUBLISHING = datetime.timedelta(minutes=10)

LIFETIME_SYNTAX_REGEX = r'(?:(\d+)(h|m|s)(?!.*\2)\s?)'
LIFETIME_SYNTAX_CHECK_REGEX = f'^{LIFETIME_SYNTAX_REGEX}+?$'
LIFETIME_MAPPING = {
    'h': 'hours',
    'm': 'minutes',
    's': 'seconds',
}


class PublishingDatabase:

    def __init__(self, data: dict, path: typing.Optional[pathlib.Path] = None):
        self.data = data
        self.path = path
        self.data_changed = False

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, key, value):
        self.data[key] = value

    def published(self, repo) -> None:
        self.data[repo.name] = datetime.datetime.now()
        self.data_changed = True

    def should_repo_publish(self, repo) -> bool:
        if repo.name not in self.data:
            return True

        now_diff = datetime.datetime.now() - self.data[repo.name]
        lifetime = convert_lifetime(repo.ipns_lifetime)

        return now_diff >= (lifetime - ACCEPTED_DELTA_FOR_PUBLISHING)

    def save(self):
        if self.path is None:
            logging.warning('No path specified for PublishingDatabase to save the db to')
            return

        with self.path.open('wb') as f:
            pickle.dump(self.data, f)

        self.data_changed = False

    @classmethod
    def load(cls):
        path = get_data_dir() / 'republishing_db.pickle'

        if not path.exists():
            return cls({}, path)

        logging.info(f'Loading published database from: {path}')
        with path.open('rb') as f:
            data = pickle.load(f)

        logging.debug(f'Loaded data: {data}')
        return cls(data, path)


def get_data_dir():
    path = pathlib.Path(appdirs.user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)

    return path


def convert_lifetime(value: str) -> datetime.timedelta:
    if re.match(LIFETIME_SYNTAX_CHECK_REGEX, value, re.IGNORECASE) is None:
        raise exceptions.PublishingException('Unknown lifetime syntax!')

    matches = re.findall(LIFETIME_SYNTAX_REGEX, value, re.IGNORECASE)
    base = datetime.timedelta()
    for match in matches:
        unit = LIFETIME_MAPPING[match[1].lower()]

        base += datetime.timedelta(**{unit: int(match[0])})

    return base


def republishing(db: PublishingDatabase, iterations: typing.Optional[int] = None):
    config = config_module.Config.get_instance()

    while iterations is None or iterations > 0:
        for repo in config.repos.values():
            if repo.republish and db.should_repo_publish(repo):
                logger.info(f'Publishing repo {repo.name}')
                repo.publish_name()
                db.published(repo)

        if db.data_changed:
            db.save()
        time.sleep(SLEEP_BETWEEN_CHECKS)

        if iterations is not None:
            iterations -= 1


def start_publishing():
    try:
        db = PublishingDatabase.load()
        republishing(db)
    except KeyboardInterrupt:
        logging.info('Received SIGINT, terminating republisher service')


if __name__ == '__main__':
    start_publishing()
