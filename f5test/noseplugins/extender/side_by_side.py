'''
Created on Mar 16, 2018

@author: jono
'''

from . import ExtendedPlugin
import sys
import os
import logging

LOG = logging.getLogger(__name__)
PATH = None
SITE_PACKAGES = 'lib/python2.7/site-packages'


class LookHere(object):

    def __init__(self, *args, **kwargs):
        self.to_pop = args
        self.paths = kwargs
        self.old = None
        self.inserts = 0

    def __enter__(self):
        LOG.debug(PATH)
        if PATH is None:
            raise RuntimeError('Please configure the side-by-side path first.')
        self.old = sys.modules.copy()
        for module in set(sys.modules):
            for p in self.to_pop:
                if module.startswith(p):
                    sys.modules.pop(module)
        for k, v in list(self.paths.items()):
            sys.path.insert(0, os.path.join(PATH, k, v, SITE_PACKAGES))
            # LOG.info(os.path.join(PATH, k, v, SITE_PACKAGES))
            self.inserts += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        list(map(sys.modules.pop, set(sys.modules) - set(self.old)))
        sys.modules.update(self.old)
        for _ in range(self.inserts):
            sys.path.pop(0)


class SideBySide(ExtendedPlugin):
    """
    Allow multiple versions of packages to be installed side by side and imported
    easily with a context manger:

    with LookHere(openssl='1.0.1'):
        import OpenSSL

    """
    enabled = False
    name = "sidebyside"

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--sidebyside-path', dest='sidebyside_path')

    def configure(self, options, noseconfig):
        super(SideBySide, self).configure(options, noseconfig)
        if self.enabled:
            global PATH
            PATH = noseconfig.options.sidebyside_path or options.path
