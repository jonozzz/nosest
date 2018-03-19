'''
Created on Aug 29, 2014

@author: jono
'''
import logging

from . import ExtendedPlugin
from ...utils.respool import IpResourcePool, IpPortResourcePool
from ...utils.respool.net import (RangeResourcePool, ResourcePool,
                                  MemberResourcePool, LazyMemberResourcePool)
from ...utils.respool.range import PortRange, IPPortRange, IPRange
from ...interfaces.testcase import ContextHelper

STDOUT = logging.getLogger('stdout')
LOG = logging.getLogger(__name__)


class PoolResourceTypes(object):
    member = MemberResourcePool
    lazy_member = LazyMemberResourcePool
    ip = IpResourcePool
    ip_port = IpPortResourcePool
    range = RangeResourcePool
    generic = ResourcePool


class RangeResourceTypes(object):
    ip = IPRange
    ip_port = IPPortRange
    port = PortRange


class Respools(ExtendedPlugin):
    """
    Log when the session has started (after all plugins are configured).
    """
    enabled = False
    score = 1000

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        super(Respools, self).configure(options, noseconfig)

        self.context = ContextHelper()
        self.cfgifc = self.context.get_config()

    def begin(self):
        STDOUT.info('Initializing resource pools...')

        factory = self.cfgifc.get_session().get_respool_handler()

        pools = self.options.get('pools', [])
        for pool in pools:
            name, specs = pool.popitem()
            klass = getattr(PoolResourceTypes, specs.get('type', 'ip'))
            # devices = specs.get('devices', [])
            # for prefix in devices:
            #     device = self.cfgifc.get_device(prefix)
            #     p = factory.get_memcached_pool(name, klass, pool_name,
            #                                    timeout=specs.get('timeout'),
            #                                    prefix=device.alias + prefix,
            #                                    **specs.args)
            #     device.respools[pool_name] = p

            #pool_name = "%s-%s" % (specs.scope, name) if specs.scope else name
            pool_name = specs.scope
            p = factory.get_memcached_pool(name, klass, pool_name,
                                           timeout=specs.get('timeout'),
                                           **specs.args)
            LOG.debug("New respool: %s", p.pool.name)

        ranges = self.options.get('ranges', [])
        for range_ in ranges:
            name, specs = range_.popitem()
            klass = getattr(RangeResourceTypes, specs.get('type', 'ip'))
            factory.get_range(name, klass, **specs.args)
