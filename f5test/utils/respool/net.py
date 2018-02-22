from __future__ import print_function

'''
Created on Jan 31, 2018

@author: jono
'''

import itertools
from netaddr import IPAddress
from .base import PoolExhausted, ResourcePool, RangeResourcePool, IPAddressResourceItem, IPAddressPortResourceItem, \
    MemberResourceItem
from .range import PortRange, IPRange

MINPORT = 20000
MAXPORT = 65534


class IpResourcePool(RangeResourcePool):
    """
    IPAddress resource pool.

    @param start: The initial IP address
    @type start: netaddr.IPAddress
    @param size: The size of the pool
    @type size: int
    """
    item_class = IPAddressResourceItem

    def __init__(self, name, start, size=1, prefix=''):
        '''
        Constructor
        '''
        super(IpResourcePool, self).__init__(name, IPAddress(start), size,
                                             prefix=prefix)


class IpPortResourcePool(IpResourcePool):
    item_class = IPAddressPortResourceItem

    def __init__(self, name, ip_range, port_range=None, size=None, prefix=''):
        '''
        Constructor
        '''
        if port_range is None:
            port_range = (MINPORT, MAXPORT)
        if not isinstance(ip_range, tuple):
            ip_range = (ip_range,)
        if not isinstance(port_range, tuple):
            port_range = (port_range,)
        self.size = size
        iterable = itertools.product(IPRange(*ip_range), PortRange(*port_range))
        ResourcePool.__init__(self, name, iterable, prefix)

    def get(self, name=None):
        if self.size and len(self.items) >= self.size:
            raise PoolExhausted(self.name)
        return super(IpPortResourcePool, self).get(name)


class MemberResourcePool(IpResourcePool):
    item_class = MemberResourceItem

    def __init__(self, name, ip_range, port_range=None, size=None,
                 remote_dir='/tmp/pool-{key}', dockers=None, local_dir=None, prefix=''):
        if port_range is None:
            port_range = (MINPORT, MAXPORT)
        if not isinstance(ip_range, tuple):
            ip_range = (ip_range,)
        if not isinstance(port_range, tuple):
            port_range = (port_range,)
        self.remote_dir = remote_dir
        self.local_dir = local_dir if local_dir else self.remote_dir
        dockers = ['localhost'] if dockers is None else dockers
        self.dockers = itertools.cycle(dockers)
        self.size = size
        iterable = itertools.product(IPRange(*ip_range), PortRange(*port_range))
        ResourcePool.__init__(self, name, iterable, prefix)
        self.tokens = dict(name=self.name, prefix=self.prefix)

    def get(self, name=None, prefix=None, tokens=None):
        #if self.size and len(self.items) >= self.size:
        #    raise PoolExhausted(self.name)

        if tokens is not None:
            self.tokens.update(tokens)

        item = super(MemberResourcePool, self).get(name, prefix=prefix)
        item.set_remote_dir(self.remote_dir, **self.tokens)
        item.set_local_dir(self.local_dir, **self.tokens)
        item.docker = next(self.dockers)
        return item

    def get_multi(self, num, name=None, prefix=None, tokens=None):
        #if self.size and len(self.items) >= self.size:
        #    raise PoolExhausted(self.name)

        if tokens is not None:
            self.tokens.update(tokens)

        items = super(MemberResourcePool, self).get_multi(num, name, prefix=prefix)
        for item in items:
            item.set_remote_dir(self.remote_dir, **self.tokens)
            item.set_local_dir(self.local_dir, **self.tokens)
            item.docker = next(self.dockers)
        return items


if __name__ == '__main__':
    print('IP pool examples:\n')
    rp = IpResourcePool('pool1', IPAddress('1.1.1.1'), 10)
    rp.get('ip1')
    print(IPAddressResourceItem.decode({'ip': '1.1.1.1', 'name': 'ip1'}))
    i = rp.get()
    print('Item by name:\n  %s' % rp.ip1)
    print('Anonymous item:\n  %s' % i)
    print('-' * 80)

    print('IP subnet pool examples:')
    rp = IpPortResourcePool('pool2', '1.1.1.254/24', 80)
    i = rp.get()
    print('Anonymous item:\n  %s' % str(i.value))
    print('-' * 80)

    print('Member pool examples:')
    rp = MemberResourcePool('pool2', '1.1.1.254/24', 80, remote_dir='/tmp/docroot-{key}',
                            local_dir='/tmp/sshfs-{key}-{foo}')
    i = rp.get(tokens=dict(foo='bar'))
    print('Anonymous item:\n  %s' % str(i.local_dir))

    print("Cool!")
