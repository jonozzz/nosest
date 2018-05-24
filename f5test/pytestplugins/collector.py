"""
Collects info on failed tests/sessions
"""
from __future__ import absolute_import
import logging
import os
import pytest
from _pytest.fixtures import FixtureLookupError
from allure_commons.types import AttachmentType

from ..interfaces.testcase import (ContextHelper, INTERFACES_CONTAINER)
from ..interfaces.selenium import SeleniumInterface
from ..interfaces.ssh import SSHInterface
from ..interfaces.icontrol.em import EMInterface
from ..interfaces.rest import RestInterface
from ..interfaces.icontrol import IcontrolInterface
from ..interfaces.config import ConfigInterface
from ..base import Interface
import f5test.commands.ui as UI
import f5test.commands.shell.ssh as SSH


LOG = logging.getLogger(__name__)


def sanitize_test_name(item):
    # Windows-based NAS doesn't support :'s in names
    return item.nodeid.replace('/', '.').replace(':', '@')


class Plugin(object):
    """
    Collects screenshots, logs, qkviews.
    """
    name = "collector"

    def __init__(self, config):
        self.config = config
        self.context = ContextHelper()
        self.session = self.context.get_config().get_session()
        self.visited_ssh = set()
        self.visited_selenium = set()
        self.visited_fixtures = set()

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

            # Switching back to main window
            if len(interface.api.window_handles) > 1:
                interface.api.switch_to_window('')

    def _get_session_dir(self):
        path = self.session.path

        if path and not os.path.exists(path):
            oldumask = os.umask(0)
            os.makedirs(path)
            os.umask(oldumask)

        return path

    def _get_or_create_dirs(self, name, root=None):
        if root is None:
            root = self._get_session_dir()

        created = False
        path = os.path.join(root, name)

        if not os.path.exists(path):
            oldumask = os.umask(0)
            os.makedirs(path)
            os.umask(oldumask)
            created = True

        return path, created

    def create_item_dir(self, item, unique=False):
        test_name = sanitize_test_name(item)
        test_root, created = self._get_or_create_dirs(test_name)
        if not created and unique:
            i = 1
            while not created:
                test_root, created = self._get_or_create_dirs("%s.%d" % (test_name, i))
                i += 1
        return test_root

    def try_collect(self, item, interface):
        if not isinstance(interface, Interface):
            return

        if isinstance(interface, ConfigInterface):
            return

        if not interface.is_opened():
            return

        sshifcs = []
        collected = 0
        if SeleniumInterface and isinstance(interface, SeleniumInterface):
            for window in interface.api.window_handles:
                credentials = interface.get_credentials(window)

                if credentials.device:
                    address = credentials.device.get_address()
                else:
                    address = credentials.address or window

                if credentials.device and address not in self.visited_ssh:
                    sshifcs.append(SSHInterface(device=credentials.device))
        elif isinstance(interface, SSHInterface):
            # Clone the SSH interface, rather than reusing it.
            sshifcs.append(SSHInterface(device=interface.device,
                                        address=interface.address,
                                        username=interface.username,
                                        password=interface.password,
                                        key_filename=interface.key_filename))
        elif isinstance(interface, (IcontrolInterface, EMInterface, RestInterface)):
            if interface.device and interface.device.address == interface.address:
                sshifcs.append(SSHInterface(device=interface.device))
        else:
            LOG.debug('Skip collection from interface: %s', interface)
            return

        test_root = self.create_item_dir(item)

        for sshifc in sshifcs:
            address = sshifc.address
            if address in self.visited_ssh:
                continue

            with sshifc:
                log_root, _ = self._get_or_create_dirs(address, test_root)
                LOG.debug('Collecting logs from %s', address)
                try:
                    version = SSH.get_version(ifc=sshifc)
                    SSH.collect_logs(log_root, ifc=sshifc, version=version)
                    collected += 1
                except Exception as e:
                    LOG.error('Collecting logs failed: %s', e)
                self.visited_ssh.add(address)

        return collected

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        report = (yield).get_result()
        # Hack to handle the case where a failure happens in a package fixture
        # and we need to drill into other package fixtures that didn't fail to
        # get to the context helper's interfaces.
        self.visited_ssh.clear()
        self.visited_selenium.clear()
        if report.outcome in ('failed', 'error'):
            fixture_values = []
            if report.when == 'setup':
                try:
                    for x in item.funcargnames:
                        val = item._request.getfixturevalue(x)
                        if val is not None:
                            fixture_values.append(val)
                except FixtureLookupError as e:
                    # Ignore it because this is the fixture that failed.
                    fixdef = e.request._arg2fixturedefs[e.argname][0]
                    if fixdef in self.visited_fixtures:
                        return
                    self.visited_fixtures.add(fixdef)
            else:
                fixture_values = [x for x in item.funcargs.values() if x is not None]

            for context in filter(lambda x: isinstance(x, ContextHelper), fixture_values):
                interfaces = context.get_container(container=INTERFACES_CONTAINER).values()
                for interface in interfaces:
                    self.try_screenshots(interface)
                    self.try_collect(item, interface)

                test_name = sanitize_test_name(item)
                url = self.session.get_url() + '/' + test_name
                pytest.allure.attach(url, "logs", AttachmentType.URI_LIST)

def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'collector-plugin')
