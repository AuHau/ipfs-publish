import datetime
import time

import pytest
from publish import republisher, exceptions, config as config_module
from .. import factories


class TestPublishingDatabase:
    def test_should_publish(self):
        repo = factories.RepoFactory(republish=True, ipns_lifetime='30m')
        db_data = {}
        db = republisher.PublishingDatabase(db_data)
        lifetime_delta = datetime.timedelta(minutes=30)

        assert db.should_repo_publish(repo) is True

        db_data[repo.name] = datetime.datetime.now()
        assert db.should_repo_publish(repo) is False

        # Should be still before the republishing window
        db_data[repo.name] = datetime.datetime.now() - \
                             (lifetime_delta - republisher.ACCEPTED_DELTA_FOR_PUBLISHING - datetime.timedelta(minutes=1))
        assert db.should_repo_publish(repo) is False

        db_data[repo.name] = datetime.datetime.now() - lifetime_delta
        assert db.should_repo_publish(repo) is True

    def test_published(self):
        repo = factories.RepoFactory(republish=True, ipns_lifetime='30m')
        db_data = {}
        db = republisher.PublishingDatabase(db_data)

        db.published(repo)
        assert repo.name in db_data
        assert db.data_changed is True


convert_lifetime_testset = (
    ('1h', datetime.timedelta(hours=1)),
    ('1m', datetime.timedelta(minutes=1)),
    ('1s', datetime.timedelta(seconds=1)),
    ('1h1m1s', datetime.timedelta(hours=1, minutes=1, seconds=1)),
)


class TestConvertLifetime:

    @pytest.mark.parametrize(('lifetime_string', 'expected_timedelta'), convert_lifetime_testset)
    def test_basic(self, lifetime_string, expected_timedelta):
        assert republisher.convert_lifetime(lifetime_string) == expected_timedelta

    def test_non_supported(self):
        with pytest.raises(exceptions.PublishingException):
            republisher.convert_lifetime('1ms')


class TestRepublishing:

    def test_basic(self, mocker):
        db = republisher.PublishingDatabase({})
        config: config_module.Config = factories.ConfigFactory()
        repo1 = factories.RepoFactory(config=config, republish=True, ipns_lifetime='30m')
        repo2 = factories.RepoFactory(config=config, ipns_lifetime='10m')
        config.repos[repo1.name] = repo1
        config.repos[repo2.name] = repo2

        mocker.patch.object(time, 'sleep')
        time.sleep.return_value = None
        mocker.patch.object(config_module.Config, 'get_instance')
        config_module.Config.get_instance.return_value = config

        republisher.republishing(db, iterations=2)

        assert repo1.name in db.data
        assert repo2.name not in db.data

