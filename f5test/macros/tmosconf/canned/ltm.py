'''
Created on May 4, 2016

@author: jono
'''
import logging

import itertools as IT

from ....utils.net import ip4to6, IPAddressRdPort, IPNetworkRd
from . import BaseConfig
from ..base import (cycle_partition_stamps, count_ip, take, PARTITION_COMMON)
from ..ltm import Node, Pool, VirtualServer, LsnPool, VirtualAddress, \
                    SnatPool, VirtualServer2, PersistenceSSL
from ..profile import Profile, ServerSsl, ClientSsl, references
from ..monitor import Monitor
from ..scaffolding import make_partitions
from ..cm import TrafficGroup
from ..net import Vlan2, FdbVlan
from ..irules import LargeAppRule
from ..LogConfig import LogConfigDestinationRemoteHighspeed, LogConfigPublisher
from ..pem import ProfileSpm
from ..translation import SnatTranslation
from f5test.utils.parsers.tmsh import RawEOL
from copy import copy
from ..scaffolding import enumerate_stamps

NODE_START = '10.10.0.50'
VIP_START = '10.11.0.50'
LOG = logging.getLogger(__name__)


class LTMConfig(BaseConfig):

    def __init__(self, nodes=10, pools=60, members=3, vips=8,
                 node1=NODE_START, vip1=VIP_START, with_monitors=True,
                 *args, **kwargs):
        self.nodes = nodes
        self.pools = pools
        self.members = members
        self.vips = vips
        self.node1 = node1
        self.vip1 = vip1
        self.with_monitors = with_monitors
        super(LTMConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('LTM configuration')
        common = self.tree[PARTITION_COMMON]
        all_partitions = tuple(self.tree.enumerate(False))

        LOG.info('Generating built-in profiles in Common partition...')
        profile_serverssl = ServerSsl('serverssl')
        profile_clientssl = ClientSsl('clientssl')
        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        self.common.hook(profile_serverssl, profile_clientssl, profile_http, profile_tcp)

        LOG.info('Generating nodes...')
        default_monitors = ['gateway_icmp'] if self.with_monitors else []
        v4nodes = count_ip(self.node1)
        all_folders = IT.cycle(self.tree.enumerate())
        all_nodes = dict((x.name, []) for x in all_partitions)
        for _ in range(self.nodes):
            ipv4 = next(v4nodes)
            n = Node(ipv4, name='Node_%s' % _,
                     monitors=default_monitors)
            n6 = Node(ip4to6(ipv4, prefix=16), name='Nodev6_%s' % _,
                      monitors=default_monitors)
            folder = next(all_folders)
            folder.hook(n, n6)
            all_nodes[folder.partition().name] += (n, n6)

        LOG.info('Generating pools...')
        http_ports = IT.repeat(80)
        https_ports = IT.repeat(443)
        monitors = IT.repeat(None)
        http_pools = dict((x.name, []) for x in all_partitions)
        https_pools = dict((x.name, []) for x in all_partitions)
        all_nodes = cycle_partition_stamps(all_nodes)
        for _ in range(self.pools):
            folder = next(all_folders)
            nodes = take(self.members, all_nodes[folder.partition().name])
            p = Pool('Pool%d-a' % _, nodes, http_ports, monitors,
                     pool_monitors=default_monitors)
            p2 = Pool('Pool%d-b' % _, nodes, https_ports, monitors,
                      pool_monitors=default_monitors)
            folder.hook(p, p2)
            http_pools[folder.partition().name].append(p)
            https_pools[folder.partition().name].append(p2)

        LOG.info('Generating virtual servers...')
        http_pools = cycle_partition_stamps(http_pools)
        https_pools = cycle_partition_stamps(https_pools)
        profiles = IT.cycle([(profile_http, profile_tcp),
                             (profile_serverssl, profile_http, profile_tcp),
                             (profile_clientssl, profile_serverssl, profile_http, profile_tcp)])
        # server_profiles = IT.cycle([])
        v4vips = count_ip(self.vip1)
        if not self.vip1:
            self.vips = 0
        for _ in range(self.vips):
            folder = next(all_folders)
            http_pool = next(http_pools[folder.partition().name])
            ipv4 = next(v4vips)
            # profile = profiles.next()
            # http_port = http_ports.next()
            vs = VirtualServer('VS%d-a' % _, ipv4, 80,
                               http_pool, next(profiles))

            https_pool = next(https_pools[folder.partition().name])
            vs2 = VirtualServer('VS%d-b' % _, ip4to6(ipv4, prefix=16), 80,
                                https_pool, next(profiles))

            https_pool = next(https_pools[folder.partition().name])
            vs3 = VirtualServer('VS%d-c' % _, ipv4, 443,
                                https_pool, next(profiles))

            folder.hook(vs, vs2, vs3)
        return self.tree


class NateIpv6LtmConfig1(BaseConfig):

    def __init__(self, node_ips, mac_addr, snat_addrs, vs_ipv6s=None,
                 vs_ports=None, with_monitors=True, *args, **kwargs):
        self.node_ips = node_ips
        self.traffic_group_mac_addr = mac_addr
        self.snat_addrs = snat_addrs
        self.vs_ipv6s = vs_ipv6s
        self.vs_ports = vs_ports
        self.with_monitors = with_monitors
        super(NateIpv6LtmConfig1, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('NateIpv6LtmConfig configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)
        common = self.tree[PARTITION_COMMON]

        traffic_group = TrafficGroup('traffic-group-1')
        traffic_group.properties.description = "floating traffic group for unit 1"
        if hasattr(self, 'traffic_group_mac_addr'):
            traffic_group.properties.mac = self.traffic_group_mac_addr
        traffic_group.properties.unit_id = 1
        common.hook(traffic_group)

        if self.snat_addrs:
            snat_pool = SnatPool('v6_CG_604')
            snat_pool.properties.members = {}
            for addr in self.snat_addrs:
                snat_pool.properties.members[addr] = RawEOL
            common.hook(snat_pool)

        fdb_vlan = FdbVlan('CG_604')
        common.hook(fdb_vlan)

        http_monitor = Monitor('http')
        common.hook(http_monitor)
        pool_monitors = []
        pool_monitors.append(http_monitor)

        all_nodes = []
        rd = self.route_domain
        for ip in self.node_ips:
            node = Node(ip, rd=rd)
            common.hook(node)
            all_nodes.append(node)

        http_ports = IT.repeat(80)
        pool = Pool('V6_pool_in_ixia', all_nodes, http_ports,
                    pool_monitors=pool_monitors,
                    load_balancing_mode='ratio-member')
        common.hook(pool)

        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        profile_analytics = Profile('analytics')
        profile_fastL4 = Profile('fastL4')
        common.hook(profile_analytics, profile_http, profile_tcp, profile_fastL4)

        profile_ssl = Profile('clientssl-insecure-compatible')
        profile_ssl.context = 'clientside'
        common.hook(profile_ssl)

        profiles = []
        profiles.append([profile_analytics, profile_http, profile_tcp])
        profiles.append([profile_ssl, profile_tcp])
        profiles.append([profile_fastL4])

        for i in range(len(self.vs_ipv6s)):
            name = 'AAAA_s10{0}-v6'.format(i)

            virtual_address = VirtualAddress(self.vs_ipv6s[i])
            virtual_address.properties.address = self.vs_ipv6s[i]
            virtual_address.properties.arp = 'enabled'
            virtual_address.properties.icmp_echo = 'enabled'

            if self.traffic_group_mac_addr:
                virtual_address.properties.traffic_group = traffic_group
            common.hook(virtual_address)

            virtual = VirtualServer2(name)
            virtual.properties.source = '::/0'
            virtual.properties.destination = IPAddressRdPort(self.vs_ipv6s[i],
                                                        port=self.vs_ports[i])
            virtual.properties.mask = 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff'

            virtual.properties.pool = pool
            virtual.properties.profiles = references(*profiles[i])
            virtual.properties.source_address_translation = {}
            virtual.properties.source_address_translation.type = 'snat'
            virtual.properties.source_address_translation.pool = snat_pool
            virtual.properties.translate_address = 'enabled'
            virtual.properties.translate_port = 'enabled'

            common.hook(virtual)

        return tree


class NateIpv4LtmConfig2(BaseConfig):

    def __init__(self, cgnatixia_ips, cgnat_ips, ixiassl_ips, mac_addr,
                 snat_addrs, rhsl_ip, vs_ipv4s=None, vs_ports=None,
                 with_monitors=True, *args, **kwargs):
        self.cgnatixia_ips = cgnatixia_ips
        self.cgnat_ips = cgnat_ips
        self.ixiassl_ips = ixiassl_ips
        self.snat_addrs = snat_addrs
        self.vs_ipv4s = vs_ipv4s
        self.vs_ports = vs_ports
        self.with_monitors = with_monitors
        self.traffic_group_mac_addr = mac_addr
        self.rhsl_ip = rhsl_ip
        super(NateIpv4LtmConfig2, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('LTM3 configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)

        common = self.tree[PARTITION_COMMON]

        gateway_monitor = Monitor('gateway_icmp')
        pool_monitors = []
        pool_monitors.append(gateway_monitor)

        snat_pool = SnatPool('v4_CG_604')
        snat_pool.properties.members = {}
        for addr in self.snat_addrs:
            snat_pool.properties.members[addr] = RawEOL
        common.hook(snat_pool)

        traffic_group = None
        for tg in (enumerate_stamps(self.tree, TrafficGroup)):
            if (tg.name == 'traffic-group-1'):
                traffic_group = tg
                break
        if (traffic_group is None):
            traffic_group = TrafficGroup('traffic-group-1')
            traffic_group.properties.description = "floating traffic group for unit 1"
            if hasattr(self, 'traffic_group_mac_addr'):
                traffic_group.properties.mac = self.traffic_group_mac_addr
            traffic_group.properties.unit_id = 1
            common.hook(traffic_group)

        # Creating nodes and pools
        all_nodes = []
        rd = self.route_domain
        # if self.node_ips:
        for l in self.cgnatixia_ips, self.cgnat_ips, self.ixiassl_ips:
            for ip in l:
                node = Node(ip, rd=rd)
                common.hook(node)
                all_nodes.append(node)

        http_ports = IT.repeat(0)
        start_idx = 0
        end_idx = len(self.cgnatixia_ips)
        ssl_pool = Pool('cgnat_ixia_ssl_pool', all_nodes[start_idx:end_idx],
                        http_ports, pool_monitors=pool_monitors)
        common.hook(ssl_pool)

        http_monitor = Monitor('http')
        common.hook(http_monitor)
        pool_monitors = []
        pool_monitors.append(http_monitor)

        http_ports = IT.repeat(80)
        start_idx = end_idx
        end_idx += len(self.cgnat_ips)
        cgnat_pool = Pool('cgnat_pool', all_nodes[start_idx:end_idx],
                          http_ports, pool_monitors=pool_monitors,
                          descriptions=['Ixia HTTP server',
                                        'HTTP Server ESXI2 Web server'])

        common.hook(cgnat_pool)

        http_ports = IT.repeat(80)
        pool_monitors = []
        pool_monitors.append(gateway_monitor)
        start_idx = end_idx
        end_idx += len(self.ixiassl_ips)
        ixia_pool = Pool('ixia_http_server_pool', all_nodes[start_idx:end_idx],
                         http_ports, pool_desc='ixia_http_server_pool',
                         pool_monitors=pool_monitors)
        common.hook(ixia_pool)

        """ Nate's harness has a cluster
        cluster = Cluster('default')
        cluster.properties.address = '172.27.35.75/24'
        cluster.properties.members = {}
        member = {}
        member['address'] = '172.27.35.74'
        member['enabled'] = RawEOL
        cluster.properties.members['1'] = member
        member['address'] = '172.27.35.73'
        member['enabled'] = RawEOL
        cluster.properties.members['2'] = member
        cluster.properties.members['3'] = {}
        common.hook(cluster)
        """

        # creating logs
        assert self.rhsl_ip

        lsn_pools = []
        create_lsn_pools(self.rhsl_ip, rd, common, pool_monitors, lsn_pools)

        # Virtual addresses
        for i in range(len(self.vs_ipv4s)):
            virtual_address = VirtualAddress(self.vs_ipv4s[i])
            virtual_address.properties.address = self.vs_ipv4s[i]
            virtual_address.properties.mask = '255.255.255.255'
            virtual_address.properties.arp = 'enabled'
            virtual_address.properties.icmp_echo = 'enabled'
            virtual_address.properties.traffic_group = traffic_group
            common.hook(virtual_address)

        # Profiles
        profile_clientssl = Profile('clientssl-insecure-compatible')
        profile_clientssl.context = 'clientside'
        profile_tcp_mobile = Profile('tcp-mobile-optimized')
        common.hook(profile_clientssl, profile_tcp_mobile)

        pem_profile = ProfileSpm('A_PEM_80_pem_profile')
        pem_profile.properties.app_service = 'none'
        pem_profile.context = 'clientside'
        common.hook(pem_profile)

        profiles = [profile_clientssl, profile_tcp_mobile, pem_profile]

        http_rule = None
        v = self.context.version
        if (v.product.is_bigip and v >= 'bigip 12.1.0'):
            profile_classic_pem = Profile('classification_pem')
            profile_classic_pem.context = 'clientside'
            common.hook(profile_classic_pem)
            profiles.append(profile_classic_pem)

            http_rule = LargeAppRule(name='PEM_Classify_irule',
                                     app_name='largeHTML_app')
            common.hook(http_rule)
        else:
            LOG.info('classification_pem not available in this version.')

        # Virtual Servers A_PEM_443_SSL
        virtual = VirtualServer2('A_PEM_443_SSL')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[0],
                                                         port=self.vs_ports[0])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = ssl_pool
        virtual.properties.ip_protocol = 'tcp'
        virtual.properties.profiles = references(*profiles)
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'lsn'
        virtual.properties.source_address_translation.pool = lsn_pools[0]
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'

        ssl_persistence = PersistenceSSL('ssl')
        ssl_persistence.default = 'yes'
        common.hook(ssl_persistence)
        virtual.properties.persist = references(ssl_persistence)
        common.hook(virtual)

        # Virtual Server A_PEM_80_HTTP_deterministic
        profiles.pop(0)
        profile_http = Profile('http-transparent')
        common.hook(profile_http)
        profiles.append(profile_http)

        virtual = VirtualServer2('A_PEM_80_HTTP_deterministic')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[1],
                                                         port=self.vs_ports[1])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = cgnat_pool
        virtual.properties.profiles = references(*profiles)

        if not (http_rule is None):
            virtual.properties.rules = references(*[http_rule])

        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'lsn'
        virtual.properties.source_address_translation.pool = lsn_pools[1]
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'
        virtual.properties.persist = references(ssl_persistence)
        common.hook(virtual)

        # VirtualServer A_PEM_80_HTTP
        virtual = VirtualServer2('A_PEM_80_HTTP')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[2],
                                                         port=self.vs_ports[2])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = cgnat_pool
        virtual.properties.profiles = references(*profiles)

        if not (http_rule is None):
            virtual.properties.rules = references(*[http_rule])

        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'lsn'
        virtual.properties.source_address_translation.pool = lsn_pools[0]
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'
        virtual.properties.persist = references(ssl_persistence)
        common.hook(virtual)

        snat_trans = SnatTranslation('10.77.0.20')
        snat_trans.properties.address = '10.77.0.20'
        snat_trans.properties.inherited_traffic_group = 'true'
        snat_trans.properties.traffic_group = traffic_group
        common.hook(snat_trans)

        # Profiles
        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        profile_analytics = Profile('analytics')
        profile_fastL4 = Profile('fastL4')
        common.hook(profile_analytics, profile_http, profile_tcp, profile_fastL4)

        profile_ssl = Profile('clientssl-insecure-compatible')
        profile_ssl.context = 'clientside'
        common.hook(profile_ssl)

        # Virtual Server  A_s100
        virtual = VirtualServer2('A_s100')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[3],
                                                         port=self.vs_ports[3])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = ixia_pool
        profiles = [profile_analytics, profile_http, profile_tcp]
        virtual.properties.profiles = references(*profiles)
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'snat'
        virtual.properties.source_address_translation.pool = snat_pool
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'

        virtual.properties.mirror = 'enabled'
        for vlan in common.content_map.get(Vlan2):
            if (vlan.name == 'CG_604'):
                virtual.properties.vlans = references(vlan)

        virtual.properties.vlans_disabled = lambda k, d: d.pop(k)
        virtual.properties.vlans_enabled = RawEOL
        common.hook(virtual)

        # Virtual Server A_s101_443
        virtual = VirtualServer2('A_s101_443')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[4],
                                                         port=self.vs_ports[4])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = ixia_pool
        profiles = [profile_analytics, profile_http, profile_tcp]
        virtual.properties.profiles = references(*profiles)
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'snat'
        virtual.properties.source_address_translation.pool = snat_pool
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'

        profiles = [profile_ssl, profile_tcp]
        virtual.properties.profiles = references(*profiles)
        common.hook(virtual)

        # Virtual Server A_s102
        virtual = VirtualServer2('A_s102')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[5],
                                                         port=self.vs_ports[5])
        virtual.properties.mask = '255.255.255.255'
        virtual.properties.pool = ixia_pool
        profiles = [profile_fastL4]
        virtual.properties.profiles = references(*profiles)
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.type = 'snat'
        virtual.properties.source_address_translation.pool = snat_pool
        virtual.properties.translate_address = 'enabled'
        virtual.properties.translate_port = 'enabled'
        common.hook(virtual)

        return tree


class NateDiameterLtmConfig3(BaseConfig):

    def __init__(self, node_ips, mac_addr, vs_ipv4s=None, vs_ports=None,
                 with_monitors=True, *args, **kwargs):
        self.node_ips = node_ips
        self.vs_ipv4s = vs_ipv4s
        self.vs_ports = vs_ports
        self.with_monitors = with_monitors
        self.traffic_group_mac_addr = mac_addr
        super(NateDiameterLtmConfig3, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('NateDiameterLtmConfig configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)

        common = self.tree[PARTITION_COMMON]

        tcp_monitor = Monitor('tcp')
        common.hook(tcp_monitor)
        pool_monitors = []
        pool_monitors.append(tcp_monitor)

        traffic_group = None
        for tg in (enumerate_stamps(self.tree, TrafficGroup)):
            if (tg.name == 'traffic-group-1'):
                traffic_group = tg
                break

        if (traffic_group is None):
            traffic_group = TrafficGroup('traffic-group-1')
            traffic_group.properties.description = "floating traffic group for unit 1"
            if hasattr(self, 'traffic_group_mac_addr'):
                traffic_group.properties.mac = self.traffic_group_mac_addr
            traffic_group.properties.unit_id = 1
            common.hook(traffic_group)

        LOG.info('...Creating nodes and pools')
        all_nodes = []
        rd = self.route_domain
        for ip in self.node_ips:
            node = Node(ip, rd=rd)
            common.hook(node)
            all_nodes.append(node)

        http_ports = IT.repeat(3868)
        diameter_pool = Pool('Diameter-test', all_nodes, http_ports,
                             pool_monitors=pool_monitors,
                             load_balancing_mode='ratio-session')
        common.hook(diameter_pool)

        # Virtual addresses
        for i in range(len(self.vs_ipv4s)):
            virtual_address = VirtualAddress(self.vs_ipv4s[i])
            virtual_address.properties.address = self.vs_ipv4s[i]
            virtual_address.properties.mask = '255.255.255.255'
            virtual_address.properties.arp = 'enabled'
            virtual_address.properties.icmp_echo = 'enabled'
            virtual_address.properties.traffic_group = traffic_group
            common.hook(virtual_address)

        # Profiles
        profile_diameter = Profile('diameter')
        profile_tcp_lan = Profile('tcp-lan-optimized')
        profile_tcp = Profile('tcp')
        common.hook(profile_diameter, profile_tcp_lan, profile_tcp)

        # Virtual Servers Diameter-13868
        for i in range(len(self.vs_ports)):
            virtual = VirtualServer2('Diameter-' + self.vs_ports[i])
            virtual.properties.source = '0.0.0.0/0'
            virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[0],
                                                             port=self.vs_ports[i])
            virtual.properties.mask = '255.255.255.255'
            virtual.properties.pool = diameter_pool
            virtual.properties.ip_protocol = 'tcp'
            if (i == 0):
                virtual.properties.profiles = references(*[profile_diameter,
                                                           profile_tcp_lan])
            else:
                virtual.properties.profiles = references(*[profile_tcp])
            virtual.properties.source_address_translation = {}
            virtual.properties.source_address_translation.type = 'automap'
            virtual.properties.translate_address = 'enabled'
            virtual.properties.translate_port = 'enabled'

            common.hook(virtual)

        return tree


class NateSIPLtmConfig4(BaseConfig):

    def __init__(self, mac_addr, rhsl_ip, vs_ipv4s=None, vs_ports=None,
                 with_monitors=True, *args, **kwargs):
        self.vs_ipv4s = vs_ipv4s
        self.vs_ports = vs_ports
        self.with_monitors = with_monitors
        self.traffic_group_mac_addr = mac_addr
        self.rhsl_ip = rhsl_ip
        super(NateSIPLtmConfig4, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('NateDiameterLtmConfig configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)

        common = self.tree[PARTITION_COMMON]
        rd = self.route_domain

        # Search for pools
        lsn_pool = None
        lsn_determ_pool = None
        for p in (enumerate_stamps(self.tree, LsnPool)):
            if (p.name == 'LSN_Pool'):
                lsn_pool = p
            elif (p.name == 'LSN_Pool_Deterministic'):
                lsn_determ_pool = p

        if (lsn_pool is None) or (lsn_determ_pool is None):
            gateway_monitor = Monitor('gateway_icmp')
            pool_monitors = []
            pool_monitors.append(gateway_monitor)

            lsn_pools = []
            create_lsn_pools(self.rhsl_ip, rd, common, pool_monitors, lsn_pools)
            lsn_pool = lsn_pools[0]
            lsn_determ_pool = lsn_pools[1]

        # Search for existing traffic group
        traffic_group = None
        for tg in (enumerate_stamps(self.tree, TrafficGroup)):
            if (tg.name == 'traffic-group-1'):
                traffic_group = tg
                break

        if (traffic_group is None):
            traffic_group = TrafficGroup('traffic-group-1')
            traffic_group.properties.description = "floating traffic group for unit 1"
            if hasattr(self, 'traffic_group_mac_addr'):
                traffic_group.properties.mac = self.traffic_group_mac_addr
            traffic_group.properties.unit_id = 1
            common.hook(traffic_group)

        v = self.context.version

        # Virtual addresses
        for i in range(len(self.vs_ipv4s)):
            virtual_address = VirtualAddress(self.vs_ipv4s[i])
            virtual_address.properties.address = 'any'
            virtual_address.properties.mask = 'any'
            virtual_address.properties.arp = 'disabled'
            virtual_address.properties.icmp_echo = 'disabled'

            if (v.product.is_bigip and v >= 'bigip 12.1.0'):
                virtual_address.properties.spanning = 'enabled'

            virtual_address.properties.traffic_group = traffic_group
            common.hook(virtual_address)

        # Profiles
        profile_tcp = Profile('tcp-mobile-optimized')
        profile_udp = Profile('udp_decrement_ttl')
        profile_pem = ProfileSpm('A_PEM_80_pem_profile')
        profile_pem.context = 'clientside'
        common.hook(profile_tcp, profile_udp, profile_pem)
        profiles = [profile_pem]

        if (v.product.is_bigip and v >= 'bigip 12.1.0'):
            profile_classic_pem = Profile('classification_pem')
            profile_classic_pem.context = 'clientside'
            common.hook(profile_classic_pem)
            profiles.append(profile_classic_pem)
        else:
            LOG.info('classification_pem not available in this version.')

        # Virtual Servers SIP_TCP_PEM
        profiles1 = copy(profiles)
        profiles1.append(profile_tcp)
        virtual = VirtualServer2('SIP_TCP_PEM')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[0],
                                                         port=self.vs_ports[0])
        virtual.properties.mask = 'any'
        virtual.properties.ip_protocol = 'tcp'
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.pool = lsn_pool
        virtual.properties.source_address_translation.type = 'lsn'
        virtual.properties.profiles = references(*profiles1)
        virtual.properties.translate_address = 'disabled'
        virtual.properties.translate_port = 'enabled'

        common.hook(virtual)

        # Virtual Servers SIP_UDP_PEM
        profiles2 = copy(profiles)
        profiles2.append(profile_udp)
        virtual = VirtualServer2('SIP_UDP_PEM')
        virtual.properties.source = '0.0.0.0/0'
        virtual.properties.destination = IPAddressRdPort(self.vs_ipv4s[0],
                                                         port=self.vs_ports[0])
        virtual.properties.mask = 'any'
        virtual.properties.ip_protocol = 'udp'
        virtual.properties.source_address_translation = {}
        virtual.properties.source_address_translation.pool = lsn_determ_pool
        virtual.properties.source_address_translation.type = 'lsn'
        virtual.properties.profiles = references(*profiles2)
        virtual.properties.translate_address = 'disabled'
        virtual.properties.translate_port = 'enabled'

        common.hook(virtual)

        return tree


def create_lsn_pools(rhsl_ip, rd, folder, pool_monitors, lsn_pools=[]):
        # creating logs
        nodes = []
        rhsl_node = Node(rhsl_ip, rd=rd)
        folder.hook(rhsl_node)
        nodes.append(rhsl_node)

        http_ports = IT.repeat(514)
        rhsl_pool = Pool('rhsl_pool', nodes, http_ports,
                         pool_monitors=pool_monitors,
                         pool_desc='Remote High Speed Logging Pool')
        folder.hook(rhsl_pool)

        rhsl_log_dest = LogConfigDestinationRemoteHighspeed('rhsl_log_destination')
        rhsl_log_dest.properties.pool_name = rhsl_pool
        folder.hook(rhsl_log_dest)

        rhsl_log_publisher = LogConfigPublisher('rhsl_publisher')
        rhsl_log_publisher.properties.description = 'Remote high speed log publisher'
        rhsl_log_publisher.properties.destinations = references(rhsl_log_dest)
        folder.hook(rhsl_log_publisher)

        # LSN Pool
        pool_data = {'LSN_Pool': '6.6.6.0/28',
                     'LSN_Pool_Deterministic': '7.7.7.0/28'}
        for (name, ipaddr) in pool_data.items():
            lsnpool = LsnPool(name)
            lsnpool.properties.egress_interfaces_enabled = RawEOL
            lsnpool.properties.egress_interfaces_disabled = lambda k, d: d.pop(k)
            lsnpool.properties.egress_interfaces = ['CG_600']
            lsnpool.properties.icmp_echo = 'enabled'
            lsnpool.properties.inbound_connections = 'automatic'
            lsnpool.properties.log_publisher = rhsl_log_publisher
            lsnpool.properties.members = [str(IPNetworkRd(ipaddr, rd=rd.id()))]
            lsnpool.properties.persistence = dict(mode='address-port')
            lsnpool.properties.route_advertisement = 'enabled'
            folder.hook(lsnpool)
            lsn_pools.append(lsnpool)
