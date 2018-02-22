'''
Created on Oct 27, 2015

@author: jono
'''
import logging

from f5test.interfaces.testcase import ContextHelper
import f5test.commands.shell as SCMD

from . import ExtendedPlugin


LOG = logging.getLogger(__name__)
TIMEOUT = 300


class CoresStop(ExtendedPlugin):
    """
    Open a SSH connection and keep it alive during the entire run.
    Check for existence of cores on the default DUT after each test.
    If found, raise the shouldStop flag and stop end the test execution.

    Caveats:
    If all tests up until that point passed the run will show a 100% pass rate.
    Tests that were not run will not show up in the report
    """
    enabled = False
    score = 501  # Needs to be higher than the other report plugins that depend on it

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--stop-on-core', action='store_true',
                          dest='stop_on_core', default=False,
                          help="Enable stopping when first core is found. (default: no)")

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        super(CoresStop, self).configure(options, noseconfig)
        self.context = ContextHelper()
        self.enabled = noseconfig.options.stop_on_core

    def afterTest(self, test):
        sshifc = self.context.get_ssh()
        if SCMD.ssh.cores_exist(ifc=sshifc):
            LOG.error('Cores found after %s.' % test.id())
            self.result.shouldStop = True

    def prepareTestResult(self, result):
        self.result = result

    def finalize(self, result):
        self.context.teardown()
