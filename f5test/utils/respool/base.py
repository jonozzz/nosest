'''
Created on Jan 30, 2018

@author: jono
'''
from netaddr import IPAddress
from ...base import OptionsStrict


class PoolExhausted(Exception):
    pass


class ResourceItem(object):

    def __init__(self, value):
        self.value = value

    @property
    def key(self):
        return str(self.value)

    @classmethod
    def decode(cls, other):
        return cls(other['value'])

    def encode(self):
        return dict(value=self.value)

    def __eq__(self, other):
        if isinstance(other, ResourceItem):
            return self.value == other.value
        else:
            return self.value == other

    def __hash__(self):
        return self.value


class NamedResourceItem(ResourceItem):

    def __init__(self, value, name=None, prefix=''):
        super(NamedResourceItem, self).__init__(value)
        self.name = name if name else self.key
        self.prefix = prefix

    def __str__(self):
        return "<%s:%s>" % (self.name, self.value)

    def __repr__(self):
        return "{} prefix={} <{}>".format(self.__class__.__name__, self.prefix, self.value)

    def __hash__(self):
        return hash(self.name)

    def encode(self):
        return dict(name=self.name, prefix=self.prefix)


class NumericResourceItem(NamedResourceItem):

    @property
    def key(self):
        return str(self.value)

    @classmethod
    def decode(cls, other):
        i = cls(other['value'], other.get('name'))
        i.prefix = other.get('prefix', '')
        return i

    def encode(self):
        return dict(name=self.name, value=self.value, prefix=self.prefix)


class IPAddressResourceItem(NamedResourceItem):

    def __init__(self, address, name=None):
        if not isinstance(address, IPAddress):
            address = IPAddress(address)
        self.ip = str(address)
        super(IPAddressResourceItem, self).__init__(address, name)

    @property
    def key(self):
        return self.ip

    @classmethod
    def decode(cls, other):
        i = cls(other['ip'], other.get('name'))
        i.prefix = other.get('prefix', '')
        return i

    def encode(self):
        return dict(name=self.name, ip=self.ip, prefix=self.prefix)


class IPAddressPortResourceItem(NamedResourceItem):

    def __init__(self, (address, port), name=None):
        if not isinstance(address, IPAddress):
            address = IPAddress(address)
        self.ip = str(address)
        self.port = int(port)
        super(IPAddressPortResourceItem, self).__init__((address, port), name)

    @property
    def key(self):
        return '{}:{}'.format(self.ip, self.port)

    @classmethod
    def decode(cls, other):
        i = cls((other['ip'], int(other['port'])), other.get('name'))
        i.prefix = other.get('prefix', '')
        return i

    def encode(self):
        return dict(name=self.name, ip=self.ip, port=self.port,
                    prefix=self.prefix, key=self.key)


class MemberResourceItem(IPAddressPortResourceItem):

    def __init__(self, (address, port), name=None):
        self.local_dir = None
        self.remote_dir = None
        self.docker = None
        super(MemberResourceItem, self).__init__((address, port), name)

    def set_local_dir(self, template, **kwargs):
        self.local_dir = template.format(key=self.key.replace(':', '-'), **kwargs)

    def set_remote_dir(self, template, **kwargs):
        self.remote_dir = template.format(key=self.key.replace(':', '-'), **kwargs)

    @classmethod
    def decode(cls, other):
        item = cls((other['ip'], other['port']), other.get('name'))
        item.prefix = other.get('prefix', '')
        item.remote_dir = other.get('remote_dir')
        item.local_dir = other.get('local_dir')
        item.docker = other.get('docker')
        return item

    def encode(self):
        return dict(name=self.name, ip=self.ip, port=self.port,
                    remote_dir=self.remote_dir, local_dir=self.local_dir,
                    docker=self.docker, prefix=self.prefix, key=self.key)


class ResourcePool(object):
    """
    A very generic resource pool. Pass a name and an iterable of reservable items.
    Call get() to reserve one item.
    Call free(item) to put it back in the pool.

    @param name: Name of the pool
    @type name: str
    @param iterable: Any finite iterable (set, tuple, list)
    @type iterable: iterable
    """
    item_class = NamedResourceItem

    def __init__(self, name, iterable, prefix=''):
        '''
        Constructor
        '''
        if isinstance(name, tuple):
            name = '.'.join(str(x) for x in name)
        self.name = name
        self.iterable = [] if iterable is None else list(iterable)
        self.items = OptionsStrict()
        self.values = set()
        self.prefix = prefix

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, i):
        return self.__dict__['items'][self.prefix + i]

    def __getattr__(self, i):
        try:
            return self[i]
        except KeyError as e:
            raise AttributeError(e)

    def __str__(self):
        return "{}<{}>{}".format(self.__class__.__name__, self.name, self.items)

    @property
    def local_items(self):
        return {k: v for k, v in self.items.items() if k.startswith(self.prefix)
                                                    and isinstance(v, self.item_class)}

    def update_with(self, values):
        tmp = dict((x.prefix + x.name, x) for x in values)
        map(self.items.pop, set(self.items) - set(tmp))
        self.items.update(tmp)
        self.values = set(x.key for x in self.items.values())

    def get(self, name=None, prefix=None, iterable=None):
        s = self.values
        prefix = self.prefix + prefix if prefix else self.prefix
        pool = iterable if iterable else iter(self.iterable)

        if name:
            key = prefix + name
            if key in self.items:
                return self.items[prefix + name]

        for value in pool:
            item = self.item_class(value, name)
            item.prefix = prefix
            key = item.key
            if key not in s:
                self.items[prefix + item.name] = item
                self.values.add(key)
                return item
        else:
            raise PoolExhausted(self.name)

    def get_multi(self, num, name=None, prefix=None, iterable=None):
        i = 0
        items = []
        s = self.values
        pool = iterable if iterable else iter(self.iterable)
        prefix = self.prefix + prefix if prefix else self.prefix

        while i < num:
            found = False
            if name:
                namei = name % (i + 1)
                key = prefix + namei
                if key in self.items:
                    items.append(self.items[key])
                    found = True
                    i += 1

            if not found:
                try:
                    value = next(pool)
                except StopIteration:
                    raise PoolExhausted(self.name)
                item = self.item_class(value, name % (i + 1) if name else name)
                item.prefix = prefix

                key = item.key
                if key not in s:
                    self.items[prefix + item.name] = item
                    self.values.add(key)
                    items.append(item)
                    i += 1
        return items

    def free(self, item):
        if isinstance(item, dict):
            item = self.item_class.decode(item)
        try:
            key = item.key
            self.items.pop(self.prefix + item.name)
            self.values.remove(key)
            return item
        except KeyError:
            return None

    def free_all(self):
        items = []
        for name in self.items.keys():
            if name.startswith(self.prefix):
                item = self.items.pop(name)
                items.append(item)
                self.values.remove(item.key)
        return items


class RangeResourcePool(ResourcePool):
    """
    A range of numbers variant of a resource pool.

    @param start: The initial number
    @type start: int
    @param size: The size of the pool
    @type size: int
    """
    item_class = NumericResourceItem

    def __init__(self, name, start, size, prefix='', template=None):
        self.start = start
        self.size = size
        self.template = template
        r = range(start, start + self.size)
        if template:
            r = (template.format(x) for x in range(start, start + self.size))
        super(RangeResourcePool, self).__init__(name, r, prefix=prefix)


if __name__ == '__main__':
    print('Resource pool examples:')
    rp = ResourcePool('pool1', [1, 99, 3, 2])
    rp.get('item1')
    i = rp.get()
    rp.get_multi(2, 'num_%d')
    print(rp.item1)
    print(i)
    print(rp.num_1, rp.num_2)
    print('-' * 80)

    print('RangeResource pool examples:')
    rp = RangeResourcePool('pool1', 1, 10, template="item_{}")
    rp.get('item1')
    i = rp.get()
    rp.get_multi(2, 'num_%d')
    print(rp.item1)
    print(i)
    print(rp.num_1, rp.num_2)
    print('-' * 80)

    print("Cool!")
