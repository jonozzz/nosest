import pytest
from ..interfaces.config import ConfigLoader, ConfigInterface
from ..interfaces.testcase import ContextHelper
import logging


logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)

def pytest_addoption(parser):
    parser.addoption(
        '--tc',
        action='store',
        #default='pytest.yaml',
        type=str,
        help='test config')


# class UnexpectedError(Exception):
#     pass


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    if config.option.tc:
        loader = ConfigLoader(config.option.tc)
        cfgifc = ConfigInterface(loader=loader)
        cfgifc.set_global_config()
        config._tc = cfgifc.open()


def pytest_unconfigure(config):
    if hasattr(config, '_tc'):
        del config._tc


@pytest.fixture(scope='session', autouse=True)
def context():
    with ContextHelper() as c:
        yield c
