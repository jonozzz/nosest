'''
Created on May 4, 2016

@author: jono
'''
import logging
import netaddr
import itertools as IT

from ..base import (PARTITION_COMMON)
from ..ltm import (Node, Pool, VirtualServer)
from ..net import (RouteDomain)
from ..profile import (Profile, Sip, references)
from ..scaffolding import make_partitions
from ..sip import SipProfileSession, SipProfileRouter, SipRoute, SipTransportConfig, SipPeer
from . import BaseConfig


LOG = logging.getLogger(__name__)


class SIPConfig(BaseConfig):

    def __init__(self, node_ips, vs_ip, vs_port=5060, *args, **kwargs):
        self.node_ips = node_ips
        self.vs_ip = vs_ip
        self.vs_port = vs_port
        super(SIPConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('SIP configuration')

        v = self.context.version
        if not (v.product.is_bigip and v >= 'bigip 11.6.0'):
            LOG.info('Sorry, no SIP session support.')
            return self.tree

        all_nodes = []
        rd = self.route_domain

        mr_sip_lb_session = SipProfileSession('mr_sip_lb_session')
        self.folder.hook(mr_sip_lb_session)

        for ip in self.node_ips:
            node = Node(ip, rd=rd)
            self.folder.hook(node)
            all_nodes.append(node)

        http_ports = IT.repeat(5060)
        mr_sip_pool = Pool('mr_sip_pool', all_nodes, http_ports)
        self.folder.hook(mr_sip_pool)

        profile_tcp = Profile('tcp')
        profile_udp = Profile('udp')
        self.common.hook(profile_tcp, profile_udp)

        mr_t1 = SipTransportConfig('mr_t1')
        mr_t1.properties.profiles = references(profile_tcp, mr_sip_lb_session)
        mr_u1 = SipTransportConfig('mr_u1')
        mr_u1.properties.profiles = references(profile_udp, mr_sip_lb_session)
        mr_u1.properties.ip_protocol = 'udp'
        self.folder.hook(mr_t1, mr_u1)

        mr_peer1 = SipPeer('mr_peer1')
        mr_peer1.properties.pool = mr_sip_pool
        mr_peer1.properties.transport_config = mr_t1
        mr_peer2 = SipPeer('mr_peer2')
        mr_peer2.properties.pool = mr_sip_pool
        mr_peer2.properties.transport_config = mr_u1
        self.folder.hook(mr_peer1, mr_peer2)

        vs_ip = netaddr.IPNetwork(self.vs_ip)

        mr_sip_tcp = VirtualServer('mr_sip_tcp', vs_ip, self.vs_port,
                                   profiles=[profile_tcp, mr_sip_lb_session],
                                   rd=rd)
        mr_sip_udp = VirtualServer('mr_sip_udp', vs_ip, self.vs_port,
                                   profiles=[profile_udp, mr_sip_lb_session],
                                   proto='udp', rd=rd, source='0.0.0.0%{}/0'.format(rd.id_))
        self.folder.hook(mr_sip_tcp, mr_sip_udp)

        mr_route1 = SipRoute('mr_route1')
        mr_route1.properties.peers = references(mr_peer1)
        mr_route1.properties.virtual_server = mr_sip_tcp
        mr_route2 = SipRoute('mr_route2')
        mr_route2.properties.peers = references(mr_peer2)
        self.folder.hook(mr_route1, mr_route2)

        mr_siproute1 = SipProfileRouter('mr_siproute1')
        mr_siproute1.properties.routes = references(mr_route1)
        mr_siproute1.properties.session = dict(transaction_timeout=15)

        mr_siproute2 = SipProfileRouter('mr_siproute2')
        mr_siproute2.properties.routes = references(mr_route2)
        self.folder.hook(mr_siproute1, mr_siproute2)

        mr_sip_tcp.profiles.append(mr_siproute1)
        mr_sip_udp.profiles.append(mr_siproute2)

        sip = Sip('mysip')
        sip.properties.max_sessions_per_registration = 1
        self.folder.hook(sip)

        return self.tree
