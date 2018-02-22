'''
Created on Apr 12, 2013

@author: jono
'''
from .scaffolding import Stamp, PropertiesStamp
import itertools
import netaddr
from ...utils.parsers import tmsh
from ...utils.parsers.tmsh import RawEOL
from ...utils.net import IPNetworkRd
from collections import OrderedDict
from ...base import AttrDict


class Node(Stamp):
    TMSH = """
        ltm node %(key)s {
           address 10.10.0.1
           #limit 100
           #ratio 1
        }
    """
    BIGPIPE = """
        node %(address)s {
           screen Node-name
           #limit 100
           #ratio 1
        }
    """

    def __init__(self, address, name=None, rd=None, monitors=None):
        self.address = address + '%%%d' % rd.id_ if rd else address
        self.name = name or str(self.address)
        self.rd = rd
        self.monitors = monitors or []
        super(Node, self).__init__()

    def from_template(self, name):
        "This is a major speedup over the deepcopy version"
        if name == 'TMSH':
            return tmsh.GlobDict({'ltm node %(key)s': {}})
        return super(Node, self).from_template(name)

    def tmsh(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip:
            key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
            value = obj.rename_key('ltm node %(key)s', key=key)
            #address = self.address + '%%%d' % self.rd.id_ if self.rd else self.address
            value['address'] = self.address
            if self.monitors:
                value['monitor'] = tmsh.RawString(' and '.join(self.monitors))
            return key, obj

    def bigpipe(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip:
            key = self.name
            value = obj.rename_key('node %(address)s', address=self.address)
            value['screen'] = self.name
            if self.monitors:
                value['monitor'] = tmsh.RawString(' and '.join(self.monitors))
            return key, obj


class Pool(Stamp):
    TMSH = """
        ltm pool %(key)s {
            monitor /Common/gateway_icmp
            load-balancing-mode round-robin
            members {
                /Common/a/b/node_b:80 {
                    address 2002::b
                }
                /Common/a/node_a:80 {
                    address 2002::a
                }
                /Common/aa/node_aa:80 {
                    address 2002::aa
                }
            }
            description none
        }
    """
    BIGPIPE = """
        pool %(name)s {
           monitor all gateway_icmp and http
           members
              10.10.0.50:http
              monitor gateway_icmp
              10.10.0.51:http
              ratio 3
              monitor gateway_icmp and http and https
        }
    """

    def __init__(self, name, nodes, ports, monitors=None, descriptions=None,
                 pool_monitors=None, load_balancing_mode=None, pool_desc=None):
        self.name = name
        self.nodes = nodes
        self.ports = ports
        self.monitors = monitors or itertools.repeat(None)
        self.descriptions = descriptions or itertools.repeat(None)
        self.pool_monitors = pool_monitors
        self.load_balancing_mode = load_balancing_mode
        self.pool_description = pool_desc
        super(Pool, self).__init__()

    def from_template(self, name):
        "This is a major speedup over the deepcopy version"
        if name == 'TMSH':
            return tmsh.GlobDict({'ltm pool %(key)s': {'members': {},
                                                       'monitor': None}})
        return super(Pool, self).from_template(name)

    def get_separator(self, address):
        if netaddr.IPAddress(address).version == 4:
            return ':'
        else:
            return '.'

    def set_monitor(self, value, monitor):
        monitors = ''
        if isinstance(monitor, basestring):
            monitors += monitor
        else:
            if monitor:
                monitors += ' and '.join(monitor)

        if monitors:
            value['monitor'] = tmsh.RawString(monitors)

    def tmsh(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip:
            key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
            value = obj.rename_key('ltm pool %(key)s', key=key)

            if self.pool_monitors:
                if isinstance(self.pool_monitors[0], basestring):
                    value.update({'monitor': ' and '.join(self.pool_monitors)})
                else:
                    value.update({'monitor': ' and '.join(monitor.get_full_path()
                                        for monitor in self.pool_monitors)})
            else:
                value.pop('monitor')

            if self.load_balancing_mode:
                value.update({'load-balancing-mode': self.load_balancing_mode})

            if self.pool_description:
                value.update({'description': self.pool_description})

            members = value['members']
            members.clear()
            for node, port, monitor, desc in itertools.izip(self.nodes,
                                                            self.ports,
                                                            self.monitors,
                                                            self.descriptions):
                member = node.get(reference=True)
                if isinstance(member, basestring) and \
                   isinstance(node.address, basestring) and \
                   (node.address in member):
                    address = node.address[:node.address.find('%')]
                    sep = self.get_separator(address)
                else:
                    sep = ':'
                member = '%s%s%s' % (member, sep, port)

                members[member] = {'address': node.address}
                if desc:
                    members[member].update({'description': desc})

                self.set_monitor(members[member], monitor)
            return key, obj

    def bigpipe(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip:
            key = self.name
            value = obj.rename_key('pool %(name)s', name=self.name)
            value.clear()
            if self.pool_monitors:
                value.update({tmsh.RawString('monitor all'): ' and '.join(self.pool_monitors)})
            value.update({'members': RawEOL})
            for node, port, monitor in itertools.izip(self.nodes,
                                                      self.ports,
                                                      self.monitors):
                address = node.address
                sep = self.get_separator(address)
                member = '%s%s%s' % (address, sep, port)

                value[member] = RawEOL
                self.set_monitor(value, monitor)
            return key, obj


class VirtualServer(Stamp):
    TMSH = """
        ltm virtual %(key)s {
            address-status yes
            #app-service none
            auth none
            auto-lasthop default
            bwc-policy none
            clone-pools none
            cmp-enabled yes
            connection-limit 0
            description none
            destination 1.1.1.1:http
            enabled
            fallback-persistence none
            flow-eviction-policy none
            fw-enforced-policy none
            fw-staged-policy none
            gtm-score 0
            ip-intelligence-policy none
            ip-protocol tcp
            last-hop-pool none
            mask 255.255.255.255
            metadata none
            mirror disabled
            mobile-app-tunnel disabled
            nat64 disabled
            partition Common
            per-flow-request-access-policy none
            persist none
            policies none
            pool none
            profiles {
                tcp {
                    context all
                }
            }
            rate-class none
            rate-limit disabled
            rate-limit-dst-mask 0
            rate-limit-mode object
            rate-limit-src-mask 0
            related-rules none
            rules none
            security-log-profiles none
            service-down-immediate-action none
            service-policy none
            source 0.0.0.0/0
            source-address-translation {
                pool none
                type automap
            }
            source-port preserve
            syn-cookie-status not-activated
            traffic-classes none
            translate-address enabled
            translate-port enabled
            urldb-feed-policy none
            vlans none
            vlans-disabled
            vs-index 26
        }
        #ltm virtual-address %(key_va)s {
        #    address 10.11.0.1
        #    mask 255.255.255.255
        #    traffic-group /Common/traffic-group-1
        #}
    """
    BIGPIPE = """
        virtual %(name)s {
           destination 10.11.0.1:80
           snat automap
           ip protocol tcp
           profile clientssl serverssl http tcp
           pool none
        }
    """

    def __init__(self, name, address, port, pool=None, profiles=None, rules=None,
                 rd=None, proto='tcp', source=None, options=None):
        self.name = name
        self.address = IPNetworkRd(address)
        self.address_str = str(self.address.ip)
        self.port = port
        self.pool = pool
        self.profiles = profiles or []
        self.rules = rules or []
        self.rd = rd
        self.proto = proto
        self.source = source
        self.options = options or AttrDict()
        super(VirtualServer, self).__init__()

    def from_template(self, name):
        "This is a major speedup over the deepcopy version"
        if name == 'TMSH':
            return tmsh.GlobDict({'ltm virtual %(key)s': {'profiles': {},
                                                          'fw-rules': {},
                                                          'snat': 'automap',
                                                          'ip-protocol': 'tcp',
                                                          'pool': 'none'}})
                                    # 'ltm virtual-address %(key_va)s': {}})
        return super(VirtualServer, self).from_template(name)

    def get_address_port(self):
        if self.address.version == 4:
            sep = ':'
        else:
            sep = '.'
        address = self.address_str + '%%%d' % self.rd.id_ if self.rd else self.address_str
        return "%s%s%s" % (address, sep, self.port)

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        o = self.options
        if v.product.is_bigip:
            folder_path = self.folder.key()
            key = self.folder.SEPARATOR.join((folder_path, self.name))
            key_va = self.folder.SEPARATOR.join((folder_path, self.address_str))
            obj = self.from_template('TMSH')

            # Update the virtual part
            value = obj.rename_key('ltm virtual %(key)s', key=key)
            value['destination'] = self.get_address_port()
            value['mask'] = str(self.address.netmask)
            value['ip-protocol'] = self.proto
            value['profiles'] = OrderedDict()
            for profile in self.profiles:
                value['profiles'].update(profile.get_vs_profile())

            if self.pool:
                value['pool'] = self.pool.get(reference=True)

            if ctx.provision.afm and self.rules:
                value['fw-rules'].clear()
                map(lambda x: value['fw-rules'].update(x.get_for_firewall()),
                    self.rules)
            else:
                # LOG.info('AFM not provisioned')
                value.pop('fw-rules')

            # Update the virtual-address part
            # value = obj.rename_key('ltm virtual-address %(key_va)s',
            #                       key_va=key_va)
            # value['address'] = self.address_str + '%%%d' % self.rd.id_ if self.rd \
            #    else self.address_str

            if o.source_address_translation:
                value['source-address-translation']['type'] = o['source_address_translation']
                value['source-address-translation']['pool'] = o.get('source_address_translation_pool')


            return key, obj

    def bigpipe(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip:
            key = self.name
            obj = self.from_template('BIGPIPE')
            value = obj.rename_key('virtual %(name)s', name=self.name)
            value.clear()
            value['destination'] = self.get_address_port()
            value['profiles'] = tmsh.RawString(' '.join([x.get_vs_profile() for x in self.profiles]))
            if self.pool:
                value['pool'] = self.pool.get(reference=True)
            return key, obj


class Node2(PropertiesStamp):
    TMSH = r"""
    ltm node %(key)s {
        address none
        app-service none
        connection-limit 0
        description none
        dynamic-ratio 1
        ephemeral false
        fqdn {
            address-family ipv4
            autopopulate disabled
            down-interval 5
            interval 3600
            name none
        }
        logging disabled
        metadata none
        monitor gateway_icmp
        partition Common
        rate-limit disabled
        ratio 1
        session monitor-enabled
        state up
    }
    """

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        add = AttrDict()
        add.address = self.properties['address']
        return {key: add}


class Pool2(PropertiesStamp):
    TMSH = r"""
    ltm pool %(key)s {
        allow-nat yes
        allow-snat yes
        app-service none
        autoscale-group-id none
        description none
        gateway-failsafe-device none
        ignore-persisted-weight disabled
        ip-tos-to-client pass-through
        ip-tos-to-server pass-through
        link-qos-to-client pass-through
        link-qos-to-server pass-through
        load-balancing-mode round-robin
        members {
        }
        metadata none
        min-active-members 0
        min-up-members 0
        min-up-members-action failover
        min-up-members-checking disabled
        monitor gateway_icmp
        partition Common
        profiles none
        queue-depth-limit 0
        queue-on-connection-limit disabled
        queue-time-limit 0
        reselect-tries 0
        service-down-action none
        slow-ramp-time 10
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.6.2':  # failed on 11.5, 11.6
                values.pop('autoscale-group-id')
            return self.get_full_path(), obj

class HttpMonitor(PropertiesStamp):
    TMSH = r"""
        ltm monitor http %(key)s {
            adaptive disabled
            adaptive-divergence-type relative
            adaptive-divergence-value 25
            adaptive-limit 200
            adaptive-sampling-timespan 300
            app-service none
            defaults-from none
            description none
            destination *:*
            interval 5
            ip-dscp 0
            manual-resume disabled
            partition Common
            password none
            recv none
            recv-disable none
            reverse disabled
            send "GET /\r\\n"
            time-until-up 0
            timeout 16
            transparent disabled
            up-interval 0
            username none
        }
    """

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        return {key: RawEOL}


class VirtualServer2(PropertiesStamp):
    TMSH = r"""
    ltm virtual %(key)s {
        address-status yes
        app-service none
        auth none
        auto-lasthop default
        bwc-policy none
        clone-pools none
        cmp-enabled yes
        connection-limit 0
        description none
        destination 10.11.138.57:http
        enabled
        fallback-persistence none
        flow-eviction-policy none
        gtm-score 0
        ip-protocol tcp
        last-hop-pool none
        mask 255.255.255.255
        metadata none
        mirror disabled
        mobile-app-tunnel disabled
        nat64 disabled
        partition Common
        per-flow-request-access-policy none
        persist none
        policies none
        pool none
        profiles {
            http {
                context all
            }
            tcp {
                context all
            }
        }
        rate-class none
        rate-limit disabled
        rate-limit-dst-mask 0
        rate-limit-mode object
        rate-limit-src-mask 0
        related-rules none
        rules none
        security-log-profiles none
        service-down-immediate-action none
        service-policy none
        source 0.0.0.0/0
        source-address-translation {
            pool none
            type automap
        }
        source-port preserve
        syn-cookie-status not-activated
        traffic-classes none
        translate-address enabled
        translate-port enabled
        urldb-feed-policy none
        vlans none
        vlans-disabled
        vs-index 2
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.6':  # failed on 11.5
                values.pop('address-status')
                values.pop('flow-eviction-policy')
                values.pop('per-flow-request-access-policy')
                values.pop('urldb-feed-policy')
            if v < 'bigip 11.6.2':  # failed on 11.6, 11.6.1
                values.pop('service-down-immediate-action')
                values.pop('service-policy')
            return self.get_full_path(), obj


class LsnPool(PropertiesStamp):
    TMSH = r"""
    ltm lsn-pool %(key)s {
        app-service none
        backup-members none
        client-connection-limit 0
        description none
        egress-interfaces none
        egress-interfaces-disabled
        hairpin-mode disabled
        icmp-echo disabled
        inbound-connections disabled
        log-profile none
        log-publisher none
        members none
        mode napt
        partition Common
        pcp {
            dslite none
            profile none
            selfip none
        }
        persistence {
            mode none
            timeout 300
        }
        port-block-allocation {
            block-idle-timeout 3600
            block-lifetime 0
            block-size 64
            client-block-limit 1
            zombie-timeout 0
        }
        route-advertisement disabled
        translation-port-range 1025-65535
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        if v.product.is_bigip:
            def pop(k, d):
                return d.pop(k)
            if v < 'bigip 11.6':  # failed on 11.4.1, 11.5
                self.properties.inbound_connections = pop
                self.properties.port_block_allocation = pop
                self.properties.pcp = pop
                self.properties.log_publisher = pop
                self.properties.log_profile = pop
            return self.get_full_path(), obj


class LsnLogProfile(PropertiesStamp):
    TMSH = r"""
    ltm lsn-log-profile %(key)s {
        app-service none
        defaults-from none
        description none
        end-inbound-session {
            action enabled
        }
        end-outbound-session {
            action enabled
            elements none
        }
        errors {
            action enabled
        }
        partition Common
        quota-exceeded {
            action enabled
        }
        start-inbound-session {
            action disabled
        }
        start-outbound-session {
            action disabled
            elements none
        }
    }
    """


class DataGroup(PropertiesStamp):
    TMSH = r"""
    ltm data-group external %(key)s {
        external-file-name none
        type string
    }
    """


class SnatPool(PropertiesStamp):
    TMSH = r"""
    ltm snatpool %(key)s {
        members {
        }
    }
    """


class VirtualAddress(PropertiesStamp):
    TMSH = r"""
    ltm virtual-address %(key)s {
        address none
        app-service none
        arp enabled
        auto-delete true
        connection-limit 0
        description none
        enabled yes
        floating enabled
        icmp-echo enabled
        inherited-traffic-group false
        mask 255.255.255.255
        metadata none
        partition Common
        route-advertisement disabled
        server-scope any
        traffic-group traffic-group-1
        unit 1
    }
    """


class PersistenceSSL(PropertiesStamp):
    default = None

    TMSH = r"""
    ltm persistence ssl %(key)s {
        app-service none
        defaults-from none
        description none
        match-across-pools disabled
        match-across-services disabled
        match-across-virtuals disabled
        mirror disabled
        override-connection-limit disabled
        partition Common
        timeout 300
    }
    """

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        if self.default:
            return {key: {'default': self.default}}
        else:
            # return super(Profile, self).reference()
            return {key: {}}

