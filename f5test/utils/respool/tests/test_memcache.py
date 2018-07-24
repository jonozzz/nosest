import unittest

from f5test.utils.respool.base import IPAddressResourceItem, MemberResourceItem
from f5test.utils.respool.net import IpPortResourcePool, MemberResourcePool, IpResourcePool, LazyMemberResourcePool
from f5test.utils.respool.memcache import MemcachePool
from netaddr import IPAddress

POOL1 = 'testenv.vlan1.vips'
POOL2 = 'testenv.vlan1.members'


class TestCases(unittest.TestCase):

    def test01_named_get(self):
        print('Memcached IP/port pool on machine1:\n')
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine1')
        pool = MemcachePool(['localhost'], p, timeout=10)
        i = pool.get('bip1')
        print(("Item by name:\n  %s\n" % pool.bip1))
        self.assertEqual(i.value, (IPAddress('1.1.1.10'), 20000))

    def test02_named_get_multi(self):
        print('Memcached IP/port pool on machine1:\n')
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine1')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.get_multi(2, name="vip_%d")
        print(("Multiple items by name:\n  %s %s\n" % (pool.vip_1.value, pool.vip_2)))
        self.assertEqual(pool.vip_1.value, (IPAddress('1.1.1.10'), 20001))
        self.assertEqual(pool.vip_2.value, (IPAddress('1.1.1.10'), 20002))

    def test03_anon_get(self):
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine1')
        pool = MemcachePool(['localhost'], p, timeout=10)
        i = pool.get()
        pool.free(i)
        print(("Anonymous item:\n  %s\n\n" % i))
        self.assertEqual(i.value, (IPAddress('1.1.1.10'), 20003))

    def test04_prefixed_named_get(self):
        print('Memcached IP/port pool on machine2:')
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine2')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.sync()
        i = pool.get('bip1')
        print(("  %s\n" % i))
        self.assertEqual(i.value, (IPAddress('1.1.1.10'), 20003))

    def test05_named_get(self):
        """Test that named get returns the cached value in test01"""
        print('Memcached IP/port pool on machine1, again:')
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine1')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.sync()
        i = pool.get('bip1')
        print(("  %s\n" % i))
        self.assertEqual(i.value, (IPAddress('1.1.1.10'), 20000))

    def test06_anon_scale(self):
        """Test the time it takes to get 2000 items"""
        p = IpPortResourcePool(POOL1, '1.1.1.10', prefix='machine1')
        pool = MemcachePool(['localhost'], p, timeout=10)
        items = pool.get_multi(2000)
        print(("It's fairly scalable too:\n  %s\n" % items[-1]))

    def test07_member_pool(self):
        """Test the time it takes to get 2000 items"""
        print('Memcached member pool on machine2:')
        p = MemberResourcePool(POOL2, '1.1.1.10', dockers=['docker-1', 'docker-2'],
                               prefix='machine2')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.sync()
        i = pool.get_multi(2, 'bip%d')
        print(("Anonymous item:\n  %s\n" % i[0].local_dir, i[1].docker))
        # Test that it visits through both "dockers"
        self.assertEqual(i[0].local_dir, '/tmp/pool-1.1.1.10-20000')
        self.assertEqual(i[1].docker, 'docker-2')
        # Named get matching a get_multi pattern should return the saved item
        i = pool.get('bip2')
        print(("Named item:\n  %s\n" % i, i.docker))
        self.assertEqual(i.value, (IPAddress('1.1.1.10'), 20001))

    def test08_different_item_type(self):
        """Test that the same pool can hold different item types"""
        p = IpResourcePool(POOL2, '1.1.1.10', prefix='machine2')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.sync()
        pool.get('bip3')
        self.assertIsInstance(pool.pool.bip1, MemberResourceItem)
        self.assertIsInstance(pool.pool.bip1, MemberResourceItem)
        self.assertEqual(pool.pool.bip3.name, 'bip3')
        self.assertIsInstance(pool.pool.bip3, IPAddressResourceItem)

    def test09_lazy_member(self):
        """Test lazy member pool, where the the IP pool is passed at get() time"""
        p = LazyMemberResourcePool(POOL2, size=10, prefix='machine2')
        pool = MemcachePool(['localhost'], p, timeout=10)
        #pool.sync()
        i = pool.get('member1', ip_pool=[{'ip': '1.1.1.1'}])
        self.assertEqual(i.value, (IPAddress('1.1.1.1'), 20000))
        i = pool.get('member2', ip_pool=[{'ip': '1.1.1.1'}])
        self.assertEqual(i.value, (IPAddress('1.1.1.1'), 20001))
        i = pool.get('member1', ip_pool=[{'ip': '1.1.1.1'}])
        self.assertEqual(i.value, (IPAddress('1.1.1.1'), 20000))

    def test99_free_pool1(self):
        p = IpPortResourcePool(POOL1, '1.1.1.10')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.free_all()

        p = IpPortResourcePool(POOL2, '1.1.1.10')
        pool = MemcachePool(['localhost'], p, timeout=10)
        pool.free_all()


if __name__ == '__main__':
    unittest.main()
