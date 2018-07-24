'''
Created on Feb 21, 2014

@author: jono
'''
import logging

from f5test.utils.convert import to_bool

import f5test.commands.shell as SCMD
import f5test.commands.rest as RCMD

import f5test.commands.icontrol as ICMD
from ...interfaces.ssh import SSHInterface
from f5test.interfaces.rest.emapi import EmapiInterface
from f5test.interfaces.rest.core import AUTH
from ...macros.base import Macro
from .base import Stage
from f5test.utils.wait import wait_args
import time


LOG = logging.getLogger(__name__)


class TweaksStage(Stage, Macro):
    """
    Mainly this stage is open for any type of debugging flags/setups needed to
    be set after a clean software install. This includes:

    - Enable iControl debug logging (icontrol);
    - Force logrotate (logrotate);
    - Enable iControl Proxy.

    These settings will be on for all tests and will not be unset (unless a
    teardown stage is implemented).
    """
    name = 'tweaks'

    def __init__(self, device, specs=None, *args, **kwargs):
        self.device = device
        self.specs = specs
        self._context = specs.get('_context')
        super(TweaksStage, self).__init__(*args, **kwargs)

    def setup(self):
        super(TweaksStage, self).setup()
        LOG.info('Tweaks stage for: %s', self.device)
        # mcp: Enable MCPD debug logging
        if self.specs.mcp and to_bool(self.specs.mcp):
            with SSHInterface(device=self.device) as sshifc:
                sshifc.api.run('setdb log.mcpd.level debug')

        # icontrol: Enable icontrol debug logging
        if self.specs.icontrol and to_bool(self.specs.icontrol):
            with SSHInterface(device=self.device) as sshifc:
                sshifc.api.run('setdb icontrol.loglevel debug')
                sshifc.api.run('bigstart restart httpd')

        # logrotate: Force logrotate all logs
        if self.specs.logrotate and to_bool(self.specs.logrotate):
            with SSHInterface(device=self.device) as sshifc:
                sshifc.api.run('/usr/sbin/logrotate /etc/logrotate.conf -f')
                # BIG-IQ is so "special" - it doesn't use the usual logrotate ways.
                # 07/24 IT: restarting restjavad causes errors in discovery
                # sshifc.api.run('[ -f /service/restjavad/run ] && bigstart stop restjavad && rm -f /var/log/restjavad* && bigstart start restjavad')

        # log_finest: Force restjavad log files to use FINEST level.
        if self.specs.log_finest and to_bool(self.specs.log_finest):
            with SSHInterface(device=self.device) as sshifc:
                sshifc.api.run("sed -i 's/^.level=.*/.level=FINEST/g' /etc/restjavad.log.conf && bigstart restart restjavad")

        # scp: Copy files to/from
        if self.specs.scp:
            params = self.specs.scp

            source = params.source if isinstance(params.source, str) \
                else ' '.join(params.source)

            with SSHInterface(device=self.device) as sshifc:
                if params.method.lower() == 'get':
                    SCMD.ssh.scp_get(ifc=sshifc, source=source,
                                     destination=params.destination, nokex=True)
                elif params.method.lower() == 'put':
                    SCMD.ssh.scp_put(ifc=sshifc, source=source,
                                     destination=params.destination, nokex=True)
                else:
                    raise ValueError("Unknown scp method: %s" % params.method)

        # shell: Execute shell commands
        if self.specs.shell:
            commands = [self.specs.shell] if isinstance(self.specs.shell,
                                                        str) \
                else self.specs.shell
            with SSHInterface(device=self.device) as sshifc:
                for command in commands:
                    ret = sshifc.api.run(command)
                    LOG.debug(ret)

        # sleep (stabalize)
        if self.specs.sleep:
            params = int(self.specs.sleep)
            LOG.info("Tweak Sleep {0}s".format(params))
            time.sleep(params)


class RebootStage(Stage, Macro):
    """
    Reboot a device and wait for mcpd/prompt to come back. Optionally wait for
    restjavad to come up.
    """
    name = 'reboot'
    timeout = 180

    def __init__(self, device, specs=None, *args, **kwargs):
        self.device = device
        self.specs = specs
        self._context = specs.get('_context')
        super(RebootStage, self).__init__(*args, **kwargs)

    def _wait_after_reboot(self, device):
        ssh = SSHInterface(device=device)

        timeout = self.timeout
        try:
            SCMD.ssh.GetPrompt(ifc=ssh).\
                run_wait(lambda x: x not in ('INOPERATIVE', '!'), timeout=timeout,
                         timeout_message="Timeout ({0}s) waiting for a non-inoperative prompt.")
            SCMD.ssh.FileExists('/var/run/mcpd.pid', ifc=ssh).\
                run_wait(lambda x: x,
                         progress_cb=lambda x: 'mcpd not up...',
                         timeout=timeout)
            SCMD.ssh.FileExists('/var/run/mprov.pid', ifc=ssh).\
                run_wait(lambda x: x is False,
                         progress_cb=lambda x: 'mprov still running...',
                         timeout=timeout)
            SCMD.ssh.FileExists('/var/run/grub.conf.lock', ifc=ssh).\
                run_wait(lambda x: x is False,
                         progress_cb=lambda x: 'grub.lock still running...',
                         timeout=timeout)
            version = SCMD.ssh.get_version(ifc=ssh)
        finally:
            ssh.close()
        return version

    def setup(self):
        super(RebootStage, self).setup()
        LOG.info('Reboot stage for: %s', self.device)
        SCMD.ssh.reboot(device=self.device)

        if self.specs.mcpd and to_bool(self.specs.mcpd):
            self._wait_after_reboot(self.device)

        if self.specs.restjavad and to_bool(self.specs.restjavad):
            RCMD.system.wait_restjavad([self.device])


class RestHealthStage(Stage, Macro):
    """
    Wait for Rest Services to be up. Optionally wait for
    restjavad to come up.
    """
    name = 'rest-health'
    timeout = 300
    interval = 10

    def __init__(self, device, specs=None, *args, **kwargs):
        self.device = device
        self.specs = specs
        self._context = specs.get('_context')
        super(RestHealthStage, self).__init__(*args, **kwargs)

    def setup(self):

        v = ICMD.system.get_version(device=self.device)
        LOG.info('Rest Health stage for: %s|%s', self.device, v)

        if v.product.is_bigiq or v.product.is_iworkflow or \
           v.product.is_bigip and (v >= 'bigip 11.5.1'):
            timeout = self.specs.timeout_each if self.specs.timeout_each else self.timeout
            interval = self.specs.check_interval if self.specs.timeout_each else self.interval
            apis = self.specs.rest_apis

            if apis and isinstance(apis, list):
                if v >= 'bigip 11.5.1' and v < 'bigip 12.0':  # unclear intermittent /mgmt/tm/ not available on 11.6.x
                    apis2 = []
                    for api in apis:
                        if not api.startswith('/mgmt/tm/'):
                            apis2.append(api)
                        else:
                            LOG.warning("11.6.x detected. Ignoring check for '%s'" % api)
                    apis = apis2

                with EmapiInterface(device=self.device, auth=AUTH.BASIC) as rstifc:
                    def wait_available(uri):
                        return rstifc.api.get(uri) == {}

                    for api in apis:
                        if api.endswith("/available"):
                            wait_args(wait_available, func_args=[api],
                                      timeout=timeout, interval=interval,
                                      timeout_message="api %s not available after {0}s" % api)
                        else:
                            wait_args(rstifc.api.get, func_args=[api],
                                      timeout=timeout, interval=interval,
                                      timeout_message="api %s not available after {0}s" % api)
            else:
                LOG.info('Rest Health stage skipping - no REST.')
