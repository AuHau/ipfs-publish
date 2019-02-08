import pathlib

import factory

from publish import config as config_module, publishing


class PublishFactory(factory.Factory):
    class Meta:
        strategy = factory.BUILD_STRATEGY


class ConfigFactory(PublishFactory):
    path = pathlib.Path(__file__).parent / 'configs' / 'basic.toml'

    class Meta:
        model = config_module.Config


class RepoFactory(PublishFactory):
    config = factory.SubFactory(ConfigFactory)
    name = factory.Faker('slug')
    git_repo_url = factory.Faker('url')
    secret = factory.Faker('pystr', min_chars=20, max_chars=20)

    class Meta:
        model = publishing.GenericRepo


class GithubRepoFactory(RepoFactory):
    class Meta:
        model = publishing.GithubRepo
