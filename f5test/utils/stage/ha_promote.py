'''
Created on Sept 30, 2015

@author: prodriguez
'''
from f5test.interfaces.rest.emapi.objects import DeviceResolver, \
                                                 FailoverState
from ...interfaces.config import ConfigInterface, expand_devices
from ...interfaces.ssh import SSHInterface
from ...macros.base import Macro
from f5test.interfaces.testcase import ContextHelper
from .base import Stage
from ...base import Options
from f5test.utils.wait import wait
from f5test.commands.rest.device import DEFAULT_ALLBIGIQS_GROUP
import f5test.commands.rest as RCMD
import f5test.defaults as F5D
import logging

LOG = logging.getLogger(__name__)


class HAPromoteStage(Stage, Macro):
    """
    Swap default device in an HA setup, and promote secondary on active/standby
    """
    name = 'ha_promote'

    def __init__(self, device, specs=None, *args, **kwargs):
        # This stage only promotes one item at a time. If the user configures
        # too many peers, ignore the rest. If the user doesn't provide at least
        # one peer, except to let them know.
        self.peer = expand_devices(specs, 'promote')[0]
        self.default = device

        options = Options(reset=specs.get("reset"),
                          timeout=specs.get("timeout"),
                          ha_passive=specs.get("ha_passive"))
        self.ha_passive = specs.get("ha_passive")
        self._context = specs.get('_context')

        super(HAPromoteStage, self).__init__(*args, **kwargs)

    def setup(self):
        super(HAPromoteStage, self).setup()
        LOG.info('Promotion stage for: %s', self.default)

        self.default.specs.default = False
        self.peer.specs.default = True

        LOG.info("old default = %s", self.default)
        LOG.info("new default = %s", self.peer)

        # if this is active/standby, promote, otherwise, not needed.
        if self.ha_passive:
            # Prepare command to send to promote
            payload = Options()
            payload.command = 'SET_PRIMARY'

            LOG.info("Picking up the list of peers from the new primary")
            context = ContextHelper(__name__)
            rest = context.get_icontrol_rest(device=self.peer).api
            resp = rest.get(DeviceResolver.DEVICES_URI % DEFAULT_ALLBIGIQS_GROUP)

            # Look for the machine id of the peer to promote
            for item in resp['items']:
                if item.address == self.peer.get_discover_address():
                    payload.machineId = item.machineId
                    LOG.info("Promoting peer to primary from peer")
                    rest.post(FailoverState.URI, payload=payload)

            # wait for restjavad to go down...
            wait(lambda: rest.get(DeviceResolver.DEVICES_URI % DEFAULT_ALLBIGIQS_GROUP)['items'],
                 negated=True,
                 progress_cb=lambda ret: 'Waiting for restjavad on {0} to go down.'.format(self.default))
            # wait for it to come back up
            RCMD.system.wait_restjavad([self.peer])
