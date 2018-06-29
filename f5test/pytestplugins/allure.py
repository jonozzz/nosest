from __future__ import absolute_import
import pytest

from f5test.interfaces import ContextHelper
from ..utils.convert import to_bool
from ..base import AttrDict
import subprocess
# from ..utils.ansible import run_playbooks, FIXTURES_DIR
import os
import logging
import shutil
import yaml
import json


LOG = logging.getLogger(__name__)
REPORT_DIR_ROOT = '/tmp'


def _get_session_dir(context, *args):
    cfgifc = context.get_config()
    path = cfgifc.get_session().path

    if args:
        path = os.path.join(path, *args)

    if path and not os.path.exists(path):
        oldumask = os.umask(0)
        try:
            os.makedirs(path)
        finally:
            os.umask(oldumask)

    return path


class Plugin(object):
    """
    Generate test run reports via Allure.
    """
    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc') and config._tc.plugins:
            self.options = config._tc.plugins.allure or AttrDict()
            self.enabled = to_bool(self.options.enabled)
        else:
            self.enabled = False

        if self.enabled:
            self.context = ContextHelper()
            log_file = os.path.join(_get_session_dir(self.context), 'debug.log')
            self.handler = logging.FileHandler(log_file, mode='w')

    def pytest_sessionstart(self, session):
        if not self.enabled:
            return

        reporter = session.config.pluginmanager.get_plugin('logging-plugin')
        formatter = reporter.formatter
        level = getattr(reporter, 'log_file_level', None)
        #handler = getattr(reporter, 'log_file_handler')
        root_logger = logging.getLogger()

        #if handler is None:
        #    return

        if formatter is not None:
            self.handler.setFormatter(formatter)
        if level is not None:
            self.handler.setLevel(level)

        # Adding the same handler twice would confuse logging system.
        # Just don't do that.

        add_new_handler = self.handler not in root_logger.handlers

        if add_new_handler:
            root_logger.addHandler(self.handler)
            #self.handler = handler
        if level is not None:
            self.orig_level = root_logger.level
            root_logger.setLevel(level)
        LOG.info("Session started.")

    def allure_generate(self):
        if not self.enabled:
            return
        path = _get_session_dir(self.context, 'report')
        ret = subprocess.call([self.options.bin, "generate", "-o", path,
                              self.config.option.allure_report_dir])
        if not ret:
            LOG.info("Allure report generated in: %s", path)
        else:
            LOG.warn("Allure report failed")

    def yaml_config_generate(self):
        if not self.enabled:
            return
        path = _get_session_dir(self.context)
        filename = os.path.join(path, 'config.yaml')
        with open(filename, "wt") as f:
            config = self.context.get_config().api
            yaml.dump(config, f, indent=4, width=1024, default_flow_style=False)

    def X_pytest_json_modifyreport(self, json_report):
        if self.enabled is False:
            return
        path = _get_session_dir(self.context)
        filename = os.path.join(path, 'report.json')
        with open(filename, "wt") as f:
            json.dump(json_report, f, indent=2)

    def pytest_sessionfinish(self, session, exitstatus):
        if not self.enabled:
            return
        LOG.info("Session finished.")
        root_logger = logging.getLogger()
        if self.handler:
            self.handler.close()
            root_logger.removeHandler(self.handler)
        self.allure_generate()
        self.yaml_config_generate()
        shutil.rmtree(self.config.option.allure_report_dir)


def pytest_cmdline_main(config):
    if hasattr(config, '_tc') and config._tc.plugins:
        options = config._tc.plugins.allure or AttrDict()
        if to_bool(options.enabled):
            context = ContextHelper()
            session = context.get_config().get_session()
            allure_report_dir = os.path.join(options.get('tmp', REPORT_DIR_ROOT),
                                             "allure-%s" % session.name)
            if config.option.allure_report_dir:
                LOG.warn('Allure report dir changed to: %s', allure_report_dir)

            config.option.allure_report_dir = allure_report_dir


def pytest_configure(config):
    if config.option.json_report:
        Plugin.pytest_json_modifyreport = Plugin.X_pytest_json_modifyreport
    config.pluginmanager.register(Plugin(config), 'alluregenerator-plugin')
