"""
Created on Jan 25, 2018

@author: jono
"""
import logging
import re

from ...utils.convert import to_bool
from . import ExtendedPlugin
from nose.case import FunctionTestCase
from nose.plugins.attrib import AttributeSelector
import os.path
import sys

STDOUT = logging.getLogger('stdout')
ITE_METADATA = '_ite_metadata'


class Dummy(object):
    pass


class ITE(ExtendedPlugin):
    """
    Log when the session has started (after all plugins are configured).
    """
    score = 1000

    def options(self, parser, env):
        """Register command line options."""
        parser.add_option('--with-ite', action='store_true',
                          dest='with_ite', default=False,
                          help="Enable ITE mockup. (default: no)")

    def configure(self, options, noseconfig):
        super(ITE, self).configure(options, noseconfig)

        if not self.enabled:
            return

        noseconfig.testMatch = re.compile('$^')
        self.attr_plugin = AttributeSelector()
        self.attr_plugin.configure(noseconfig.options, noseconfig)

        if os.getuid() == 0:
            os.setegid(self.options.gid)
            os.seteuid(self.options.uid)

    def begin(self):
        STDOUT.info('ITE emulation plugin starting...')
        for path in self.options.paths:

            if path.startswith('/'):
                p = path
            else:
                p = os.path.join(os.path.dirname(__file__), path)

            # Pull any existing paths to make sure our mocks come first.
            if p in sys.path:
                sys.path.remove(p)
            sys.path.append(p)

    def mdparse(self, source):
        metadata_regex = re.compile(r"""
                                    ^\#\s?@         # Metadata marker
                                    (\w+):       # Name of metadata key
                                    \s*?(.*?)\n  # The value of the metadata
                                    """, re.VERBOSE | re.MULTILINE)
        tokens = [(key.strip(), val.strip()) for key, val in
                  metadata_regex.findall(source)]
        return tokens

    def loadTestsFromModule(self, module, path=None):
        if not os.path.isfile(path):
            return
        with open(path) as f:
            source = f.read()
            tokens = dict(self.mdparse(source))

        if tokens:
            def test_eval():
                g = globals()
                g['__name__'] = '__main__'
                g['__file__'] = path
                g['__path__'] = [path]
                need_root = to_bool(tokens.get('Sudo', False))
                try:
                    #exec(source, g)
                    if need_root and os.getuid() == 0:
                        os.setegid(0)
                        os.seteuid(0)
                    else:
                        STDOUT.warning('This test requires root privileges.')
                    exec(compile(source, path, 'exec'), g)
                except SystemExit as e:
                    from tcutils.base import PASS
                    assert e.code in (None, PASS), e.code
                finally:
                    if need_root and os.getuid() == 0:
                        os.setegid(self.options.gid)
                        os.seteuid(self.options.uid)
            module.__module__ = module.__name__
            module.compat_func_name = 'main'
            f = FunctionTestCase(test_eval, descriptor=module)
            dummy = Dummy()
            for k, v in tokens.items():
                setattr(dummy, k, v)
            setattr(module, ITE_METADATA, dummy)
            if not self.attr_plugin.enabled:
                return [f]
            if self.attr_plugin.validateAttrib(dummy) is None:
                return [f]

#     def loadTestsFromName(self, name, module=None, importPath=None):
#         with open(name) as f:
#             source = f.read()
#             tokens = self.mdparse(source)
# 
#         if tokens:
#             def test():
#                 print("yup!")
#             return [FunctionTestCase(test, descriptor=name)]

#     def loadTestsFromNames(self, names, module=None):
#         pass
