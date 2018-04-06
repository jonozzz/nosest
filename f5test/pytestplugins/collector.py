"""
Collects info on failed tests/sessions
"""
import pytest
from allure_commons.types import AttachmentType

from ..interfaces.testcase import (ContextHelper, INTERFACES_CONTAINER)
from ..interfaces.selenium import SeleniumInterface
import f5test.commands.ui as UI


class Plugin(object):
    """
    Collects screenshots, logs, qkviews.
    """
    name = "collector"

    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc'):
            self.options = config._tc.plugins.sidebyside
            self.enabled = self.options.enabled
        else:
            self.enabled = False

    def try_screenshots(self, interface):
        if isinstance(interface, SeleniumInterface):
            for window in interface.api.window_handles:
                credentials = interface.get_credentials(window)

                if credentials.device:
                    name = credentials.device.get_alias()
                else:
                    name = credentials.address or window

                png, html = UI.common.screen_shot2(window=window, ifc=interface)
                pytest.allure.attach(png, "screenshot-%s" % name, AttachmentType.PNG)
                pytest.allure.attach(html, "page-%s" % name, AttachmentType.HTML)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        report = (yield).get_result()
        for context in filter(lambda x: isinstance(x, ContextHelper),
                              item.funcargs.values()):
            interfaces = context.get_container(container=INTERFACES_CONTAINER).values()
            if report.outcome in ('failed', 'error'):
                for interface in interfaces:
                    self.try_screenshots(interface)

    # def pytest_sessionstart(self, session):
    #     if self.enabled is False:
    #         return
    #
    #     global PATH
    #     PATH = self.options.path


def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'collector-plugin')
