'''
Created on Apr 12, 2013

@author: jono
'''
from .scaffolding import Stamp, FileStamp, Literal, PropertiesStamp
import logging
from ...base import enum
from ...utils.parsers import tmsh
from ...utils.parsers.tmsh import RawEOL
from ...macros.webcert import WebCert

LOG = logging.getLogger(__name__)


class Provision(Stamp):
    TMSH = """
        sys provision %(name)s {
           level none
        }
    """
    BIGPIPE = """
        provision %(name)s {
           level none
        }
    """
    states = enum(MINIMAL='minimum',
                  NOMINAL='nominal',
                  DEDICATED='dedicated')

    def __init__(self, name, level=states.NOMINAL):
        self.name = name
        self.level = level
        super(Provision, self).__init__()

    def tmsh(self, obj):
        value = obj.rename_key('sys provision %(name)s', name=self.name)
        value['level'] = self.level
        return None, obj

    def bigpipe(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip and v >= 'bigip 10.0.0':
            value = obj.rename_key('provision %(name)s', name=self.name)
            value['level'] = self.level
            return None, obj
        return None, None


class Defaults(Literal):
    TMSH = """
        sys httpd {
            auth-pam-idle-timeout 21600
        }
        net self-allow {
            defaults {
                ospf:any
                tcp:161
                tcp:22
                tcp:4353
                tcp:443
                tcp:53
                udp:1026
                udp:161
                udp:4353
                udp:520
                udp:53
            }
        }
    """
    BIGPIPE = """
        stp {
        # config name none
        }
        self allow {
        #   default tcp domain udp 1026 tcp ssh tcp snmp proto ospf tcp 4353 udp domain tcp https udp efs udp 4353 udp snmp
        }
    """

    def bigpipe(self, obj):
        value = obj.rename_key('stp')
        value['config name'] = 'none'

        value = obj.rename_key('self allow')
        value['default tcp domain udp 1026 tcp ssh tcp snmp proto ospf tcp 4353 udp domain tcp https udp efs udp 4353 udp snmp'] = None
        return None, obj


class Platform(Stamp):
    TMSH = """
        sys management-ip %(ip)s/%(netmask)s { }
        sys management-route default {
           gateway none
        }
        sys db dhclient.mgmt {
            value "disable"
        }
        sys global-settings {
           mgmt-dhcp disabled
           gui-setup disabled
           hostname bigip1
        }
    """
    BIGPIPE = """
        mgmt %(ip)s {
           netmask %(netmask)s
        }
        mgmt route default inet {
           gateway none
        }
        system {
           hostname bigip1
        }
    """

    def __init__(self, address, gateway, hostname=None, dhcp=False, wizard=False):
        self.address = address
        self.gateway = gateway
        self.hostname = hostname or "dut1"
        self.dhcp = dhcp
        self.wizard = wizard
        super(Platform, self).__init__()

    def tmsh(self, obj):
        obj.rename_key('sys management-ip %(ip)s/%(netmask)s',
                       ip=self.address.ip, netmask=self.address.netmask)
        value = obj['sys management-route default']
        value['gateway'] = str(self.gateway)
        if self.dhcp:
            obj['sys db dhclient.mgmt']['value'] = 'enable'

        value = obj['sys global-settings']
        value['gui-setup'] = 'enabled' if self.wizard else 'disabled'
        value['mgmt-dhcp'] = 'enabled' if self.dhcp else 'disabled'
        value['hostname'] = self.hostname
        return None, obj

    def bigpipe(self, obj):
        value = obj.rename_key('mgmt %(ip)s', ip=self.address.ip)
        value['netmask'] = str(self.address.netmask)
        value = obj['mgmt route default inet']
        value['gateway'] = str(self.gateway)
        value = obj['system']
        value['gui setup'] = 'enable' if self.wizard else 'disable'
        value['hostname'] = self.hostname
        return None, obj


class DNS(Stamp):
    TMSH = """
        sys dns {
            name-servers { 127.0.0.1 }
            search { sub.domain.com domain.com }
        }
    """
    BIGPIPE = """
        dns {
           nameservers
              127.0.0.1
           search
              sub.domain.com
              domain.com
        }
    """

    def __init__(self, servers, suffixes=None):
        self.servers = servers
        self.suffixes = suffixes or []
        super(DNS, self).__init__()

    def tmsh(self, obj):
        obj['sys dns']['name-servers'] = self.servers
        obj['sys dns']['search'] = self.suffixes
        return None, obj

    def bigpipe(self, obj):
        value = obj['dns']
        value.clear()
        value.update({'nameservers': RawEOL})
        value.update(dict((x, tmsh.RawEOL) for x in self.servers))
        if self.suffixes:
            value.update({'search': RawEOL})
            value.update(dict((x, tmsh.RawEOL) for x in self.suffixes))
        return None, obj


class NTP(Stamp):
    TMSH = """
        sys ntp {
            servers { ntp }
            timezone America/Los_Angeles
        }
    """
    BIGPIPE = """
        ntp {
           servers ntp
           timezone "America/Los_Angeles"
        }
    """

    def __init__(self, servers, timezone=None):
        self.servers = servers or []
        self.timezone = timezone
        super(NTP, self).__init__()

    def tmsh(self, obj):
        value = obj['sys ntp']
        value.clear()
        value['servers'] = self.servers
        if self.timezone:
            value['timezone'] = self.timezone
        return None, obj

    def bigpipe(self, obj):
        value = obj['ntp']
        value.clear()
        if self.servers:
            value['servers'] = tmsh.RawString(' '.join(self.servers))
        if self.timezone:
            value['timezone'] = self.timezone
        return None, obj


class Mail(Stamp):
    TMSH = """
        sys smtp-server %(key)s {
            from-address nobody@test.com
            local-host-name test.net
            smtp-server-host-name mail
            smtp-server-port 25
        }
        """

    def __init__(self, server, port=25, originator='nobody@foo.com'):
        self.server = server
        self.port = port
        self.originator = originator
        super(Mail, self).__init__()

    def tmsh(self, obj):
        v = self.folder.context.version
        if v.product.is_bigip and v >= 'bigip 11.3.0' or \
           v.product.is_em and v >= 'em 3.0.0':
            key = self.folder.SEPARATOR.join((self.folder.key(), self.server))
            value = obj.rename_key('sys smtp-server %(key)s', key=key)
            value['smtp-server-host-name'] = self.server
            value['smtp-server-port'] = self.port
            value['from-address'] = self.originator
            return key, obj
        return None, None


class SSLCert(FileStamp):
    TMSH = """
        sys file ssl-cert %(key)s {
            cache-path %(location)s
            revision 1
            #source-path /config/ssl/ssl.crt/test.crt
        }
        """

    def __init__(self, name='test.crt', obj=None):
        self.name = name
        assert obj, "obj parameter must be a crypto.X509 instance"
        self.obj = obj
        self.location = None
        super(SSLCert, self).__init__()

    @property
    def remote_path(self):
        partition = self.folder.partition().name
        return '/config/filestore/files_d/{partition}_d/certificate_key_d/{name}'\
            .format(partition=partition, name=self.name)

    @property
    def payload(self):
        return WebCert.as_pem(self.obj)

    def tmsh(self, obj):
        key = self.get_full_path()
        partition = self.folder.partition().name
        value = obj.format(key=key, location=self.remote_path)
        return key, value


class SSLKey(FileStamp):
    TMSH = """
        sys file ssl-key %(key)s {
            cache-path %(location)s
            revision 1
        }
        """

    def __init__(self, name='test.key', obj=None):
        self.name = name
        assert obj, "obj parameter must be a crypto.PKey instance"
        self.obj = obj
        self.location = None
        super(SSLKey, self).__init__()

    @property
    def remote_path(self):
        partition = self.folder.partition().name
        return '/config/filestore/files_d/{partition}_d/certificate_key_d/{name}'\
            .format(partition=partition, name=self.name)

    @property
    def payload(self):
        return WebCert.as_pem(self.obj)

    def tmsh(self, obj):
        key = self.get_full_path()
        value = obj.format(key=key, location=self.remote_path)
        return key, value


class DataGroup(PropertiesStamp, FileStamp):
    TMSH = r"""
    sys file data-group %(key)s {
        cache-path %(location)s
        type string
    }
    """

    def __init__(self, name='dg1', properties=None, dg_file=None):
        super(DataGroup, self).__init__(name, properties)
        assert dg_file, "dg_file must contain a path to a local file"
        self.dg_file = dg_file

    @property
    def remote_path(self):
        partition = self.folder.partition().name
        return '/config/filestore/files_d/{partition}_d/data_group_d/{name}'\
            .format(partition=partition, name=self.name)

    @property
    def payload(self):
        with open(self.dg_file) as f:
            return f.read()

    def tmsh(self, obj):
        key = self.get_full_path()
        value = obj.format(key=key, location=self.remote_path)
        return key, value


class FeatureModule(PropertiesStamp):
    TMSH = r"""
    sys feature-module %(key)s {
        enabled
    }
    """

    def tmsh(self, obj):
        return self.name, obj


class Cluster(PropertiesStamp):
    TMSH = r"""
    sys cluster %(key)s {
        address 10.1.2.3/24
        members {
            1 {
                address 10.1.2.3
                enabled
                priming disabled
            }
        }
        min-up-members 1
        min-up-members-enabled no
    }
    """


class Snmp(PropertiesStamp):
    TMSH = r"""
    sys snmp {
        agent-addresses { tcp6:161 udp6:161 }
        agent-trap enabled
        allowed-addresses { 127. }
        auth-trap disabled
        bigip-traps enabled
        communities none
        description none
        disk-monitors none
        include none
        l2forward-vlan none
        load-max1 12
        load-max5 12
        load-max15 12
        process-monitors none
#        snmpv1 enable
#        snmpv2c enable
        sys-contact "Customer Name <admin@customer.com>"
        sys-location "Network Closet 1"
        sys-services 78
        trap-community public
        trap-source none
        traps none
        users none
        v1-traps none
        v2-traps none
    }
    """
