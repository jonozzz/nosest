"""
Collects info on failed tests/sessions
"""
import pytest
from _pytest.fixtures import FixtureLookupError
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
        # Hack to handle the case where a failure happens in a package fixture
        # and we need to drill into other package fixtures that didn't fail to
        # get to the context helper's interfaces.
        if report.outcome in ('failed', 'error'):
            fixture_values = []
            if report.when == 'setup':
                try:
                    for x in item.funcargnames:
                        val = item._request.getfixturevalue(x)
                        if val is not None:
                            fixture_values.append(val)
                except FixtureLookupError:
                    # Ignore it because this is the fixture that failed.
                    pass
            else:
                fixture_values = [x for x in item.funcargs.values() if x is not None]

            for context in filter(lambda x: isinstance(x, ContextHelper), fixture_values):
                interfaces = context.get_container(container=INTERFACES_CONTAINER).values()
                for interface in interfaces:
                    self.try_screenshots(interface)


def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'collector-plugin')
