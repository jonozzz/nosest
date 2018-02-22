'''
Created on May 4, 2016

@author: jono
'''
import logging
import netaddr

from ....utils.net import IPAddressRdPort
from ..apm.swg_explicit import SWGExplicit
from ..apm.swg_transparent import SWGTransparent
from ..net import Vlan
from ..scaffolding import enumerate_stamps
from ..sys import SSLCert, SSLKey
from . import BaseConfig


LOG = logging.getLogger(__name__)


class APMConfig(BaseConfig):

    def __init__(self, vs_ip, ssl_key=None, ssl_cert=None, *args, **kwargs):
        self.vs_ip = vs_ip
        self.ssl_key = ssl_key
        self.ssl_cert = ssl_cert
        super(APMConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('APM configuration')
        rd = self.route_domain

        ssl_cert = SSLCert(name='apm.crt', obj=self.ssl_cert)
        ssl_key = SSLKey(name='apm.key', obj=self.ssl_key)
        self.folder.hook(ssl_cert, ssl_key)
        vlans = enumerate_stamps(self.tree, Vlan, include_common=False)
        self.folder.hook(SWGTransparent(rd=rd, ssl_cert=ssl_cert, ssl_key=ssl_key,
                                        vlans=vlans))

        vs_ip = netaddr.IPNetwork(self.vs_ip)

        self.folder.hook(SWGExplicit(rd=rd, destination=IPAddressRdPort(vs_ip, rd=rd.id(), port=3128),
                                     ssl_cert=ssl_cert, ssl_key=ssl_key))

        return self.tree
