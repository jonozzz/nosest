'''
Created on Jan 31, 2018

@author: jono
'''

import warnings
import pylibmc


class MemcachePool(object):
    '''
    This creaes a memcache representation of the given pool.

    Let's say our local pool is:
    pool_1: (1, 2, 3)

    This will be represented in memcache as the following key/values:
    pool_1: [pool_1_1, pool_1_2, pool_1_3]
    pool_1_1: 1
    pool_1_2: 2
    pool_1_3: 3

    For a pool of N items you'll have N+1 key/value pairs in memcached, one for
    each individual item and one that holds each item's key name.

    @param servers: a list of memcached IP addresses
    @param pool: The pool that will be memcached
    @param timeout: The default timeout for all gets (default: infinite)
    '''
    item_key = '{}_{}'

    def __init__(self, servers, pool, timeout=0, encode=False):
        self.mc = pylibmc.Client(servers, binary=True,
                                 behaviors={"tcp_nodelay": True,
                                            "cas": True,
                                            "ketama": True})
        self.pool = pool
        self.timeout = timeout
        self.encode = encode
        self.sync()

    # Just proxy all other attributes to the inner pool.
    def __getitem__(self, i):
        return self.pool[i]

    def __getattr__(self, i):
        try:
            if i.startswith('__'):
                return super(MemcachePool, self).__getattr__(i)
            return self[i]
        except KeyError as e:
            raise AttributeError(e)

    def get(self, name=None, timeout=None, encode=None, **kwargs):
        pool = self.pool
        timeout = timeout if timeout is not None else self.timeout
        while True:
            key_names, cas = self.mc.gets(pool.name)
            pool_ids = self.mc.get_multi(key_names)
            pool.update_with(pool_ids.values())
            item = pool.get(name, **kwargs)
            key_name = self.item_key.format(pool.name, item.key)
            pool_ids = set(pool_ids)
            pool_ids.add(key_name)
            if self.mc.cas(pool.name, pool_ids, cas):
                self.mc.add(key_name, item, timeout)
                break
            else:
                warnings.warn('Collision. Retrying...')
        if encode is None:
            encode = self.encode
        return item if not encode else item.encode()

    def get_multi(self, num, name=None, timeout=None, encode=None, **kwargs):
        pool = self.pool
        timeout = timeout if timeout is not None else self.timeout
        while True:
            key_names, cas = self.mc.gets(pool.name)
            pool_ids = self.mc.get_multi(key_names)
            pool.update_with(pool_ids.values())
            items = []
            for item in pool.get_multi(num, name, **kwargs):
                items.append(item)
                key_name = self.item_key.format(pool.name, item.key)
                pool_ids = set(pool_ids)
                pool_ids.add(key_name)
            if self.mc.cas(pool.name, pool_ids, cas):
                self.mc.set_multi({x.key: x for x in items},
                                  time=timeout, key_prefix='%s_' % pool.name)
                break
            else:
                warnings.warn('Collision. Retrying...')
        if encode is None:
            encode = self.encode
        return items if not encode else [x.encode() for x in items]

    def free(self, item):
        pool = self.pool
        while True:
            key_names, cas = self.mc.gets(pool.name)
            pool_ids = self.mc.get_multi(key_names)
            pool.update_with(pool_ids.values())
            item = pool.free(item)
            pool_ids = set(pool_ids)
            if item is not None:
                key_name = self.item_key.format(pool.name, item.key)
                pool_ids.remove(key_name)
            if self.mc.cas(pool.name, pool_ids, cas):
                self.mc.delete(key_name)
                break
            else:
                warnings.warn('Collision. Retrying...')
        return item

    def free_all(self):
        pool = self.pool
        while True:
            key_names, cas = self.mc.gets(pool.name)
            pool_ids = self.mc.get_multi(key_names)
            pool.update_with(pool_ids.values())
            items = pool.free_all()
            pool_ids = set(pool_ids)
            key_names = set()
            for item in items:
                key_name = self.item_key.format(pool.name, item.key)
                key_names.add(key_name)
                pool_ids.remove(key_name)
            if self.mc.cas(pool.name, pool_ids, cas):
                self.mc.delete_multi(key_names)
                break
            else:
                warnings.warn('Collision. Retrying...')
        return items

    def sync(self):
        pool = self.pool
        while True:
            self.mc.add(pool.name, pool.items)
            key_names, cas = self.mc.gets(pool.name)
            pool_ids = self.mc.get_multi(key_names or [])
            pool_ids = set(pool_ids)
            for item in pool.items.values():
                key_name = self.item_key.format(pool.name, item.key)
                self.mc.add(key_name, item, self.timeout)
                pool_ids.add(key_name)
            if self.mc.cas(pool.name, pool_ids, cas):
                pool_ids = self.mc.get_multi(set(key_names))
                pool.update_with(pool_ids.values())
                break
            else:
                warnings.warn('Collision. Retrying...')

    def flush(self):
        """This will delete the pool & its items!
        Do this only when you're sure that no other clients are using this pool."""
        pool = self.pool
        key_names = self.mc.get(pool.name)
        self.mc.delete_multi(key_names)
        self.mc.delete(pool.name)


if __name__ == '__main__':
    from f5test.utils.respool.net import IpPortResourcePool, MemberResourcePool

    print('Memcached IP/port pool on machine1:\n')
    p = IpPortResourcePool('labenv1.vlan1.vips', '1.1.1.10')
    p.prefix = 'machine1'
    pool = MemcachePool(['localhost'], p, timeout=10)
    i = pool.get('bip1')
    print("Item by name:\n  %s\n" % pool.bip1)
    pool.free(i)

    pool.get_multi(2, name="vip_%d")
    print("Multiple items by name:\n  %s %s\n" % (pool.vip_1.value, pool.vip_2))

    i = pool.get()
    pool.free(i)
    print("Anonymous item:\n  %s\n\n" % i)

    print('Memcached IP/port pool on machine2:')
    p = IpPortResourcePool('labenv1.vlan1.vips', '1.1.1.10')
    p.prefix = 'machine2'
    pool = MemcachePool(['localhost'], p, timeout=10)
    pool.sync()
    i = pool.get('bip1')
    pool.free_all()
    print("Anonymous item:\n  %s\n" % i)

    items = pool.get_multi(2000)
    print("It's fairly scalable too:\n  %s\n" % items[-1])

    print('Memcached member pool on machine2:')
    p = MemberResourcePool('docker-1-members', '1.1.1.10', dockers=['docker-1', 'docker-2'])
    #p.prefix = 'docker-1'
    pool = MemcachePool(['localhost'], p, timeout=10)
    pool.sync()
    i = pool.get_multi(2, 'bip%d')
    print("Anonymous item:\n  %s\n" % i[0].local_dir, i[1].docker)
    i = pool.get('bip2')
    print("Anonymous item:\n  %s\n" % i.local_dir, i.docker)
    pool.free_all()

    print('Cool!')
