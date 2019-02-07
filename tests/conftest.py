import pathlib

import pytest

from publish import config as config_module


@pytest.fixture
def config():
    path = pathlib.Path(__file__) / '..' / '..' / 'configs' / 'basic.toml'
    return config_module.Config(path)
