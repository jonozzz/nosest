from nose.plugins.base import Plugin
from nose.util import tolist
from ..interfaces.config import ConfigLoader, ConfigInterface
from ..interfaces.testcase import THREAD_STORAGE
from ..interfaces.config.driver import Signals
import ast
import os
import atexit


def print_open_contexts():
    if THREAD_STORAGE._attrs:
        print("Found contexts that have not been closed:")
        print(THREAD_STORAGE._attrs)


def do_nothing(*args, **kwargs):
    return


class TestConfig(Plugin):
    """
    Test Config plugin. Enabled by when ``--tc-file`` is passed. Parses a config
    file (usually in YAML format) and stores it in a global variable as a
    dictionary. Use ConfigInterface to read/write from/to this config
    variable.
    """
    enabled = False
    name = "test_config"
    # High score means further head in line.
    score = 550

    env_opt = "NOSE_TEST_CONFIG_FILE"

    callbacks = {'on_before_extend': do_nothing,
                 'on_after_extend': do_nothing
                 }

    def options(self, parser, env=os.environ):
        """ Define the command line options for the plugin. """
        parser.add_option(
            "--tc-file", action="store",
            default=env.get(self.env_opt),
            help="Configuration file to parse and pass to tests"
                 " [NOSE_TEST_CONFIG_FILE]")
        parser.add_option(
            "--tc-format", action="store",
            default=env.get('NOSE_TEST_CONFIG_FILE_FORMAT'),
            help="Test config file format, default is: autodetect"
                 " [NOSE_TEST_CONFIG_FILE_FORMAT]")
        parser.add_option(
            "--tc", action="append",
            dest="overrides",
            default=[],
            help="Option:Value specific overrides.")
        parser.add_option(
            "--tc-exact", action="store_true",
            default=False,
            help="Optional: Do not explode periods in override keys to "
                 "individual keys within the config dict, instead treat them"
                 " as config[my.toplevel.key] ala sqlalchemy.url in pylons")
        parser.add_option(
            "--tc-debug-open-contexts", action="store_true", default=False,
            help="For debugging only. Dump any contexts that are still open upon interpreter exit.")

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        if not options.tc_file:
            return

        self.enabled = True
        Plugin.configure(self, options, noseconfig)
        loader = ConfigLoader(options.tc_file, options.tc_format)
        with Signals.on_before_extend.connected_to(self.callbacks['on_before_extend']), \
                Signals.on_after_extend.connected_to(self.callbacks['on_after_extend']):
            cfgifc = ConfigInterface(loader=loader)
        cfgifc.set_global_config()
        config = cfgifc.get_config()

        if options.tc_debug_open_contexts:
            atexit.register(print_open_contexts)

        if options.overrides:
            self.overrides = []
            overrides = set(tolist(options.overrides))
            for override in overrides:
                keys, val = override.split(":", 1)
                # Attempt to convert the string into int/bool/float or default
                # to string
                if val == '':
                    val = None
                else:
                    needquotes = False
                    try:
                        val = ast.literal_eval(val)
                    except ValueError:
                        needquotes = True

                    if needquotes or isinstance(val, basestring):
                        val = '"%s"' % val

                if options.tc_exact:
                    config[keys] = val
                else:
                    ns = ''.join(['["%s"]' % i for i in keys.split(".")])
                    # BUG: Breaks if the config value you're overriding is not
                    # defined in the configuration file already. TBD
                    exec('config%s = %s' % (ns, val))
    configure.critical = True

    def begin(self):
        from ..interfaces.testcase import ContextHelper
        context = ContextHelper()
        context._clear()
        context.set_container()
