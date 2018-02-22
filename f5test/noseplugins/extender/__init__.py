'''
Created on Jul 24, 2014

@author: jono
'''
import importlib
import inspect
import logging
import pkgutil
import sys
import traceback

from nose.plugins.base import Plugin
from nose.plugins import manager

LOG = logging.getLogger(__name__)
PLUGIN_NAME = 'reporting'


# TODO: Patch this directly into nose upstream.
def simple(self, *arg, **kw):
    """Call all plugins, returning the first non-None result.
    """
    for p, meth in self.plugins:
        # Unfortunate backward compatibility :(
        if inspect.ismethod(meth) and meth.func_code.co_argcount - 1 != len(arg):
            arg = arg[:meth.func_code.co_argcount - 1]
        try:
            result = meth(*arg, **kw)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            if getattr(meth, 'critical', False):
                raise
            result = None
            err = sys.exc_info()
            tb = ''.join(traceback.format_exception(*err))
            LOG.critical('Exception in plugin %s: %s', p, tb)
        if result is not None:
            return result
manager.PluginProxy.simple = simple


class ExtendedPlugin(Plugin):
    score = 500

    def options(self, parser, env):
        pass

    def configure(self, options, noseconfig):
        # Auto-enable plugin when --with_<name> argument is passed
        args = (noseconfig.options, 'with_%s' % self.name)
        if hasattr(*args):
            self.enabled = bool(getattr(*args))

        if options.enabled is not None:
            self.enabled = bool(options.enabled)
        if options.get('score'):
            self.score = int(options.score)
        self.options = options
        self.noseconfig = noseconfig


class Extender(Plugin):
    """
    Gather data about tests and store it in the "reporting" container.
    Enabled by default.
    """
    enabled = True
    name = "extender"
    score = 500

    def __init__(self):
        super(Extender, self).__init__()
        # parent = importlib.import_module(__name__.rsplit('.', 1)[0])
        self.plugins = []

        # Find and load all our plugins and attach them to nose
        # parent = importlib.import_module(__name__.rsplit('.', 1)[0])
        parent = importlib.import_module(__name__)
        for _, module_name, _ in pkgutil.walk_packages(parent.__path__):
            try:
                module = importlib.import_module('%s.%s' % (parent.__name__, module_name))
            except ImportError:
                #LOG.warning('Unable to load plugin %s. Possible dependency issue.', module_name)
                err = sys.exc_info()
                tb = ''.join(traceback.format_exception(*err))
                print('Unable to load plugin {} ({})'.format(module_name, tb))
                continue
            for _, klass in inspect.getmembers(module, lambda x: inspect.isclass(x)):
                if issubclass(klass, ExtendedPlugin) and klass is not ExtendedPlugin:
                    plugin = klass()
                    self.plugins.append(plugin)

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--no-extender', action='store_true',
                          dest='no_extender', default=False,
                          help="Disable this plugin. (default: no)")

        for plugin in self.plugins:
            plugin.addOptions(parser, env)

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        from ...base import Options as O
        from ...interfaces.config import ConfigInterface

        self.options = options
        if options.no_extender:
            self.enabled = False

        with ConfigInterface() as cfgifc:
            plugin_options = cfgifc.api.plugins or O()

        for plugin in self.plugins:
            LOG.debug('Configuring plugin: %s', plugin.name)
            plugin.configure(plugin_options.get(plugin.name) or O(), noseconfig)
            noseconfig.plugins.addPlugin(plugin)

        noseconfig.plugins.sort()
