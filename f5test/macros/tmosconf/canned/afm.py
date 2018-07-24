'''
Created on May 4, 2016

@author: jono
'''
import logging

import itertools as IT

from ....utils.net import IPAddressRd, IPAddressRdPort
from ....utils.dicts import flatten
from ...base import Macro
from ..base import (cycle_partition_stamps, count_ip, take_f, take,
                    cycle_ip_network, next_f, PARTITION_COMMON, RD_START)
from ..ltm import VirtualServer2, VirtualServer
from ..net import (SelfIP, Vlan, RouteDomain, SelfIP2, RouteDomain2)
from ..profile import Profile
from ..scaffolding import make_partitions
from ..security import (AddressList, Rule, RuleList, PortList, RuleDestination,
                        Firewall, Policy, GlobalRules, RuleSource)
from . import BaseConfig


LOG = logging.getLogger(__name__)


class AFMConfig(BaseConfig):

    def __init__(self, address_lists=0, port_lists=1, rules=2,
                 rules_lists=1, vlans=0, self_ips=0, route_domains=1,
                 vips=1, *args, **kwargs):
        self.address_lists = address_lists
        self.port_lists = port_lists
        self.rules = rules
        self.rules_lists = rules_lists
        self.vlans = vlans
        self.self_ips = self_ips
        self.route_domains = route_domains
        self.vips = vips
        super(AFMConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('AFM configuration')
        tree = self.tree
        common = tree[PARTITION_COMMON]
        all_partitions = tuple(tree.enumerate(False))
        all_folders = IT.cycle(tree.enumerate())

        # Cut it short if we're running on a pre-11.3.0 BIGIP.
        v = common.context.version
        if not (v.product.is_bigip and v >= 'bigip 11.3.0'):
            LOG.info('Sorry, no AFM support.')
            return tree

        LOG.info('Generating VLANs...')
        all_vlans = dict((x.name, []) for x in all_partitions)
        all_vlans_nord = dict((x.name, []) for x in all_partitions)
        for _ in range(self.vlans):
            folder = next(all_folders)
            v1 = Vlan('Vlan%d-u' % _)
            v2 = Vlan('Vlan%d-n' % _)
            folder.hook(v1, v2)
            all_vlans[folder.partition().name] += (v1,)
            all_vlans_nord[folder.partition().name] += (v2,)

        LOG.info('Generating address lists...')
        addresses = IT.cycle([('1.1.1.1', '1.1.1.2'),
                             ('1.1.1.0/24', '1.1.2.1', '172.0.0.0/8'),
                             ('::', '0.0.0.0/0'),
                             ('2002::1', 'baad::/16', 'dead:beef::/32')])
        all_address_lists = dict((x.name, []) for x in all_partitions)
        for _ in range(self.address_lists):
            folder = next(all_folders)
            a = AddressList('AddressList%d' % _, next(addresses))
            folder.hook(a)
            all_address_lists[folder.partition().name] += (a,)

        LOG.info('Generating port lists...')
        ports = IT.cycle([(1, 32767, 65535),
                         (443, '443-453', 10000),
                         ('20000-30000', 12345),
                         ('1-65535',)])
        all_port_lists = dict((x.name, []) for x in all_partitions)
        for _ in range(self.port_lists):
            folder = next(all_folders)
            p = PortList('PortList%d' % _, next(ports))
            folder.hook(p)
            all_port_lists[folder.partition().name] += (p,)

        LOG.info('Generating rules...')
        ipv4addresses = count_ip('10.0.0.1')
        ipv6addresses = count_ip('2001::1')
        ports = IT.cycle(range(1, 65536))
        address_lists = cycle_partition_stamps(all_address_lists)
        port_lists = cycle_partition_stamps(all_port_lists)
        all_rules = dict((x.name, []) for x in all_partitions)
        vlans = cycle_partition_stamps(all_vlans)
        for _ in range(self.rules):
            folder = next(all_folders)

            # IPv4 rules
            destination = RuleDestination()
            destination['address-lists'] = take_f(3, address_lists, folder)
            destination['addresses'] += take(4, ipv4addresses)
            destination['port-lists'] = take_f(5, port_lists, folder)
            destination['ports'] = take(6, ports)

            source = RuleSource()
            source['address-lists'] = take_f(3, address_lists, folder)
            source['addresses'] += take(4, ipv4addresses)
            source['port-lists'] = take_f(5, port_lists, folder)
            source['ports'] = take(6, ports)
            source['vlans'] = take_f(3, vlans, folder)

            r = Rule('Rule_v4_%d' % _, destination=destination, source=source)
            all_rules[folder.partition().name] += (r,)

            # IPv6 rules. Management IP address must be ipv6 for this to work.
#             destination = RuleDestination()
#             destination['address-lists'] = take_f(3, address_lists, folder)
#             destination['addresses'] += take(6, ipv6addresses)
#             destination['port-lists'] = take_f(5, port_lists, folder)
#             destination['ports'] = take(6, ports)
#
#             source = RuleSource()
#             source['address-lists'] = take_f(3, address_lists, folder)
#             source['addresses'] += take(6, ipv6addresses)
#             source['port-lists'] = take_f(5, port_lists, folder)
#             source['ports'] = take(6, ports)
#             source['vlans'] = take_f(3, vlans, folder)
#
#             r = Rule('Rule_v6_%d' % _, destination=destination, source=source)
#             all_rules[folder.partition().name] += (r,)

        LOG.info('Generating rule lists...')
        all_rule_lists = dict((x.name, []) for x in all_partitions)
        for _ in range(self.rules_lists):
            #folder = all_folders.next()
            rules = take(5, all_rules[folder.partition().name])
            rl = RuleList('RuleList%d' % _, rules=rules)
            self.common.hook(rl)
            all_rule_lists[self.common.partition().name] += (rl,)

        LOG.info('Generating global firewall...')
        rule_lists = cycle_partition_stamps(all_rule_lists)
        if v >= 'bigip 11.5.1':
            p = Policy('Policy')
            p.properties.rules = flatten(*[x.get_for_firewall() for x in take(5, rule_lists[PARTITION_COMMON])])
            gr = GlobalRules()
            gr.properties.enforced_policy = p
            self.common.hook(p, gr)
        else:
            fw = Firewall(Firewall.types.GLOBAL,  # @UndefinedVariable
                          rules=take(5, rule_lists[PARTITION_COMMON]))
            self.common.hook(fw)

        LOG.info('Generating management firewall...')
        rules = cycle_partition_stamps(all_rules)
        fw = Firewall(Firewall.types.MANAGEMENT_PORT,  # @UndefinedVariable
                      rules=take(5, rules[PARTITION_COMMON]))
        folder.hook(fw)

        LOG.info('Generating Route Domains...')
        all_route_domains = dict((x.name, []) for x in all_partitions)
        vlans = cycle_partition_stamps(all_vlans, infinite=False,
                                       include_common=False)
        vlan_to_rd = {}
        rd_ids = IT.count(RD_START)
        if v >= 'bigip 11.5.1':
            for _ in range(self.route_domains):
                folder = next(all_folders)

                p = Policy('RouteDomain_Policy%d' % _)
                p.properties.rules = flatten(*[x.get_for_firewall() for x in take_f(2, rules, folder) +
                                               take_f(3, rule_lists, folder)])

                _ = take_f(3, vlans, folder)
                rd = RouteDomain2(next(rd_ids))
                rd.properties.id = rd.id_ = rd.name
                rd.properties.fw_enforced_policy = p
                rd.properties.vlans = _ or None
                folder.hook(rd, p)

                vlan_to_rd.update([(v, rd) for v in _])
                all_route_domains[folder.partition().name] += (rd,)
        else:
            for _ in range(self.route_domains):
                folder = next(all_folders)
                _ = take_f(3, vlans, folder)
                rd = RouteDomain(next(rd_ids), rules=take_f(2, rules, folder) +
                                 take_f(3, rule_lists, folder), vlans=_)
                vlan_to_rd.update([(v, rd) for v in _])
                folder.hook(rd)
                all_route_domains[folder.partition().name] += (rd,)

        LOG.info('Generating Self IPs...')
        vlans = cycle_partition_stamps(all_vlans)
        vlans_nord = cycle_partition_stamps(all_vlans_nord)
        selfv4 = cycle_ip_network('10.1.0.1/32')
        selfv6 = cycle_ip_network('dead:beef::1/128')
        if v >= 'bigip 11.5.1':
            for _ in range(self.self_ips):
                folder = next(all_folders)

                vlan = next_f(vlans, folder)

                p = Policy('SelfIP1_Policy%d' % _)
                p.properties.rules = flatten(*[x.get_for_firewall() for x in take_f(3, rules, folder)])
                s = SelfIP2('SelfIP1%d' % _)
                s.properties.address = IPAddressRd(next(selfv4), rd=vlan_to_rd[vlan])
                s.properties.vlan = vlan
                s.properties.fw_enforced_policy = p
                folder.hook(s, p)

                p = Policy('SelfIP2_Policy%d' % _)
                p.properties.rules = flatten(*[x.get_for_firewall() for x in take_f(5, rules, folder)])
                s = SelfIP2('SelfIP2%d' % _)
                s.properties.address = IPAddressRd(next(selfv6), rd=vlan_to_rd[vlan])
                s.properties.vlan = vlan
                s.properties.fw_enforced_policy = p
                folder.hook(s, p)

                p = Policy('SelfIP3_Policy%d' % _)
                p.properties.rules = flatten(*[x.get_for_firewall() for x in take_f(2, rules, folder)])
                s = SelfIP2('SelfIP3%d' % _)
                s.properties.address = next(selfv4)
                s.properties.vlan = next_f(vlans_nord, folder)
                s.properties.fw_enforced_policy = p
                folder.hook(s, p)
        else:
            for _ in range(self.self_ips):
                folder = next(all_folders)
    
                vlan = next_f(vlans, folder)
                s1 = SelfIP(next(selfv4), vlan=vlan, rd=vlan_to_rd[vlan],
                            name='SelfIP%d' % _, rules=take_f(3, rules, folder))
                s2 = SelfIP(next(selfv6), vlan=vlan, rd=vlan_to_rd[vlan],
                            rules=take_f(5, rules, folder))
                s3 = SelfIP(next(selfv4), vlan=next_f(vlans_nord, folder),
                            rules=take_f(2, rules, folder))
                folder.hook(s1, s2, s3)

        LOG.info('Generating Virtual IPs...')
        profile_tcp = Profile('tcp')
        common.hook(profile_tcp)
        route_domains = cycle_partition_stamps(all_route_domains)
        if v >= 'bigip 11.5.1':
            for _ in range(self.vips):
                folder = next(all_folders)

                p = Policy('VSa_Policy%d' % _)
                p.properties.rules = flatten(*[x.get_for_firewall() for x in take_f(5, all_rules, folder)])
                v1 = VirtualServer2('VS%d-a' % _)
                v1.properties.destination = IPAddressRdPort(next(ipv4addresses), port=80)
                v1.properties.fw_enforced_policy = p
                v1.properties.profiles = [profile_tcp]
                folder.hook(p, v1)
        else:
            for _ in range(self.vips):
                folder = next(all_folders)
    
                v1 = VirtualServer('VS%d-a' % _, next(ipv4addresses), 80,
                                   rules=take_f(5, all_rules, folder),
                                   profiles=[profile_tcp])
                v2 = VirtualServer('VS%d-b' % _, next(ipv6addresses), 443,
                                   rules=take_f(5, all_rules, folder),
                                   profiles=[profile_tcp])
                v3 = VirtualServer('VS%d-c' % _, next(ipv6addresses), 443,
                                   rules=take_f(2, all_rules, folder),
                                   profiles=[profile_tcp],
                                   rd=next_f(route_domains, folder))
                folder.hook(v1, v2, v3)

        return tree
