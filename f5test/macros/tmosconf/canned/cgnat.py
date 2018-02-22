'''
Created on May 4, 2016

@author: jono
'''
import logging

from ....utils.net import IPNetworkRd, IPAddressRd, IPAddressRdPort
from ....utils.parsers.tmsh import RawEOL
from ..ltm import (LsnPool, LsnLogProfile, VirtualServer2, VirtualAddress)
from ..net import Vlan
from ..profile import (Profile, Sip, references)
from ..scaffolding import enumerate_stamps
from ..pem import ProfileSpm
from . import BaseConfig


LOG = logging.getLogger(__name__)


class CGNATConfig(BaseConfig):

    def __init__(self, vs_ip, vs_port=None, *args, **kwargs):
        self.vs_ip = vs_ip
        self.vs_port = vs_port or 5060
        super(CGNATConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('CGNAT configuration')
        all_vlans = list(enumerate_stamps(self.tree, Vlan, include_common=False))
        rd = self.route_domain

        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        alg_sip = Sip('alg_sip')
        alg_sip.properties.community = 'alg_sip'
        self.common.hook(profile_http, profile_tcp)
        self.folder.hook(alg_sip)

        lsn_log_profile = LsnLogProfile('lsn_log_profile')

        lsnpool = LsnPool('lsnpool')
        lsnpool.properties.client_connection_limit = 10000
        lsnpool.properties.egress_interfaces = references(*all_vlans)
        lsnpool.properties.egress_interfaces_enabled = RawEOL
        lsnpool.properties.egress_interfaces_disabled = lambda k, d: d.pop(k)
        lsnpool.properties.hairpin_mode = 'enabled'
        lsnpool.properties.icmp_echo = 'enabled'
        lsnpool.properties.members = [str(IPNetworkRd('4.4.4.0/28', rd=rd.id()))]
        lsnpool.properties.persistence = dict(mode='address')
        lsnpool.properties.route_advertisement = 'enabled'
        lsnpool.properties.translation_port_range = '50000-60000'

        lsnpool2 = LsnPool('lsnpool2')
        lsnpool2.properties.inbound_connections = 'automatic'
        lsnpool2.properties.log_profile = lsn_log_profile
        lsnpool2.properties.log_publisher = '/Common/local-db-publisher'
        lsnpool2.properties.members = [str(IPNetworkRd('4.4.4.128/28', rd=rd.id()))]
        lsnpool2.properties.port_block_allocation = {}
        lsnpool2.properties.port_block_allocation.block_idle_timeout = 30
        lsnpool2.properties.translation_port_range = '32769-65535'

        lsnpool3 = LsnPool('lsnpool3')
        lsnpool.properties.hairpin_mode = 'enabled'
        lsnpool.properties.icmp_echo = 'enabled'
        lsnpool3.properties.log_profile = str(lsn_log_profile)
        lsnpool3.properties.log_publisher = '/Common/local-db-publisher'
        lsnpool3.properties.members = [str(IPNetworkRd('5.5.5.0/26', rd=rd.id()))]
        lsnpool3.properties.mode = 'deterministic'
        lsnpool3.properties.persistence = dict(mode='address-port')
        lsnpool3.properties.route_advertisement = 'enabled'
        self.folder.hook(lsnpool, lsnpool2, lsnpool3)

        cgnat_sip_tcp = VirtualServer2('cgnat_sip_tcp')
        cgnat_sip_tcp.properties.destination = str(IPAddressRdPort('0.0.0.0',
                                                                   rd=rd.id(), port=self.vs_port))
        cgnat_sip_tcp.properties.mask = str(IPAddressRd('0.0.0.0'))
        cgnat_sip_tcp.properties.source = str(IPNetworkRd('0.0.0.0/0', rd=rd.id()))
        self.folder.hook(cgnat_sip_tcp)

        profile_fastL4 = Profile('fastL4')
        self.common.hook(profile_fastL4)

        cgnat_http = VirtualServer2('cgnat_http')
        cgnat_http.properties.destination = str(IPAddressRdPort('0.0.0.0',
                                                                rd=rd.id(), port=8080))
        cgnat_http.properties.ip_forward = RawEOL
        cgnat_http.properties.mask = str(IPAddressRd('0.0.0.0'))
        cgnat_http.properties.source = str(IPNetworkRd('10.80.0.0/16', rd=rd.id()))
        cgnat_http.properties.source_address_translation = {}
        cgnat_http.properties.source_address_translation.type = 'lsn'
        cgnat_http.properties.source_address_translation.pool = lsnpool
        cgnat_http.properties.translate_address = 'disabled'
        cgnat_http.properties.translate_port = 'disabled'
        cgnat_http.properties.profiles = references(profile_fastL4)
        cgnat_http.properties.vlans = references(*all_vlans)
        cgnat_http.properties.vlans_disabled = lambda k, d: d.pop(k)
        cgnat_http.properties.vlans_enabled = RawEOL
        self.folder.hook(cgnat_http)

        profile_rtsp = Profile('rtsp')
        profile_rtsp.context = 'clientside'
        self.common.hook(profile_rtsp)

        cgnat_rtsp = VirtualServer2('cgnat_rtsp')
        cgnat_rtsp.properties.destination = str(IPAddressRdPort('0.0.0.0',
                                                                rd=rd.id(), port=554))
        cgnat_rtsp.properties.mask = str(IPAddressRd('0.0.0.0'))
        cgnat_rtsp.properties.source = str(IPNetworkRd('10.80.0.0/16', rd=rd.id()))
        cgnat_rtsp.properties.source_address_translation = {}
        cgnat_rtsp.properties.source_address_translation.type = 'lsn'
        cgnat_rtsp.properties.source_address_translation.pool = lsnpool3
        cgnat_rtsp.properties.translate_address = 'disabled'
        cgnat_rtsp.properties.translate_port = 'disabled'
        cgnat_rtsp.properties.profiles = references(profile_rtsp, profile_tcp)
        self.folder.hook(cgnat_rtsp)

        return self.tree


class PPTPConfig(BaseConfig):

    def __init__(self, node_ips, vs_ip, vs_port=1723, *args, **kwargs):
        self.node_ips = node_ips
        self.vs_ip = vs_ip
        self.vs_port = vs_port
        super(PPTPConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('PPTP configuration')
        v = self.context.version
        if not (v.product.is_bigip and v >= 'bigip 12.0.0'):
            LOG.info('Sorry, PBA mode support not available in this version.')
            return self.tree

        rd = self.route_domain

        profile_pptp = Profile('pptp')
        profile_tcp = Profile('tcp')
        pem_profile = ProfileSpm('A_PEM_80_pem_profile')
        pem_profile.context = 'clientside'
        self.common.hook(profile_pptp, profile_tcp)
        self.folder.hook(pem_profile)

        lsn_log_profile = LsnLogProfile('lsn_log_profile')

        lsnpool = LsnPool('LSN_Pool_PBA')
        lsnpool.properties.client_connection_limit = 10000
        lsnpool.properties.log_profile = str(lsn_log_profile)
        lsnpool.properties.log_publisher = '/Common/local-db-publisher'
        lsnpool.properties.members = [str(IPNetworkRd('8.8.8.0/28', rd=rd.id()))]
        lsnpool.properties.mode = 'pba'
        lsnpool.properties.persistence = dict(mode='address-port', timeout=30)
        lsnpool.properties.port_block_allocation = dict(block_idle_timeout=30)
        lsnpool.properties.translation_port_range = '32769-65535'
        self.folder.hook(lsnpool)

        pptp_vs = VirtualServer2('PPTP_VS_PBA')
        pptp_vs.properties.destination = str(IPAddressRdPort(self.vs_ip,
                                             rd=rd.id(), port=self.vs_port))
        pptp_vs.properties.source = IPNetworkRd('0.0.0.0/0', rd=rd.id())
        pptp_vs.properties.source_address_translation = {}
        pptp_vs.properties.source_address_translation.type = 'lsn'
        pptp_vs.properties.source_address_translation.pool = lsnpool
        pptp_vs.properties.profiles = references(pem_profile, profile_tcp,
                                                 profile_pptp)
        self.folder.hook(pptp_vs)

        return self.tree
