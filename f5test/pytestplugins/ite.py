'''
Created on Mar 29, 2018

@author: jono
'''
from __future__ import absolute_import
import pytest
from ..utils.convert import to_bool
from ..base import AttrDict
import logging
import re
import os
import sys


LOG = logging.getLogger(__name__)


def mdparse(source):
    metadata_regex = re.compile(r"""
                                ^\#\s?@         # Metadata marker
                                (\w+):       # Name of metadata key
                                \s*?(.*?)\n  # The value of the metadata
                                """, re.VERBOSE | re.MULTILINE)
    tokens = [(key.strip(), val.strip()) for key, val in
              metadata_regex.findall(source)]
    return tokens


class IteFile(pytest.Module):
    def collect(self):
        f = self.fspath.open()
        try:
            yield IteItem(self.fspath.purebasename, self, f.read())
        finally:
            f.close()


class IteItem(pytest.Function):
    def __init__(self, name, parent, source):
        # Make super constructors happy.
        setattr(parent.obj, name, lambda: None)

        super(IteItem, self).__init__(name, parent)
        self.source = source
        self.tokens = dict(mdparse(source))
        # Turn Metadata into markers
        for name, value in self.tokens.items():
            mark = getattr(pytest.mark, name)(value)
            self.add_marker(mark)

        self.add_marker(getattr(pytest.allure, 'label')('suite', 'ITE'))
        #self.reporter = self.config.pluginmanager.get_plugin('terminalreporter')

    def runtest(self):
        g = globals()
        g['__name__'] = '__main__'
        g['__file__'] = self.fspath.strpath
        g['__path__'] = [self.fspath.strpath]

        need_root = to_bool(self.tokens.get('Sudo', False))
        try:
            if need_root:
                if os.getuid() == 0:
                    os.setegid(0)
                    os.seteuid(0)
                else:
                    #self.reporter.write_line('You need to run `pytest` the as root or else it will fail.')
                    LOG.warn('ITE test "%s" requires root!', self.nodeid)

            exec (compile(self.source, self.fspath.strpath, 'exec'), g)
        except SystemExit as e:
            from tcutils.base import PASS
            assert e.code in (None, PASS), e.code
        finally:
            if need_root and os.getuid() == 0:
                os.setegid(self.options.gid)
                os.seteuid(self.options.uid)

    def reportinfo(self):
        return self.fspath, 0, "ite test: %s" % self.name


class ItePlugin(object):
    """
    Send email report.
    """
    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc'):
            self.options = config._tc.plugins.ite or AttrDict()
            self.enabled = to_bool(self.options.enabled)
        else:
            self.enabled = False
        self.markers = {}

    # def pytest_addoption(self, parser):
    #     parser.addoption(
    #         '--with-ite',
    #         action='store_true',
    #         default=False,
    #         type=bool,
    #         help='look for ITE tests')

    def pytest_sessionstart(self, session):
        if self.enabled is False:
            return

        for path in self.options.paths:

            if path.startswith('/'):
                p = path
            else:
                p = os.path.join(os.path.dirname(__file__), path)

            # Pull any existing paths to make sure our mocks come first.
            if p in sys.path:
                sys.path.remove(p)
            sys.path.append(p)

    def pytest_pycollect_makemodule(self, path, parent):
        with open(path.strpath) as f:
            if mdparse(f.read()):
                return IteFile(path, parent)

        module = pytest.Module(path, parent)
        return module


def pytest_configure(config):
    config.pluginmanager.register(ItePlugin(config), 'ite-plugin')
