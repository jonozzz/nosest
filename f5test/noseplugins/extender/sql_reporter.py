'''
Created on Nov 28, 2016

@author: jono
'''
from datetime import datetime
import json
import logging
import mysql.connector
from mysql.connector.errors import OperationalError
import time
import traceback

from . import ExtendedPlugin, PLUGIN_NAME
from .report import nose_selector
from .logcollect_start import get_test_meta
from ...base import AttrDict
from nose.plugins.skip import SkipTest
from functools import wraps

LOG = logging.getLogger(__name__)
DEFAULT_FILENAME = 'results.json'
FAIL = 'FAIL'
ERROR = 'ERROR'
PASSED = 'PASSED'
SKIP = 'SKIP'
INCLUDE_ATTR = ['module', 'uimode', 'hamode', 'scenario', 'doc']


class SqlReporter(ExtendedPlugin):
    """
    Connect to a MySQL server and submit results. The database must be setup with the correct schema prior to running this.
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
    name = "sql_reporter"

    def options(self, parser, env):
        """Register command line options."""
        parser.add_option('--with-sqlreport', action='store_true',
                          dest='with_sqlreport', default=False,
                          help="Enable SQL Reporting tool. (default: no)")
        parser.add_option('--sqlreport-resume', action="store",
                          help="The run ID of the test run that's being resumed.")

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        from ...interfaces.testcase import ContextHelper
        super(SqlReporter, self).configure(options, noseconfig)
        self.filename = options.get('filename', DEFAULT_FILENAME)
        self.data = ContextHelper().set_container(PLUGIN_NAME)
        self.context = ContextHelper()
        self.run_id = None
        self.rerun_id = None
        self.resume_id = int(noseconfig.options.sqlreport_resume or 0)
        self.duts_ids = []
        self.cursor = None

    def connect_db(self):
        o = self.options
        self.cnx = mysql.connector.connect(user=o.user, password=o.password,
                                           host=o.host, port=o.port,
                                           database=o.db)
        self.cursor = self.cnx.cursor(buffered=True)

    def close_db(self):
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.cnx:
            self.cnx.close()
            self.cnx = None

    def commit(self, *args, **kwargs):
        retry = 2
        while True:
            try:
                if not (self.cursor or self.cnx):
                    LOG.warning("No active DB connection. Attempt to connect..")
                    self.connect_db()
                self.cursor.execute(*args, **kwargs)
                break
            except OperationalError as e:
                if retry > 0:
                    LOG.warning('DB error: {}. Retry...'.format(e))
                    self.close_db()
                    retry = retry - 1
                else:
                    LOG.warning("DB error: {}. No more retry.".format(e))
                    break

        self.cnx.commit()

    def begin(self):
        """Set the testrun start time.
        """
        self.connect_db()
        session = self.context.get_config().get_session()

        d = self.data
        tr = d.config.get('testrun', AttrDict())
        if self.resume_id:
            query = "INSERT INTO reruns (runner, url, name, start, meta, type, harness, owner, description, run_id) \
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            self.commit(query, (d.test_runner_ip,
                                d.session_url,
                                session.name,
                                d.time.start,
                                json.dumps(d.config.testrun),
                                tr.type, tr.harness, tr.owner, tr.description,
                                self.resume_id))
            self.run_id = self.resume_id
            self.rerun_id = self.cursor.lastrowid
        else:
            query = "INSERT INTO runs (runner, url, name, start, meta, type, harness, owner, description) \
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            self.commit(query, (d.test_runner_ip,
                                d.session_url,
                                session.name,
                                d.time.start,
                                json.dumps(d.config.testrun),
                                tr.type, tr.harness, tr.owner, tr.description))
            self.run_id = self.cursor.lastrowid
        LOG.info('SQL Run ID: %d', self.run_id)

    def startTest(self, test, blocking_context=None):
        """Initializes a timer before starting a test."""
        # No-op when current test is blocked
        if not self.resume_id and not self.duts_ids:
            for dut in self.data.duts:
                query = "INSERT INTO duts (run_id, address, alias, platform, \
                                           version, build, product, project, has_cored) \
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                self.commit(query, (self.run_id,
                                    dut.device.address,
                                    dut.device.alias,
                                    dut.platform,
                                    dut.version.version,
                                    dut.version.build,
                                    dut.version.product.to_tmos,
                                    dut.project,
                                    int(dut.cores.data.get(dut.device.alias, False)
                                        if self.data.cores.data else False)))
                self.duts_ids.append(self.cursor.lastrowid)
        if blocking_context:
            return

    def addSuccess(self, test):
        test_meta = get_test_meta(test, as_dict=True)

        query = "INSERT INTO tests (run_id, name, status, author, start) \
                        VALUES (%s, %s, %s, %s, %s)"
        self.commit(query, (self.run_id,
                            nose_selector(test),
                            'PASS',
                            test_meta['author'],
                            datetime.fromtimestamp(test._start)
                            ))

    def addError(self, test, err):
        test_meta = get_test_meta(test, as_dict=True)

        if issubclass(err[0], SkipTest):
            status = 'SKIP'
        else:
            status = 'ERROR'

        query = "INSERT INTO tests (run_id, name, status, traceback, author, start) \
                        VALUES (%s, %s, %s, %s, %s, %s)"
        self.commit(query, (self.run_id,
                            nose_selector(test),
                            status,
                            ''.join(traceback.format_exception(*err)),
                            test_meta['author'],
                            datetime.fromtimestamp(test._start)
                            ))

    def addFailure(self, test, err):
        test_meta = get_test_meta(test, as_dict=True)

        query = "INSERT INTO tests (run_id, name, status, traceback, author, start) \
                        VALUES (%s, %s, %s, %s, %s, %s)"
        self.commit(query, (self.run_id,
                            nose_selector(test),
                            'FAIL',
                            ''.join(traceback.format_exception(*err)),
                            test_meta['author'],
                            datetime.fromtimestamp(test._start)
                            ))

    def addBlocked(self, test, err):
        test_meta = get_test_meta(test, as_dict=True)

        query = "INSERT INTO tests (run_id, name, status, author, start) \
                        VALUES (%s, %s, %s, %s, %s)"
        self.commit(query, (self.run_id,
                            nose_selector(test),
                            'BLOCK',
                            test_meta['author'],
                            datetime.fromtimestamp(test._start) if hasattr(test, '_start') else None
                            ))

    def finalize(self, result):
        try:
            query = "UPDATE runs SET stop=%s WHERE id=%s"
            self.commit(query, (self.data.time.stop,
                                self.run_id))
            if self.rerun_id:
                query = "UPDATE reruns SET stop=%s WHERE id=%s"
                self.commit(query, (self.data.time.stop,
                                    self.rerun_id))
            for dut_id, dut in zip(self.duts_ids, self.data.duts):
                query = "UPDATE duts SET has_cored=%s WHERE id=%s"
                self.commit(query, (int(dut.cores.data.get(dut.device.alias, False)
                                        if self.data.cores.data else False),
                                    dut_id))
        finally:
            self.close_db()


SQL_PLUGIN = 'sql_reporter'


def sql_log_result():
    def _my_decorator(f):

        def addResult_mysql(*args, **kwargs):
            test_obj = args[0]

            name1 = (test_obj._name.split('.')[:-1])
            name1.append(f.func_name)
            method_name = '.'.join(name1)

            start_time = time.time()
            tb = ''
            try:
                rslt = f(*args, **kwargs)
            except Exception as err:
                tb = traceback.format_exc()
                if isinstance(err, SkipTest):
                    rslt = 'SKIP'
                else:
                    rslt = 'FAIL'

            status = 'PASS' if rslt is None else rslt
            stop_time = time.time()

            plugins = test_obj._resultForDoCleanups.plugins.plugins
            for plugin in plugins:
                if plugin.name == SQL_PLUGIN:
                    run_id = plugin.run_id
                    sql_plugin = plugin
                    break

            insert = "INSERT INTO tests (run_id, name, status, author, start, \
                        stop, traceback) \
                        VALUES (%s, %s, %s, %s, %s, %s, %s)"
            data = (run_id,
                    method_name,
                    status,
                    test_obj.author,
                    datetime.fromtimestamp(start_time),
                    datetime.fromtimestamp(stop_time),
                    tb
                    )
            sql_plugin.commit(insert, data)

        return wraps(f)(addResult_mysql)
    return _my_decorator
