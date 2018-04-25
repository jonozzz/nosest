'''
Created on Mar 29, 2018

@author: jono
'''
from __future__ import absolute_import
import pytest
import logging

logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("selenium").setLevel(logging.WARNING)


class Plugin(object):
    """
    Enables standard logging to file for all plugins.
    """
    def __init__(self, config):
        self.config = config
        self.handler = None

    def pytest_sessionstart(self, session):
        reporter = session.config.pluginmanager.get_plugin('logging-plugin')
        formatter = reporter.formatter
        level = getattr(reporter, 'log_file_level', None)
        handler = getattr(reporter, 'log_file_handler')
        root_logger = logging.getLogger()

        if handler is None:
            return

        if formatter is not None:
            handler.setFormatter(formatter)
        if level is not None:
            handler.setLevel(level)

        # Adding the same handler twice would confuse logging system.
        # Just don't do that.
        add_new_handler = handler not in root_logger.handlers

        if add_new_handler:
            root_logger.addHandler(handler)
            handler.mode = 'a'
            self.handler = handler
        if level is not None:
            self.orig_level = root_logger.level
            root_logger.setLevel(level)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session, exitstatus):
        root_logger = logging.getLogger()
        if self.handler:
            root_logger.removeHandler(self.handler)


def pytest_addoption(parser):
    parser.addoption('--no-log-hijack', action='store_true',
                     help='do not hijack logging')


def pytest_configure(config):
    if not config.option.no_log_hijack:
        config.pluginmanager.register(Plugin(config), 'logging2-plugin')
