from netaddr import IPNetwork, IPAddress
import socket
import re
from unittest.case import SkipTest
from netaddr.compat import _is_int

BASE_IPV6 = 'FD32:00F5:0000::/64'

def resolv(hostname):
    """Resolves a hostname into an IP address."""
    try:
        _, _, ip_list = socket.gethostbyaddr(hostname)
    except socket.herror:  # [Errno 1] Unknown host
        return hostname
    return ip_list[0]


def get_local_ip(peer):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((peer.split(':', 1)[0], 0))
    ip = s.getsockname()[0]
    s.close()
    return ip


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    #s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port


def ip4to6(ipv4, prefix=None, base=BASE_IPV6):
    """
    Convert an IPv4 to IPv6 by splitting the network part of the ip and shifting
    it to the Global ID and Subnet ID zone.

    @param address: IPv4 address (e.g. '10.10.10.10/24' or '10.10.0.1/16'
    @type address: str
    @param base: IPv6 reserved base. Default: 'FD32:00F5:0000::'
    @type base: str
    """
    ipv4 = IPNetwork(ipv4)
    if prefix:
        ipv4.prefixlen = prefix
    ipv6 = IPNetwork(BASE_IPV6)
    ipv6.value += (ipv4.value >> (32 - ipv4.prefixlen)) << 64
    ipv6.value += ipv4.value - ipv4.network.value
    return ipv6.ip if prefix else ipv6


def dmz_check(cfgifc):
    address = IPAddress(cfgifc.get_device().address)
    good = False
    if cfgifc.api.platform.dmz:
        for x in cfgifc.api.platform.dmz:
            if address in IPNetwork(x):
                good = True
                break
    else:
        good = True  # No dmz networks defined, we assume everyone can connect to us
    if not good:
        raise SkipTest('No connectivity between BIGIQ and this machine.')


class IPAddressRd(IPAddress):

    def __init__(self, addr, version=None, flags=0, rd=0):
        if not _is_int(addr):
            m = re.match('(?P<addr>[a-f\d\.:]+)%?(?P<rd>\d+)?', str(addr))
            if not m:
                raise ValueError(addr)
            self.rd = int(m.group('rd') or rd)
            addr = m.group('addr')
        else:
            self.rd = rd
        super(IPAddressRd, self).__init__(addr, version, flags)

    def __str__(self):
        """:return: IP address in presentational format"""
        if self.rd:
            return "%s%%%d" % (self._module.int_to_str(self._value), self.rd)
        return self._module.int_to_str(self._value)


class IPAddressRdPort(IPAddress):

    def __init__(self, addr, version=None, flags=0, rd=0, port=0):
        if not _is_int(addr):
            m = re.match('(?P<addr>[a-f\d\.:]+)%?(?P<rd>\d+)?[\.:]?(?P<port>\d+)?', str(addr))
            if not m:
                raise ValueError(addr)
            self.rd = int(m.group('rd') or rd)
            self.port = int(m.group('port') or port)
            addr = m.group('addr')
        else:
            self.rd = rd
        super(IPAddressRdPort, self).__init__(addr, version, flags)

    def __str__(self):
        if self.rd:
            addr = "%s%%%d" % (self._module.int_to_str(self._value), self.rd)
        else:
            addr = self._module.int_to_str(self._value)
        if self.port:
            if self.version == 4:
                return "%s:%d" % (addr, self.port)
            else:
                return "%s.%d" % (addr, self.port)


class IPNetworkRd(IPNetwork):

    def __init__(self, addr, implicit_prefix=False, version=None, flags=0, rd=0):
        if not _is_int(addr):
            m = re.match('(?P<addr>[a-f\d\.:]+)%?(?P<rd>\d+)?/?(?P<prefix>\d+)?', str(addr))
            if not m:
                raise ValueError(addr)
            self.rd = int(m.group('rd') or rd)
            if m.group('prefix'):
                addr = '{addr}/{prefix}'.format(**m.groupdict())
            else:
                addr = m.group('addr')
        else:
            self.rd = rd
        super(IPNetworkRd, self).__init__(addr, implicit_prefix, version, flags)

    def __str__(self):
        """:return: this IPNetwork in CIDR format"""
        addr = self._module.int_to_str(self._value)
        if self.rd:
            return "%s%%%d/%s" % (addr, self.rd, self.prefixlen)
        return "%s/%s" % (addr, self.prefixlen)

    @property
    def ip(self):
        """
        The IP address of this `IPNetwork` object. This is may or may not be
        the same as the network IP address which varies according to the value
        of the CIDR subnet prefix.
        """
        return IPAddressRd(self._value, self._module.version, rd=self.rd)


IPV4_ANY = IPNetworkRd('0.0.0.0/0')
IPV6_ANY = IPNetworkRd('::/0')
