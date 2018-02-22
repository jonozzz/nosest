'''
Created on Dec 30, 2015

@author: jwong
'''
from .base import Stage
from ...base import Options
from ...interfaces.config import ConfigInterface
from ...interfaces.ssh import SSHInterface
from ...macros.tmosconf.placer_vcmp import VcmpPlacer

import logging

DEFAULT_TIMEOUT = 600
LOG = logging.getLogger(__name__)


class ConfigVCMPStage(Stage, VcmpPlacer):
    """
    This stage makes sure the devices are configured with the 'stock' settings.
    Its functionally is similar to the f5.configurator CLI utility.
    """
    name = 'config_vcmp'

    def __init__(self, device, specs, *args, **kwargs):
        configifc = ConfigInterface()
        config = configifc.open()
        self._context = specs.get('_context')
        guests = configifc.get_devices_instances([device])

        options = Options(device=device,
                          timeout=specs.get('timeout'),
                          no_irack=specs.get('no irack'),
                          csv=specs.get('csv'),
                          hostname=specs.get('hostname'))

        if config.irack:
            options.irack_address = config.irack.address
            options.irack_username = config.irack.username
            options.irack_apikey = config.irack.apikey

        super(ConfigVCMPStage, self).__init__(options=options, guests=guests,
                                              *args, **kwargs)

    def setup(self):
        ret = super(ConfigVCMPStage, self).setup()

        return ret

    def revert(self):
        super(ConfigVCMPStage, self).revert()
        if self._context:
            LOG.debug('In ConfigVCMPStage.revert()')
            device = self.options.device
            self._context.get_interface(SSHInterface, device=device)
