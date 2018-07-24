'''
Created on Aug 28, 2014

@author: jono
'''
import inspect
import json
import logging
import os
import traceback
import unittest
import requests

from ...base import Options
from ...utils.convert import json_serial
from . import ExtendedPlugin, PLUGIN_NAME
from ...interfaces.testcase import ContextHelper

LOG = logging.getLogger(__name__)
DEFAULT_FILENAME = 'results.json'
FAIL = 'FAIL'
ERROR = 'ERROR'
PASSED = 'PASSED'
SKIP = 'SKIP'
INCLUDE_ATTR = ['module', 'uimode', 'hamode', 'scenario', 'doc']


class JsonReporter(ExtendedPlugin):
    """
    Generate a json report for the overall test run.
    Data exposed:
    - test runner (ip, data from testrun_data config param, whole duration, url, etc.)
    - dut used info (ip, product, etc.)
    - for each test case run:
        - expose run times in micros
        - status (Passed/Fail etc)
        - size on disk
        - name, author, test attributes, etc.
    """
    enabled = False
    name = "json_reporter"

    def options(self, parser, env):
        """Register command line options."""
        parser.add_option('--with-jsonreport', action='store_true',
                          dest='with_jsonreport', default=False,
                          help="Enable Json Reporting tool. (default: no)")

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        super(JsonReporter, self).configure(options, noseconfig)
        self.enabled = self.enabled or noseconfig.options.with_jsonreport
        self.filename = options.get('filename', DEFAULT_FILENAME)
        self.callback_url = options.get('callback url')
        self.context = ContextHelper()
        self.data = self.context.set_container(PLUGIN_NAME)

    def report_results(self):
        LOG.info("Reporting results for Json Generator tool...")

    def dump_json(self):
        d = self.data
        path = d.session.path or '.'
        result = d.test_result
        output = Options()
        total = Options()

        def testcases(seq):
            return [x[0] for x in seq if isinstance(x[0], unittest.TestCase)]

        total.failures = result.failures + [(x[0], x[1]) for x in result.blocked.get(FAIL, [])]
        total.errors = result.errors + [(x[0], x[1]) for x in result.blocked.get(ERROR, [])]
        total.skipped = result.skipped + [(x[0], x[1]) for x in result.blocked.get(SKIP, [])]
        if hasattr(result, 'known_issue'):
            total.failures += result.known_issue

        output.summary = Options()
        output.summary.total = result.testsRun
        output.summary.failed = len(testcases(total.failures))
        output.summary.errors = len(testcases(total.errors))
        output.summary.skipped = len(testcases(total.skipped))

        output.duration = d.time.delta.total_seconds()
        output.start = d.time.start
        output.stop = d.time.stop
        output.runner = d.test_runner_ip
        output.url = d.session_url
        output.name = d.session.name
        output.statistics = self.context.get_stat_counter()
        # {{ dut.device.alias }} - {{ dut.device.address }}: {{ dut.platform }} {{ dut.version.version }} {{ dut.version.build }} {{ dut.project }} {% if data and data.cores[dut.device.alias] %}[CORED]{% endif %}
        output.duts = [dict(alias=x.device.alias, address=x.device.address,
                            is_default=x.device.is_default(),
                            platform=x.platform, version=x.version.version,
                            build=x.version.build, product=x.version.product.to_tmos,
                            project=x.project, has_cored=d.cores.data.get(x.device.alias, False) if d.cores  and
                       d.cores.data else False)
                       for x in d.duts]
        output.testrun_data = d.config.testrun

        output.results = []
        for result, status in [(total.failures, FAIL),
                               (total.errors, ERROR),
                               (total.skipped, SKIP),
                               (d.result.passed, PASSED)]:
            for test, err in result:
                if not isinstance(test, unittest.TestCase) or test.address() is None:
                    continue
                _, module, method = test.address()
                if method is None:
                    address = module
                else:
                    address = '%s:%s' % (module, method)

                tb = None
                if isinstance(err, tuple):
                    message = str(err[1]).encode('utf-8')
                    tb = ''.join(traceback.format_exception(*err))
                elif isinstance(err, Exception):
                    message = str(err)
                else:
                    message = err
                testMethod = getattr(test.test, test.test._testMethodName)
                try:
                    loc = len(inspect.getsourcelines(testMethod)[0])
                    size = len(inspect.getsource(testMethod))
                except (IOError,  # IOError:source code not available
                        IndexError):  # IndexError: list index out of range (bug in inspect?)
                    loc = size = -1

                r = Options()
                r.name = address
                r.status = status
                r.author = getattr(test.test, 'author', None)
                r.rank = getattr(test.test, 'rank', None)
                r.attrbutes = {}
                for key in INCLUDE_ATTR:
                    if hasattr(test.test, key):
                        r.attrbutes[key] = getattr(test.test, key)
                r.message = message
                r.traceback = tb
                r.loc = loc
                r.size = size
                if hasattr(test, '_start'):
                    r.start = test._start
                    if hasattr(test, '_stop'):
                        r.stop = test._stop
                else:
                    LOG.debug('No timestamp for %s', test)
                output.results.append(r)

        if os.path.exists(path):
            with open(os.path.join(path, self.filename), 'wt') as f:
                json.dump(output, f, indent=4, default=json_serial)

        if self.callback_url:
            LOG.debug("POSTing to callback endpoint...")
            s = requests.Session()
            headers = {}
            headers['Content-Type'] = 'application/json'
            s.headers.update(headers)
            try:
                s.post(self.callback_url, json.dumps(output, default=json_serial),
                       timeout=1)
            except requests.exceptions.ReadTimeout:
                LOG.debug("No response received from the callback endpoint. Ignoring.")
            except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as e:
                LOG.warning("Cannot connect to callback endpoint (%s).", e)

    def finalize(self, result):
        self.dump_json()
