
import pytest
from ..interfaces.config import ConfigLoader, ConfigInterface
from ..interfaces.testcase import ContextHelper


def pytest_addoption(parser):
    group = parser

    def add_option_ini(option, dest, default=None, type=None, **kwargs):
        parser.addini(dest, default=default, type=type,
                      help='default value for ' + option)
        group.addoption(option, dest=dest, **kwargs)

    add_option_ini(
        '--tc',
        dest='tc', action='store',
        default='test_config.yaml',
        help='test config yaml')


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    if config.option.tc:
        loader = ConfigLoader(config.option.tc)
        cfgifc = ConfigInterface(loader=loader)
        cfgifc.set_global_config()
        config._tc = cfgifc.open()

        # Override config args
        for key, value in list(config._tc.get('pytest', {}).items()):
           setattr(config.option, key, value)


def pytest_unconfigure(config):
    if hasattr(config, '_tc'):
        del config._tc


@pytest.fixture(scope='session')
def context(request):
    with ContextHelper() as c:
        yield c


@pytest.fixture(scope='module')
def module_context(request):
    with ContextHelper(request.node.nodeid) as c:
        yield c


@pytest.fixture(scope='class')
def class_context(request):
    with ContextHelper(request.node.nodeid) as c:
        yield c


@pytest.fixture(scope='function')
def function_context(request):
    with ContextHelper(request.node.nodeid) as c:
        yield c
