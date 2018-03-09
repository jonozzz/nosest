'''
Created on Apr 12, 2013

@author: jono
'''
from .scaffolding import Stamp
from ...utils.parsers.tmsh import RawDict, RawEOL
from ...utils.net import IPNetworkRd
from netaddr import IPNetwork
from .scaffolding import PropertiesStamp
import numbers


can_tmsh = lambda v: (v.product.is_bigip and v >= 'bigip 11.0.0' or
                      v.product.is_em and v >= 'em 2.0.0' or
                      v.product.is_bigiq or v.product.is_iworkflow)


class SelfIP(Stamp):
    TMSH = """
        net self %(key)s {
            address fd32:f5:0:a0a::15ec/64
            allow-service {
                default
            }
            fw-rules {
                aaaaa {
                    description none
                    rule-list rule_list1
                }
                bbbb {
                    rule-list _sys_self_allow_all
                }
            }
            vlan internal
        }
    """
    BIGPIPE = """
        self %(address)s {
           netmask 255.255.0.0
           vlan internal
           allow default
        }
    """

    def __init__(self, address, vlan, name=None, allow=None, rules=None):
        self.address = address if isinstance(address, IPNetwork) else IPNetworkRd(address)
        self.vlan = vlan
        self.name = name or str(address).replace('/', '_')
        self.allow = allow or ['default']
        self.rules = rules or []
        #self.rd = rd
        super(SelfIP, self).__init__()

    def tmsh(self, obj):
        # We don't want to use tmsh to set selfIPs on BIGIQ because of reasons.
        v = self.folder.context.version
        if v.product.is_bigiq and v >= 'bigiq 4.2.0' or v < 'bigiq 4.0' or \
           v >= 'iworkflow 2.0':
            return None, None
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        value = obj.rename_key('net self %(key)s', key=key)
        value['allow-service'] = dict((x, RawEOL) for x in self.allow)
        #value['fw-rules'] = dict((x, RawEOL) for x in self.rules)
        if self.rules:
            value['fw-rules'].clear()
            map(lambda x: value['fw-rules'].update(x.get_for_firewall()),
                self.rules)
        else:
            #LOG.info('AFM not provisioned')
            value.pop('fw-rules')
        #rd_suffix = '%' + str(self.rd.id_) if self.rd else ''
        #value['address'] = "{0.ip}{1}/{0.prefixlen}".format(self.address, rd_suffix)
        value['address'] = str(self.address)
        value['vlan'] = self.vlan.get(reference=True)
        return key, obj

    def bigpipe(self, obj):
        key = str(self.address.ip)
        value = obj.rename_key('self %(address)s', address=key)
        value['netmask'] = str(self.address.netmask)
        if len(self.allow) == 1:
            value['allow'] = self.allow[0]
        else:
            value['allow'] = dict(x.split(':') for x in self.allow)
        value['vlan'] = self.vlan.get(reference=True)
        return key, obj


class SelfIP2(PropertiesStamp):
    TMSH = """
    net self %(key)s {
        address 10.75.2.45/24
        address-source from-user
        allow-service {
            default
        }
        app-service none
        description none
        floating disabled
#        fw-enforced-policy none
#        fw-staged-policy none
        inherited-traffic-group false
        partition Common
        service-policy none
        traffic-group traffic-group-local-only
        unit 0
        vlan vlan_3563
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 12.0':  # failed on 11.5.5, 11.6.3
                values.pop('address-source')
                values.pop('service-policy')
            return self.get_full_path(), obj


class Trunk(Stamp):
    TMSH = """
        net trunk %(name)s {
            lacp disabled
            interfaces {
                1/1.2
                2/1.2
                3/1.2
                4/1.2
                5/1.2
                6/1.2
                7/1.2
                8/1.2
            }
            link-select-policy auto
        }
    """
    BIGPIPE = """
        trunk %(name)s {
            lacp disable
            interfaces {
                1/1.1
                2/1.1
                3/1.1
                4/1.1
            }
        }
    """

    def __init__(self, name, interfaces=None, lacp=None, \
                 link_select_policy=None):
        self.name = name
        self.interfaces = interfaces or set()
        self.lacp = lacp
        self.link_select_policy = link_select_policy
        super(Trunk, self).__init__()

    def compile(self):
        v = self.folder.context.version
        if can_tmsh(v):
            key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
            obj = self.from_template('TMSH')
            value = obj.rename_key('net trunk %(name)s', name=self.name)
            if self.interfaces:
                value['interfaces'].clear()
                value['interfaces'].update(dict((x, RawEOL) for x in self.interfaces))
            else:
                value.pop('interfaces')
            if self.lacp:
                value['lacp'] = 'enabled'
            if self.link_select_policy:
                value['link-select-policy'] = self.link_select_policy
        else:
            key = obj = None
        return key, obj


class Vlan(Stamp):
    TMSH = """
        net vlan %(name)s {
#            if-index 128
            partition Part1
            interfaces {
                1.3 {
                    tagged
                }
            }
#            tag 4092
        }
    """
    BIGPIPE = """
        vlan %(name)s {
           interfaces {
               1.1
           }
        }
    """

    def __init__(self, name, untagged=None, tagged=None, tag=None):
        self.name = name
        self.untagged = untagged or []
        self.tagged = tagged or []
        self.tag = tag
        super(Vlan, self).__init__()

    def tmsh(self, obj):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        partition = self.folder.partition().name
        value = obj.rename_key('net vlan %(name)s', name=self.name)
        value['description'] = self.name
        value['partition'] = partition
        if self.untagged or self.tagged:
            value['interfaces'].clear()
            value['interfaces'].update(dict((x, []) for x in self.untagged))
            value['interfaces'].update(dict((x, ['tagged']) for x in self.tagged))
        else:
            value.pop('interfaces')
        if self.tagged:
            value['tag'] = self.tag

        return key, obj

    def bigpipe(self, obj):
        v = self.folder.context.version
        key = self.name
        #partition = self.folder.partition().name
        if v.product.is_bigip and v < 'bigip 10.0':
            D = RawDict
        else:
            D = dict

        value = obj.rename_key('vlan %(name)s', name=self.name)
        if self.untagged:
            value['interfaces'] = D()
            value['interfaces'].update(D((x, RawEOL) for x in self.untagged))
        else:
            value.pop('interfaces')

        if self.tagged:
            value['tag'] = self.tag
            value['interfaces tagged'] = D()
            value['interfaces tagged'].update(D((x, RawEOL) for x in self.tagged))

        return key, obj


class RouteDomain(Stamp):
    TMSH = """
        net route-domain %(name)s {
            description none
            id 0
            partition Common
#            parent /Common/0
            fw-rules {
                aaaaa {
                    description none
                    rule-list rule_list1
                }
                bbbb {
                    rule-list _sys_self_allow_all
                }
            }
            vlans {
                /Part1/ha
                /Part1/ga-ha
                internal
                external
                v1-a
            }
        }
    """

    def __init__(self, id_, name=None, vlans=None, parent=None, rules=None):
        assert isinstance(id_, numbers.Integral)
        self.id_ = id_
        self.name = name or id_
        self.vlans = vlans or []
        self.parent = parent
        self.rules = rules or []
        super(RouteDomain, self).__init__()

    def id(self):
        return self.id_

    def compile(self):
        ctx = self.folder.context
        v = ctx.version
        if can_tmsh(v):
            key = self.name
            partition = self.folder.partition().name
            obj = self.from_template('TMSH')
            value = obj.rename_key('net route-domain %(name)s', name=self.name)
            value['id'] = self.id_
            value['partition'] = partition
            if self.vlans:
                value['vlans'].clear()
                value['vlans'].update(dict((x.get(reference=True), RawEOL) for x in self.vlans))
            else:
                value.pop('vlans')
            if self.parent:
                value['parent'] = self.parent

            if ctx.provision.afm and self.rules:
                value['fw-rules'].clear()
                map(lambda x: value['fw-rules'].update(x.get_for_firewall()),
                    self.rules)
            else:
                #LOG.info('AFM not provisioned')
                value.pop('fw-rules')
        else:
            key = obj = None
        return key, obj


class RouteDomain2(PropertiesStamp):
    TMSH = """
    net route-domain %(key)s {
        app-service none
        bwc-policy none
        connection-limit 0
        description none
        flow-eviction-policy none
#        fw-enforced-policy none
#        fw-staged-policy none
        id 0
        ip-intelligence-policy none
        parent none
        partition Common
        routing-protocol none
        service-policy none
        strict enabled
        vlans none
    }
"""

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.6.2':  # failed on 11.5.2, 11.6
                values.pop('connection-limit')
                values.pop('flow-eviction-policy')
                values.pop('service-policy')
                values.pop('ip-intelligence-policy')
            return self.get_full_path(), obj


class Vlan2(PropertiesStamp):
    TMSH = """
    net vlan %(key)s {
        app-service none
        auto-lasthop default
        cmp-hash default
        customer-tag none
        dag-round-robin disabled
        dag-tunnel outer
        description internal
        failsafe disabled
        failsafe-action failover-restart-tm
        failsafe-timeout 90
        if-index 144
        interfaces {
        }
        learning enable-forward
        mtu 1500
        partition Common
        sflow {
            poll-interval 0
            poll-interval-global yes
            sampling-rate 0
            sampling-rate-global yes
        }
        source-checking disabled
        tag 4094
    }
    """

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        return {key: RawEOL}

    def compile(self):
        key, obj = super(Vlan2, self).compile()
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.6.0':  # failed on 11.5.5
                values.pop('dag-tunnel')
                values.pop('customer-tag')
                # interfaces:
                #     1.1:
                #        tag-mode: xyz
                for value in values.get('interfaces', {}).values():
                    if 'tag-mode' in value:
                        value.pop('tag-mode')
        return key, obj


class FdbVlan(PropertiesStamp):
    TMSH = """
    net fdb vlan %(key)s {
        app-service none
        partition Common
        records none
    }
    """


class NetInterface(PropertiesStamp):
    TMSH = """
    net interface %(key)s {
        media-fixed 1000T-FD
        media-max 10000T-FD
    }
    """
    def tmsh(self, obj):
        return self.name, obj
