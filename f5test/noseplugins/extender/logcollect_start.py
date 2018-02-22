'''
Created on Sep 4, 2014

This plugin collects logs from all devices used during a failed/errored test.

IT: The MemoryHandler needs a lot of rework.

@author: jono
'''
import base64
import codecs
from inspect import getmodule
import logging
import os
import sys
import threading
import traceback
import re

try:
    import jinja2
except ImportError:
    jinja2 = None

from nose.plugins import logcapture
from nose.plugins.attrib import get_method_attr
from nose.plugins.base import Plugin
from nose.plugins.skip import SkipTest
from nose.suite import ContextSuite
import yaml

from . import ExtendedPlugin
from ...utils.stages import StageError
from ...interfaces.config.core import CFG_SESSION

LOG = logging.getLogger(__name__)
STDOUT = logging.getLogger('stdout')
CONSOLE_LOG = 'console.log'
SESSION_LOG = 'session.log'
TEST_HTML = 'test_log.html'
SAFE_LEVEL = 1
HREF_TMPL = r'<a href="https://indexing/source/xref/emtest/\2#\3">\1</a>'
INC_TEST_ATTRIBUTES = ('author', 'rank')
CONTEXT_NAME = __name__


def get_test_meta(test, attribs=INC_TEST_ATTRIBUTES, as_dict=False):
    # I wish there was a better way to dump a whole "attr container",
    # but the attr plugin mixes the attrs with the test object attrs.
    if not attribs:
        attribs = []
    klass = test.context if isinstance(test, ContextSuite) else test.test
    if hasattr(klass, '_testMethodName'):
        method = getattr(klass, klass._testMethodName, None)
    else:
        method = None

    if as_dict:
        return dict((k, get_method_attr(method, klass, k, 'N/A'))
                    for k in attribs)
    return ["%s: %s" % (k, get_method_attr(method, klass, k, 'N/A'))
            for k in attribs]


class DummyPlugin(Plugin):
    def options(self, parser, env):
        pass
logcapture.LogCapture = DummyPlugin


class MyFileHandler(logging.FileHandler):

    def __init__(self, filename, mode='a', encoding=None, delay=0, filters=None):
        super(MyFileHandler, self).__init__(filename, mode, encoding, delay)
        self.filterset = logcapture.FilterSet(filters or [])

    def filter(self, record):
        if self.filterset.allow(record.name):
            return super(MyFileHandler, self).filter(record)


class RawMemoryHandler(logcapture.MyMemoryHandler):
    TEMPLATE = 'log_html.tmpl'

    def __init__(self, level=logging.NOTSET):
        logging.Handler.__init__(self, level)
        self.buffer = []
        if jinja2:
            loader = jinja2.PackageLoader(__package__)
            env = jinja2.Environment(loader=loader, autoescape=True)
            self.template = env.get_template(self.TEMPLATE)

    def filter(self, record):
        return logging.Handler.filter(self, record)

    def emit(self, record):
        self.buffer.append(record)

    def commit(self, filename):
        if jinja2:
            text = self.template.render(buffer=self.buffer)
            with open(filename, "wt") as f:
                f.write(text.encode('utf-8'))


class LoggingProxy(object):
    """Forward file object to :class:`logging.Logger` instance.

    :param logger: The :class:`logging.Logger` instance to forward to.
    :param loglevel: Loglevel to use when writing messages.

    """
    closed = False
    loglevel = logging.INFO
    _thread = threading.local()

    def __init__(self, logger, loglevel=None):
        self.logger = logger
        self.loglevel = loglevel or self.logger.level or self.loglevel
        self.buffer = []

    def write(self, data):
        self.buffer.append(data.strip())
        if data[-1] == '\n':
            self.flush()

    def writeln(self, arg=None):
        if arg:
            self.write(arg)
        self.flush()

    def writelines(self, sequence):
        """`writelines(sequence_of_strings) -> None`.

        Write the strings to the file.

        The sequence can be any iterable object producing strings.
        This is equivalent to calling :meth:`write` for each string.

        """
        for part in sequence:
            self.write(part)

    def flush(self):
        """This object is not buffered so any :meth:`flush` requests
        are ignored."""
        if self.buffer:
            data = ''.join(self.buffer)
            self.logger.log(self.loglevel, data)
            self.buffer[:] = []

    def close(self):
        """When the object is closed, no write requests are forwarded to
        the logging object anymore."""
        self.flush()
        self.closed = True

    def isatty(self):
        """Always returns :const:`False`. Just here for file support."""
        return False

    def fileno(self):
        return None


class LogCollect(ExtendedPlugin):
    """
    Log Collector plugin. Enabled by default. Disable with ``--no-logcollect``.
    Upon a test failure this plugin iterates through each open interface and
    tries to collect troubleshooting data, like screenshots and log files.
    """
    enabled = True
    score = 540
    logformat = '%(asctime)s - %(levelname)8s [%(threadName)s] %(name)s:%(lineno)d - %(message)s'
    env_opt = 'NOSE_NOLOGCAPTURE'
    logdatefmt = None
    clear = False
    filters = []

    def options(self, parser, env):
        """Register commandline options.
        """
        parser.add_option('--console-redirect', action='store_true',
                          default=False,
                          help="Enable redirection of console output to a console.log.")
        parser.add_option('--no-logcollect', action='store_true',
                          dest='no_logcollect', default=False,
                          help="Disable LogCollect.")

    def configure(self, options, conf):
        """
        Configure plugin. Skip plugin is enabled by default.
        """
        from ...interfaces.testcase import ContextHelper
        import f5test.commands.ui as UI
        import f5test.commands.shell.ssh as SSH
        self.UI = UI
        self.SSH = SSH

        if not self.can_configure:
            return
        self.conf = conf
        self.enabled = False if getattr(conf.options, 'no_logcollect', False) else True

        self.context = ContextHelper(CONTEXT_NAME)
        self.logformat = options.format or self.logformat
        self.logdatefmt = options.datefmt or self.logdatefmt
        self.clear = options.get('clear') or self.clear
        self.loglevel = options.level or 'NOTSET'
        if options.filters:
            self.filters = options.filters
        self.blocked_contexts = {}

    def _get_session_dir(self):
        cfgifc = self.context.get_config()
        path = cfgifc.get_session().path

        if path and not os.path.exists(path):
            oldumask = os.umask(0)
            os.makedirs(path)
            os.umask(oldumask)

        return path

    def setOutputStream(self, stream):
        if not self.conf.options.console_redirect:
            return

        logger = logging.getLogger('_console_')
        logger.disabled = False

        log_dir = self._get_session_dir()
        assert log_dir is not None
        console_filename = os.path.join(log_dir, CONSOLE_LOG)

        logformat = '%(asctime)s - %(message)s'
        fmt = logging.Formatter(logformat, self.logdatefmt)
        handler = logging.FileHandler(console_filename)
        handler.setFormatter(fmt)

        for x in logger.handlers:
            logger.removeHandler(x)
        logger.addHandler(handler)

        def findCaller():
            """
            Modified findCaller() that digs down in the frame stack until it
            finds the method that wrote to the stdout/stderr.
            """
            f = logging.currentframe()
            if f is not None:
                f = f.f_back
            rv = "(unknown file)", 0, "(unknown function)"

            if __file__[-4:].lower() in ['.pyc', '.pyo']:
                _thisfile = __file__[:-4] + '.py'
            else:
                _thisfile = __file__
            _thisfile = os.path.normcase(_thisfile)

            while hasattr(f, "f_code"):
                co = f.f_code
                filename = os.path.normcase(co.co_filename)
                if filename in (logging._srcfile, _thisfile):
                    f = f.f_back
                    continue
                rv = (co.co_filename, f.f_lineno, co.co_name)
                module = getmodule(f)
                if module:
                    logger.name = module.__name__
                break
            return rv

        logger.findCaller = findCaller
        sl = LoggingProxy(logger, logging.INFO)
        sys.stdout = sl

        sl = LoggingProxy(logger, logging.ERROR)
        sys.stderr = sl

        proxy = LoggingProxy(logger)
        return proxy

    def setupLoghandler(self):
        # setup our handler with root logger
        root_logger = logging.getLogger()
        if self.clear:
            if hasattr(root_logger, "handlers"):
                for handler in root_logger.handlers:
                    root_logger.removeHandler(handler)
            for logger in logging.Logger.manager.loggerDict.values():  # @UndefinedVariable
                if hasattr(logger, "handlers"):
                    for handler in logger.handlers:
                        logger.removeHandler(handler)
        # make sure there isn't one already
        # you can't simply use "if self.handler not in root_logger.handlers"
        # since at least in unit tests this doesn't work --
        # LogCapture() is instantiated for each test case while root_logger
        # is module global
        # so we always add new MyMemoryHandler instance
        for handler in root_logger.handlers[:]:
            if isinstance(handler, logcapture.MyMemoryHandler):
                root_logger.handlers.remove(handler)
        root_logger.addHandler(self.handler_html)
        # to make sure everything gets captured
        loglevel = getattr(self, "loglevel") or "NOTSET"
        root_logger.setLevel(getattr(logging, loglevel))

    def formatLogRecords(self):
        return self.handler_html.buffer

    def start(self):
        self.handler_html = RawMemoryHandler()
        self.setupLoghandler()

    def begin(self):
        # setup our handler with root logger
        cfgifc = self.context.get_config()
        self.start()
        root_logger = logging.getLogger()

        log_dir = self._get_session_dir()
        if not log_dir:
            return

        run_filename = os.path.join(log_dir, SESSION_LOG)

        config = dict((k, v) for k, v in cfgifc.open().items() if k != CFG_SESSION)
        filename = os.path.join(log_dir, 'config.yaml')
        with open(filename, "wt") as f:
            yaml.dump(config, f, indent=4, width=1024, default_flow_style=False)

        fmt = logging.Formatter(self.logformat, self.logdatefmt)
        handler = MyFileHandler(run_filename, filters=self.filters)
        handler.setFormatter(fmt)
        root_logger.addHandler(handler)

        session = cfgifc.get_session()
        url = session.get_url()
        if url:
            STDOUT.info('Session URL: %s', url)
        STDOUT.info('Watch the progress of this run with: tail -f %s/session.log or edit logging.conf to display INFO level at the console.', log_dir)
    begin.critical = True

    def _get_or_create_dirs(self, name, root=None):
        if root is None:
            root = self._get_session_dir()

        created = False
        path = os.path.join(root, name)

        # Windows-based NAS doesn't support :'s in names
        path = path.replace(':', '@')
        if not os.path.exists(path):
            oldumask = os.umask(0)
            os.makedirs(path)
            os.umask(oldumask)
            created = True

        return path, created

    def _collect_forensics(self, test, err, context=None):
        """Collects screenshots and logs."""
        try:
            from ...interfaces.selenium import SeleniumInterface
            from selenium.common.exceptions import WebDriverException
        except ImportError:
            WebDriverException = SeleniumInterface = None
        from ...interfaces.ssh import SSHInterface
        from ...interfaces.subprocess import ShellInterface
        from ...interfaces.icontrol import IcontrolInterface
        from ...interfaces.icontrol.em import EMInterface
        from ...interfaces.rest import RestInterface
        from ...interfaces.config import ConfigInterface
        from ...interfaces.testcase import (InterfaceHelper,
                                            INTERFACES_CONTAINER,
                                            LOGCOLLECT_CONTAINER)
        from ...base import Interface

        if context:
            blocked_tests = self.blocked_contexts.setdefault(context, [])
            test_name = context.id()

            # print (test, err, context)
            # We already collected logs for this context
            if blocked_tests:
                return

            blocked_tests.append((test, err))
        else:
            test_name = test.id()

        ih = InterfaceHelper()
        ih._setup(test_name.split(':', 1)[0])
        interfaces = ih.get_container(container=INTERFACES_CONTAINER).values()
        extra_files = ih.get_container(container=LOGCOLLECT_CONTAINER)

        # Disregard skipped tests
        if issubclass(err[0], SkipTest):
            return

        config = self.context.get_config().open()
        if config is None:
            LOG.warn('config not available')
            return

        if not config.paths or not config.paths.logs:
            LOG.warn('logs path not defined')
            return

        # Save the test log
        test_root, created = self._get_or_create_dirs(test_name)
        if not created:
            i = 1
            while not created:
                test_root, created = self._get_or_create_dirs("%s.%d" % (test_name, i))
                i += 1
        records = self.formatLogRecords()
        self.context.set_data('test_root', test_root)
        if records:
            test_meta = get_test_meta(test)

            tmp = "\nTest attributes:\n" + '\n'.join(test_meta) + '\n'
            LOG.log(SAFE_LEVEL, tmp)

            tmp = ''
            if err[0] is StageError:
                for line in err[1].format_errors():
                    tmp += line
            else:
                tmp += ''.join(traceback.format_exception(*err))
                tmp = re.sub(r'(File ".*?/((?:tests|tests-latest|src)/.*?\.py)", line (\d+))', HREF_TMPL, tmp)
            LOG.log(SAFE_LEVEL, tmp.decode('utf-8'))

        filename = os.path.join(test_root, TEST_HTML)
        self.handler_html.commit(filename)

        # Sort interfaces by priority.
        interfaces.sort(key=lambda x: x._priority if hasattr(x, '_priority')
                        else 0)

        # Tests may define extra files to be picked up by the logcollect plugin
        # in case of a failure.
        LOG.debug('Collecting logs...')
        for item, local_name in extra_files.iteritems():
            if isinstance(item, tuple):
                ifc, src = item
                assert isinstance(ifc, (SSHInterface, ShellInterface))
            else:
                ifc = ShellInterface()
                src = item

            was_opened = ifc.is_opened()
            if not was_opened:
                ifc.open()

            try:
                address = ifc.address
                log_root, _ = self._get_or_create_dirs(address, test_root)
                if local_name is None:
                    local_name = os.path.basename(src)
                ifc.api.get(src, os.path.join(log_root, local_name))
            except IOError, e:
                LOG.error("Could not copy file '%s' (%s)", src, e)
            finally:
                if not was_opened:
                    ifc.close()

        if WebDriverException and issubclass(err[0], WebDriverException) and err[1].screen:
            filename = os.path.join(test_root, 'screenshot.png')
            with codecs.open(filename, "w") as f:
                f.write(base64.b64decode(err[1].screen.encode('ascii')))

        visited = dict(ssh=set(), selenium=set())
        # Collect interface logs
        for interface in interfaces:
            if not isinstance(interface, Interface):
                continue

            if isinstance(interface, ConfigInterface):
                continue

            if not interface.is_opened():
                continue

            sshifcs = []
            if SeleniumInterface and isinstance(interface, SeleniumInterface):
                try:
                    for window in interface.api.window_handles:
                        credentials = interface.get_credentials(window)

                        if credentials.device:
                            address = credentials.device.get_address()
                        else:
                            address = credentials.address or window

                        if address not in visited['selenium']:
                            log_root, _ = self._get_or_create_dirs(address, test_root)
                            try:
                                self.UI.common.screen_shot(log_root, window=window,
                                                           ifc=interface)
                            except Exception, e:
                                LOG.error('Screenshot faied: %s', e)

                            if credentials.device:
                                sshifcs.append(SSHInterface(device=credentials.device))
                except:
                    err = sys.exc_info()
                    tb = ''.join(traceback.format_exception(*err))
                    LOG.debug('Error taking screenshot. (%s)', tb)
                finally:
                    try:
                        interface.api.switch_to_window('')
                    except:
                        LOG.debug('Error switching to main window.')

            elif isinstance(interface, SSHInterface):
                sshifcs.append(SSHInterface(device=interface.device,
                                            address=interface.address,
                                            username=interface.username,
                                            password=interface.password,
                                            key_filename=interface.key_filename))

            elif isinstance(interface, (IcontrolInterface, EMInterface,
                                        RestInterface)):
                if interface.device and interface.device.address == interface.address:
                    sshifcs.append(SSHInterface(device=interface.device))

            else:
                LOG.debug('Skip collection from interface: %s', interface)

            for sshifc in sshifcs:
                try:
                    with sshifc:
                        address = sshifc.address
                        if address not in visited['ssh']:
                            log_root, _ = self._get_or_create_dirs(address, test_root)
                            LOG.debug('Collecting logs from %s', address)
                            try:
                                version = self.SSH.get_version(ifc=sshifc)
                                self.SSH.collect_logs(log_root, ifc=sshifc,
                                                      version=version)
                            except Exception, e:
                                LOG.error('Collecting logs failed: %s', e)
                            visited['ssh'].add(address)
                except:
                    err = sys.exc_info()
                    tb = ''.join(traceback.format_exception(*err))
                    LOG.debug('Error collecting logs. (%s)', tb)

        del interfaces[:]

    def handleFailure(self, test, err):
        self._collect_forensics(test, err)

    def handleError(self, test, err):
        self._collect_forensics(test, err)

    def handleBlocked(self, test, err, context):
        self._collect_forensics(test, err, context)

    # These are needed to override LogCapture's behavior
    def formatError(self, test, err):
        return err

    def formatFailure(self, test, err):
        return err

    def startContext(self, context):
        """Clear buffers and handlers before test.
        """
        self.handler_html.truncate()

    def afterTest(self, test):
        sys.stdout.flush()
        sys.stderr.flush()
        self.handler_html.truncate()

    def _logging_leak_check(self, root_logger):
        LOG.debug("Logger leak check...ugh!")
        loggers = [('*root*', root_logger)] + root_logger.manager.loggerDict.items()
        loggers.sort(key=lambda x: x[0])
        for name, logger in loggers:
            LOG.debug("%s:%s", name, logger)
            if hasattr(logger, 'handlers'):
                for handler in logger.handlers:
                    LOG.debug(" %s", handler)

    def finalize(self, result):
        self.context.teardown()
