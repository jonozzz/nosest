'''
Created on Mar 28, 2018

@author: jono
'''
import sys
import os

PATH = None
SITE_PACKAGES = 'lib/python2.7/site-packages'


class LookHere(object):

    def __init__(self, *args, **kwargs):
        self.to_pop = args
        self.paths = kwargs
        self.old = None
        self.inserts = 0

    def __enter__(self):
        if PATH is None:
            raise RuntimeError('Please configure the side-by-side path first.')
        self.old = sys.modules.copy()
        for module in set(sys.modules):
            for p in self.to_pop:
                if module.startswith(p):
                    sys.modules.pop(module)
        for k, v in self.paths.items():
            sys.path.insert(0, os.path.join(PATH, k, v, SITE_PACKAGES))
            # LOG.info(os.path.join(PATH, k, v, SITE_PACKAGES))
            self.inserts += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        map(sys.modules.pop, set(sys.modules) - set(self.old))
        sys.modules.update(self.old)
        for _ in range(self.inserts):
            sys.path.pop(0)


class Plugin(object):
    """
    Allow multiple versions of packages to be installed side by side and imported
    easily with a context manger:

    with LookHere(openssl='1.0.1'):
        import OpenSSL

    """
    name = "sidebyside"

    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc'):
            self.options = config._tc.plugins.sidebyside
            self.enabled = self.options.enabled
        else:
            self.enabled = False

    def pytest_sessionstart(self, session):
        if self.enabled is False:
            return

        global PATH
        PATH = self.options.path


def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'sidebyside-plugin')
