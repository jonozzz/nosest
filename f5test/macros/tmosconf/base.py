'''
Created on Jun 10, 2011

@author: jono
'''
import logging

import netaddr

import itertools as IT

from ..base import Macro
from .auth import User, PasswordPolicy
from .net import (SelfIP, SelfIP2, Vlan, Vlan2, RouteDomain, Trunk, NetInterface)
from .scaffolding import Stamp, make_partitions
from .sys import Provision, FeatureModule, Defaults, Platform, DNS, NTP, Mail, Snmp


PARTITION_COMMON = 'Common'
RD_START = 100
FEATURE_MODULES = ('cgnat')
LOG = logging.getLogger(__name__)

__version__ = '0.1'


def cycle_partition_stamps(dictionary, infinite=True, include_common=True):
    """Given a partition -> list of stamps mapping it will return a similar
    mapping but instead of lists there will be cycle iterators.
    Any non-Common partition will have cycle though Common partition elements
    first then through its own."""
    f = IT.cycle if infinite else lambda x: iter(x)
    g = IT.chain if include_common else lambda x, y: iter(y)
    from_common = dictionary[PARTITION_COMMON]
    return dict((k, f(v) if k == PARTITION_COMMON
                else f(g(from_common, v)))
                for k, v in dictionary.items())


def take(n, iterable):
    "Return first n items of the iterable as a list"
    return list(IT.islice(iterable, n))


def take_f(n, mapping, folder):
    "Return first n items of the iterable as a list"
    return take(n, mapping[folder.partition().name])


def next_f(mapping, folder):
    return next(mapping[folder.partition().name])


def count_ip(start):
    "Returns an iterator which generates a new IP string each time"
    ip = netaddr.IPAddress(start)
    while True:
        yield str(ip)
        ip += 1


def cycle_ip_network(start):
    "Returns an iterator which generates a new IP/prefix string each time"
    ip = netaddr.IPNetwork(start)
    while True:
        yield str(ip)
        ip.value += 1


class SystemConfig(Macro):

    def __init__(self, context, mgmtip=None, gateway=None, dhcp=False,
                 nameservers=None, suffixes=None, ntpservers=None,
                 timezone=None, partitions=3, provision=None, users=None,
                 smtpserver=None, hostname=None, tree=None):
        self.context = context
        self.mgmtip = netaddr.IPNetwork(mgmtip or '127.0.0.1/24')
        self.gateway = netaddr.IPAddress(gateway or '0.0.0.0')
        self.dhcp = dhcp
        self.nameservers = nameservers
        self.suffixes = suffixes
        self.ntpservers = ntpservers
        self.timezone = timezone
        self.partitions = partitions
        self.provision = provision or {}
        self.users = users or {}
        self.smtpserver = smtpserver
        self.hostname = hostname
        self.tree = tree
        super(SystemConfig, self).__init__()

    def setup(self):
        LOG.info('Platform configuration')
        tree = self.tree or make_partitions(count=self.partitions,
                                            context=self.context)
        common = tree[PARTITION_COMMON]

        # Constants
        common.hook(Defaults())
        # Management IP
        common.hook(Platform(self.mgmtip, self.gateway, self.hostname,
                             dhcp=self.dhcp))
        # DNS
        if self.nameservers:
            common.hook(DNS(self.nameservers, self.suffixes))
        # NTP
        if self.ntpservers:
            common.hook(NTP(self.ntpservers, self.timezone))

        # Mail
        if self.smtpserver:
            common.hook(Mail(self.smtpserver))

        LOG.info('Generating users...')
        for name, specs in self.users.items():
            if isinstance(specs, str):
                u = User(name, role=specs)
            else:
                u = User(name, **specs)
            common.hook(u)

        LOG.info('Generating PasswordPolicy...')
        p = PasswordPolicy()
        common.hook(p)

        LOG.info('Generating provision...')
        for name, level in self.provision.items():
            if name in FEATURE_MODULES:
                p = FeatureModule(name)
                common.hook(p)
            else:
                p = Provision(name, level)
                common.hook(p)

        return tree


class NetworkConfig(Macro):

    def __init__(self, context, trunks=None, vlans=None, selfips=None, rds=None,
                 interfaces=None, tree=None):
        self.context = context
        self.interfaces = interfaces
        self.trunks = trunks or {}
        self.vlans = vlans or {}
        self.selfips = selfips or {}
        self.rds = rds or []
        self.tree = tree
        super(NetworkConfig, self).__init__()

    def setup(self):
        LOG.info('Network configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)
        common = tree[PARTITION_COMMON]

        # This is a simplified configuration where all interfaces in one VLAN
        # can be either tagged or untagged, and - if using trunks - only one
        # trunk is assigned to one VLAN. Trunks have the same name as the VLANs
        # they assigned to.
        if self.interfaces:
            LOG.info('Generating interfaces...')
            if isinstance(self.interfaces, dict):
                for name, specs in self.interfaces.items():
                    if isinstance(specs, Stamp):
                        i = specs
                    else:
                        i = NetInterface(name, specs)
                    common.hook(i)
            elif isinstance(self.interfaces, list):
                for specs in self.interfaces:
                    i = NetInterface(specs.name, specs.properties)
                    common.hook(i)
            else:
                raise NotImplementedError

        if self.trunks:
            LOG.info('Generating trunks...')
            if isinstance(self.trunks, dict):
                for name, specs in self.trunks.items():
                    if isinstance(specs, Stamp):
                        t = specs
                    else:
                        link_policy = getattr(specs, 'link-select-policy', None)
                        t = Trunk(name, specs.interfaces, specs.lacp,
                                  link_policy)
                    common.hook(t)
            # New format, based on yaml
            elif isinstance(self.trunks, list):
                for specs in self.trunks:
                    if isinstance(specs, Stamp):
                        t = specs
                    else:
                        link_policy = getattr(specs, 'link-select-policy', None)
                        t = Trunk(specs.name, specs.interfaces, specs.lacp,
                                  link_policy)
                    common.hook(t)
            else:
                raise NotImplementedError

        LOG.info('Generating VLANs...')
        vlan_name_map = {}
        if isinstance(self.vlans, dict):
            for name, specs in self.vlans.items():
                if isinstance(specs, Stamp):
                    v = specs
                else:
                    v = Vlan(name=name, untagged=specs.untagged, tagged=specs.tagged,
                             tag=specs.tag)
                common.hook(v)
                vlan_name_map[name] = v
        # New format, based on yaml
        elif isinstance(self.vlans, list):
            for specs in self.vlans:
                t = Vlan2(specs.name, specs.properties)
                common.hook(t)
                vlan_name_map[specs.name] = t
        else:
            raise NotImplementedError

        LOG.info('Generating RDs...')
        # New format, based on yaml
        if isinstance(self.rds, list):
            for specs in self.rds:
                if isinstance(specs, Stamp):
                    t = specs
                else:
                    t = RouteDomain(specs.id, specs.name,
                                    vlans=[vlan_name_map[x] for x in specs.vlans])
                common.hook(t)
        else:
            raise NotImplementedError

        if self.selfips:
            LOG.info('Generating Self IPs...')
            if isinstance(self.selfips, dict):
                for vlan, specs in self.selfips.items():
                    if isinstance(specs, (str, netaddr.IPNetwork)):
                        s = SelfIP(specs, vlan_name_map[vlan])
                        common.hook(s)
                    elif isinstance(specs, (list, tuple)):
                        for x in specs:
                            s = SelfIP(vlan=vlan_name_map[vlan], **x)
                            common.hook(s)
                    else:
                        specs.vlan = vlan_name_map[vlan]
                        s = SelfIP(**specs)
                        common.hook(s)
            elif isinstance(self.selfips, list):
                for specs in self.selfips:
                    specs.vlan = vlan_name_map[specs.properties.vlan]
                    # s = SelfIP(**specs)
                    s = SelfIP2(specs.name, specs.properties)
                    common.hook(s)
        return tree


class SnmpConfig(Macro):

    def __init__(self, context, communities=None, clients=None, tree=None):
        self.context = context
        self.communities = communities or {}
        self.clients = clients or []
        self.tree = tree
        super(SnmpConfig, self).__init__()

    def setup(self):
        LOG.info('Snmp configuration')
        tree = self.tree or make_partitions(count=0, context=self.context)
        common = tree[PARTITION_COMMON]

        snmp = Snmp()
        communities = {}
        for community in self.communities.get('v2c', []):
            key_name = "i%s_%d" % (community, len(list(communities.keys())) + 1)
            LOG.info('Generating V1, V2c community %s...', key_name)
            communities[key_name] = {'community-name': community}
        snmp.properties.communities = communities

        clients = []
        for client in self.clients:
            clients.append(client)
        snmp.properties.allowed_addresses = clients

        common.hook(snmp)
        return tree
