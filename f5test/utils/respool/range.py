'''
Created on Jan 31, 2018

@author: jono
'''
import itertools
from netaddr import IPNetwork, IPAddress
from ...base import OptionsStrict

MINPORT = 20000
MAXPORT = 65534


class Range(object):
    def __init__(self, start, stop=None):
        if stop:
            assert stop >= start
        else:
            stop = start
        self.start = start
        self.stop = stop
        self._iter = iter(xrange(start, stop + 1))

    def __iter__(self):
        return self

    def __getitem__(self, i):
        return list(self)[i]

    def __next__(self):
        return next(self._iter)
    next = __next__


class PortRange(Range):

    def __init__(self, start, stop=None):
        assert start >= 0
        if stop:
            assert stop <= MAXPORT
        else:
            stop = MAXPORT
        super(PortRange, self).__init__(start, stop)


class IPRange(Range):

    def __init__(self, start, stop=None):
        if isinstance(start, str) and '/' in start:
            start = IPNetwork(start)

        if isinstance(start, IPNetwork):
            stop = IPAddress(start.last - 1)
            start = start.ip
        else:
            start = IPAddress(start)
            if stop:
                stop = IPAddress(stop)
                assert stop >= start
            else:
                stop = IPAddress(start)
        self.current = start
        self.stop = stop

    def __iter__(self):
        return self

    def __next__(self):
        ip = IPAddress(self.current)
        if self.current > self.stop:
            raise StopIteration
        self.current += 1
        return ip
    next = __next__


class IPPortRange(Range):
    def __init__(self, ip_range, port_range=None):
        if port_range is None:
            port_range = (MINPORT, MAXPORT)
        if not isinstance(ip_range, (tuple, list)):
            ip_range = (ip_range,)
        if not isinstance(port_range, (tuple, list)):
            port_range = (port_range,)
        #self.current = itertools.product(IPRange(*ip_range), PortRange(*port_range))
        self.current = (OptionsStrict(ip=x[0], port=x[1])
                        for x in itertools.product(IPRange(*ip_range),
                                                   PortRange(*port_range)))

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.current)
    next = __next__


if __name__ == '__main__':
    print('IP range:')
    rp = IPRange('1.1.1.1', '1.1.1.3')
    print(list(rp))
    print('-' * 80)

    print('IP subnet range:')
    rp = IPRange('1.1.1.1/24')
    print(len(list(rp)))
    print('-' * 80)

    print('IP/port custom range:')
    rp = IPPortRange(('1.1.1.200', '1.1.1.201'), 80)
    print(next(rp))
    print(next(rp))
    print('-' * 80)

    print("Cool!")
