'''
Created on Apr 12, 2013

@author: jono
'''
from .scaffolding import Stamp
import logging

LOG = logging.getLogger(__name__)


class vCMPGuest(Stamp):
    TMSH = """
        vcmp guest %(name)s {
            cores-per-slot 1
            initial-image BIGIP-11.6.0.0.0.401.iso
            management-ip 10.192.76.135/24
            management-gw 10.192.76.1
        }
        """

    def __init__(self, name, initial_image, management_ip, management_gw,
                 initial_hotfix=None, cores_per_slot=None):
        self.name = name
        self.initial_image = initial_image
        self.initial_hotfix = initial_hotfix
        self.management_ip = management_ip
        self.management_gw = management_gw
        self.cores_per_slot = cores_per_slot or 1
        super(vCMPGuest, self).__init__()

    def tmsh(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip and v >= 'bigip 11.0.0':
            key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
            value = obj.rename_key('vcmp guest %(name)s', name=self.name)
            value['initial-image'] = self.initial_image
            value['management-ip'] = str(self.management_ip)
            value['management-gw'] = str(self.management_gw)
            value['cores-per-slot'] = self.cores_per_slot

            if self.initial_hotfix:
                value['initial-hotfix'] = self.initial_hotfix

            return key, obj
        return None, None
