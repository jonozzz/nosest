import pytest
from ..interfaces.testcase import ContextHelper
from ..utils.respool import IpResourcePool, IpPortResourcePool
from ..utils.respool.net import (RangeResourcePool, ResourcePool,
                                  MemberResourcePool, LazyMemberResourcePool)
from ..utils.respool.range import PortRange, IPPortRange, IPRange
from ..utils.convert import to_bool


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


class Plugin(object):
    """
    Setup respools per session.
    """
    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc'):
            self.options = config._tc.plugins.respool
            self.enabled = to_bool(self.options.enabled)
        else:
            self.enabled = False
        self.context = ContextHelper()

    def Xpytest_sessionstart(self, session):
        cfgifc = self.context.get_config()
        factory = cfgifc.get_session().get_respool_handler()

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

            # pool_name = "%s-%s" % (specs.scope, name) if specs.scope else name
            pool_name = specs.scope
            p = factory.get_memcached_pool(name, klass, pool_name,
                                           timeout=specs.get('timeout'),
                                           **specs.args)
            #LOG.debug("New respool: %s", p.pool.name)

        ranges = self.options.get('ranges', [])
        for range_ in ranges:
            name, specs = range_.popitem()
            klass = getattr(RangeResourceTypes, specs.get('type', 'ip'))
            factory.get_range(name, klass, **specs.args)

    def pytest_sessionfinish(self, session, exitstatus):
        self.context.teardown()

    @pytest.fixture(scope='session')
    def respool(self, request):
        cfgifc = self.context.get_config()
        factory = cfgifc.get_session().get_respool_handler()

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

            # pool_name = "%s-%s" % (specs.scope, name) if specs.scope else name
            pool_name = specs.scope
            p = factory.get_memcached_pool(name, klass, pool_name,
                                           timeout=specs.get('timeout'),
                                           **specs.args)

        yield factory.pools


def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'respool-plugin')
