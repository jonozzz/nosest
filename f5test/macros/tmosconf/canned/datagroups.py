'''
Created on May 4, 2016

@author: jono
'''
import logging
import netaddr

from ....utils.net import IPNetworkRd, IPAddressRdPort
from ..iapps import iApp
from ..irules import GbbpDG
from ..ltm import (DataGroup as LtmDataGroup, VirtualServer2, Pool2)
from ..profile import (Profile, references)
from ..sys import DataGroup as SysDataGroup
from . import BaseConfig


LOG = logging.getLogger(__name__)


class DGConfig(BaseConfig):

    def __init__(self, node_ips, vs_ip, vs_port=80, sp1_members=None, sp2_members=None,
                 dg_file=None, *args, **kwargs):
        self.node_ips = node_ips
        self.vs_ip = vs_ip
        self.vs_port = vs_port
        self.sp1_members = sp1_members or []
        self.sp2_members = sp2_members or []
        self.dg_file = dg_file
        super(DGConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('GBBP Datagroup configuration')
        rd = self.route_domain

        vs_ip = netaddr.IPNetwork(self.vs_ip)

        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        self.common.hook(profile_http, profile_tcp)

        webpool3 = Pool2('webpool3')
        webpool3.properties.members = [str(IPAddressRdPort(x, rd=rd.id(), port=80))
                                       for x in self.node_ips]

        ad_query_virtual = VirtualServer2('ad_query_virtual')
        ad_query_virtual.properties.destination = str(IPAddressRdPort(vs_ip,
                                                                      rd=rd.id(), port=self.vs_port))
        ad_query_virtual.properties.source = str(IPNetworkRd('0.0.0.0/0', rd=rd.id()))
        ad_query_virtual.properties.profiles = references(profile_http, profile_tcp)
        ad_query_virtual.properties.pool = webpool3
        self.folder.hook(webpool3, ad_query_virtual)

        sdg = SysDataGroup('sdg1', dg_file=self.dg_file)
        ldg = LtmDataGroup('ldg1')
        ldg.properties.external_file_name = str(sdg)
        self.folder.hook(sdg, ldg)

        gbbp = GbbpDG()
        self.folder.hook(gbbp)

        iapp = iApp('f5.microsoft_exchange_2010_2013_cas.v1.2.0')
        self.folder.hook(iapp)

        iapp = iApp('f5.microsoft_exchange_2010_2013_cas.v1.5.1')
        self.folder.hook(iapp)

        iapp = iApp('f5.ssl_intercept.v1.0.0')
        self.folder.hook(iapp)

        iapp = iApp('f5.citrix_vdi.v2.3.0')
        self.folder.hook(iapp)

        return self.tree
