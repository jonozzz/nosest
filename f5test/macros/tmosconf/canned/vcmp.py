'''
Created on May 4, 2016

@author: jono
'''
import logging
import netaddr


from ...base import Macro
from ..base import PARTITION_COMMON
from ..scaffolding import make_partitions
from ..vcmp import vCMPGuest


LOG = logging.getLogger(__name__)


class vCMPConfig(Macro):

    def __init__(self, context, name=None, initial_image=None,
                 initial_hotfix=None, management_ip=None, management_gw=None,
                 cores_per_slot=None, state=None, tree=None):
        self.context = context
        self.tree = tree
        self.name = name
        self.initial_image = initial_image
        self.initial_hotfix = initial_hotfix
        self.management_ip = netaddr.IPNetwork(management_ip or '127.0.0.1/24')
        self.management_gw = netaddr.IPAddress(management_gw or '0.0.0.0')
        self.cores_per_slot = cores_per_slot
        super(vCMPConfig, self).__init__()

    def setup(self):
        tree = self.tree or make_partitions(count=self.partitions,
                                            context=self.context)
        common = tree[PARTITION_COMMON]

        # vCMP Guest
        LOG.info('Generating vCMP Guest: %s' % self.name)
        common.hook(vCMPGuest(self.name, self.initial_image,
                              self.management_ip, self.management_gw,
                              cores_per_slot=self.cores_per_slot,
                              initial_hotfix=self.initial_hotfix))

        return tree
