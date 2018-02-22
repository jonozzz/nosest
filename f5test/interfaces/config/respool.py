"""
Created on Feb 2, 2018

@author: jono
"""
from ...base import OptionsStrict
from ...utils.respool import MemcachePool

DEFAULT_TIMEOUT = 60


class RespoolFactory(object):

    def __init__(self, memcache_specs, machine_id=''):
        self.memcache_specs = memcache_specs
        self.prefix = machine_id if machine_id else ''
        self.pools = OptionsStrict()
        self.ranges = OptionsStrict()

    def get(self, name, klass, *args, **kwargs):
        pool = self.pools[name] = klass(*args, prefix=self.prefix, **kwargs)
        return pool

    def get_range(self, name, klass, *args, **kwargs):
        range_ = self.ranges[name] = list(klass(*args, **kwargs))
        return range_

    def get_memcached_pool(self, name, klass, *args, **kwargs):
        timeout = kwargs.pop('timeout', DEFAULT_TIMEOUT)
        #prefix = self.prefix + kwargs.pop('prefix', '')
        if timeout is None:
            timeout = self.memcache_specs.timeout
        pool = self.pools[name] = MemcachePool(self.memcache_specs.servers,
                                               klass(*args, prefix=self.prefix, **kwargs),
                                               timeout=timeout,
                                               encode=True)
        return pool
