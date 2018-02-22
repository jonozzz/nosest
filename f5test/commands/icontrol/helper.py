from .base import IcontrolCommand
from f5test.utils.wait import wait
from time import sleep
import logging
LOG = logging.getLogger(__name__)
VIP_STATES = {'green': 'AVAILABILITY_STATUS_GREEN',
              'red': 'AVAILABILITY_STATUS_RED',
              'blue': 'AVAILABILITY_STATUS_BLUE'}

# this file contains wrappers for BIG-IP icontrol functions called during
# the APIC tests


def _fix_partition(name):
    if name.startswith('/'):
        return name
    else:
        return '/' + name


set_active_folder = None
class SetActiveFolder(IcontrolCommand):
    '''
    Set the current active folder on the BIG-IP
    '''
    def __init__(self, folder='/Common', *args, **kwargs):
        super(SetActiveFolder, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(folder)

    def setup(self):
        self.api.System.Session.set_active_folder(folder=self.partition)


check_sync = None
class CheckSync(IcontrolCommand):
    '''
    Check that the BIG-IPs in the cluster are in sync
    '''
    def __init__(self, state='In Sync', dg='F5', *args, **kwargs):
        super(CheckSync, self).__init__(*args, **kwargs)
        self.state = state
        self.dg = dg

    def setup(self):
        ic = self.api
        ic.System.Session.set_active_folder(folder='/Common')
        timeout = 480
        sync_ready = False
        for _ in range(timeout):
            try:
                sync_stat = ic.Management.DeviceGroup.\
                    get_sync_status(device_groups=[self.dg])[0]['status']
                LOG.info("BIGIP's Sync Status => {}".format(sync_stat))
                timeout1 = 10
                if sync_stat == self.state:
                    for _ in range(timeout1):
                        sync_stat = ic.Management.DeviceGroup.\
                            get_sync_status(device_groups=[self.dg])[0]['status']
                        if sync_stat == self.state:
                            sync_ready = True
                            sleep(1)
                        else:
                            break
                elif sync_stat == 'Standalone':
                    raise Exception('Device is in standalone mode')
                if sync_ready:
                    LOG.info('BIGIPs are in sync for continuous {} seconds'.format(timeout1))
                    return
            except:
                LOG.info('Exception thrown in get_sync_status. Retrying')
            sleep(1)
        raise Exception('DeviceGroup failed to sync, timeout {}s has reached'.format(timeout))


check_partition_vip = None
class CheckPartitionVip(IcontrolCommand):
    '''
    Check if partition on bigip corresponding to
    tenant on APIC is deleted.
    '''
    def __init__(self, partition, exist=False, vip_cnt=0, *args, **kwargs):
        super(CheckPartitionVip, self).__init__(*args, **kwargs)
        self.partition = partition
        self.exist = exist
        self.vip_cnt = vip_cnt

    def setup(self):
        ic = self.api
        LOG.info('Checking partition "{}" ....'.format(self.partition))
        plist = ic.Management.Partition.get_partition_list()
        try:
            for pt in plist:
                ptname = pt['partition_name']
                if not self.exist:
                    if self.partition == ptname:
                        raise Exception('Partition {} exists, which should'
                                       ' not be the case'.format(ptname))
                else:
                    if self.partition == ptname:
                        folder = '/' + ptname
                        ic.System.Session.set_active_folder(folder=folder)
                        vips = ic.LocalLB.VirtualServer.get_list()
                        if len(vips) == self.vip_cnt:
                            LOG.info('Expected: Partition {} has {} VIP(s)'
                                     .format(ptname, self.vip_cnt))
                            return
                        raise Exception('Partition "{}" should have {} VIP(s) - "{}"'
                                       .format((ptname, self.vip_cnt, vips)))
            if not self.exist:
                LOG.info('Expected: Partition "{}" does not exist '.format(self.partition))
            else:
                raise Exception('Partition "{}" not found !!'.format(self.partition))
        finally:
            ic.System.Session.set_active_folder(folder='/Common')


device_group_exists = None
class DeviceGroupExists(IcontrolCommand):
    '''
    check if specified device group exists
    '''
    def __init__(self, name, *args, **kwargs):
        super(DeviceGroupExists, self).__init__(*args, **kwargs)
        self.name = name

    def setup(self):
        ic = self.api
        devicegroups = ic.Management.DeviceGroup.get_list()
        return devicegroups and self.name in devicegroups

find_matching_partition = None
class FindMatchingPartition(IcontrolCommand):
    '''
    search bigip partitions to find one that contains the apic id
    '''
    def __init__(self, apic_id, *args, **kwargs):
        super(FindMatchingPartition, self).__init__(*args, **kwargs)
        self.apic_id = apic_id

    def setup(self):
        ic = self.api
        partition_list = ic.Management.Partition.get_partition_list()
        for pt in partition_list:
            partition = pt['partition_name']
            if partition.find(self.apic_id) > 0:
                return partition
        raise Exception('Could not find partition with id {} on BIG-IP'.format(self.apic_id))

get_partitions = None
class GetPartitions(IcontrolCommand):
    '''
    get the full partition list
    '''
    def setup(self):
        ic = self.api
        return ic.Management.Partition.get_partition_list()

get_vip_names = None
class GetVipNames(IcontrolCommand):
    '''
    get the list of vip names associated with a partition
    '''
    def __init__(self, partition, *args, **kwargs):
        super(GetVipNames, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            vip_names = ic.LocalLB.VirtualServer.get_list()
            # The VIP's name is a full path: return just the name
            vip_names = map(lambda vip_name: vip_name.split('/')[-1], vip_names)
            return vip_names
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_vip_address_port = None
class GetVipAddressPort(IcontrolCommand):

    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipAddressPort, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            addr_port = self.api.LocalLB.VirtualServer.get_destination_v2(
                                            virtual_servers=[self.vip_name])[0]
            # The address looks like /partition/x.x.x.x, so get just the address
            address = addr_port['address'].split('/')[-1]
            # The address has a route domain, probably, so remove it
            address = address.split('%')[0]
            port = addr_port['port']
            return (address, port)
        finally:
            self.api.System.Session.set_active_folder(folder='/Common')


def _get_vip_source_port_behavior(ic, partition, vip_name):
    try:
        ic.System.Session.set_active_folder(folder=partition)
        source_port_behavior = ic.LocalLB.VirtualServer.get_source_port_behavior(virtual_servers=[vip_name])[0]
        return source_port_behavior
    finally:
        ic.System.Session.set_active_folder(folder='/Common')


get_vip_source_port_behavior = None
class GetVipSourcePortBehavior(IcontrolCommand):

    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipSourcePortBehavior, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        return _get_vip_source_port_behavior(self.api, self.partition, self.vip_name)

check_source_port = None
class CheckSourcePort(IcontrolCommand):

    def __init__(self, partition, vip_name, behavior, *args, **kwargs):
        super(CheckSourcePort, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name
        self.behavior = behavior

    def setup(self):
        return wait(lambda: _get_vip_source_port_behavior(self.api, self.partition, self.vip_name),
                    condition=lambda x: x == self.behavior,
                    progress_cb=lambda x: 'Port Behavior: {}'.format(x),
                    timeout=20, interval=1)

def _get_vip_connection_mirror_state(ic, partition, vip_name):
    try:
        ic.System.Session.set_active_folder(folder=partition)
        connection_mirror_state = ic.LocalLB.VirtualServer.get_connection_mirror_state(virtual_servers=[vip_name])[0]
        return connection_mirror_state
    finally:
        ic.System.Session.set_active_folder(folder='/Common')
    
get_vip_connection_mirror_state = None
class GetVipConnectionMirrorState(IcontrolCommand):
    
    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipConnectionMirrorState, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        return _get_vip_connection_mirror_state(self.api, self.partition, self.vip_name)

check_connection_mirror = None
class CheckConnectionMirror(IcontrolCommand):

    def __init__(self, partition, vip_name, state, *args, **kwargs):
        super(CheckConnectionMirror, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name
        self.state = state

    def setup(self):
        return wait(lambda: _get_vip_connection_mirror_state(self.api, self.partition, self.vip_name),
                    condition=lambda x: x == self.state,
                    progress_cb=lambda x: 'Connection Mirroring: {}'.format(x),
                    timeout=20, interval=1)

def _get_vip_persistence_profile(ic, partition, vip_name):
    try:
        ic.System.Session.set_active_folder(folder=partition)
        persistence_profiles = ic.LocalLB.VirtualServer.get_persistence_profile(virtual_servers=[vip_name])
        if persistence_profiles and len(persistence_profiles) > 0 and len(persistence_profiles[0]) > 0:
            return persistence_profiles[0][0]['profile_name']
        return None
    finally:
        ic.System.Session.set_active_folder(folder='/Common')

get_vip_persistence_profile = None
class GetVipPersistenceProfile(IcontrolCommand):

    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipPersistenceProfile, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        return _get_vip_persistence_profile(self.ic, self.partition, self.vip_name)
    
check_vip_persistence_profile = None
class CheckVipPersistenceProfile(IcontrolCommand):
    def __init__(self, partition, vip_name, state, *args, **kwargs):
        super(CheckVipPersistenceProfile, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name
        self.state = state
        
    def setup(self):
        LOG.info('Waiting for profile to equal {}'.format(self.state))
        return wait(lambda: _get_vip_persistence_profile(self.api, self.partition, self.vip_name),
                    condition=lambda x: x == self.state,
                    progress_cb=lambda x: 'Persistence Profile: {}'.format(x),
                    timeout=20, interval=1)


def _get_vip_fb_persistence_profile(ic, partition, vip_name):
    try:
        ic.System.Session.set_active_folder(folder=partition)
        fb_persistence_profile = ic.LocalLB.VirtualServer.get_fallback_persistence_profile(virtual_servers=[vip_name])
        if fb_persistence_profile and len(fb_persistence_profile[0]) > 0:
            return fb_persistence_profile[0]
        return None
    finally:
        ic.System.Session.set_active_folder(folder='/Common')

get_vip_fb_persistence_profile = None
class GetVipFbPersistenceProfile(IcontrolCommand):
    
    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipFbPersistenceProfile, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        return _get_vip_fb_persistence_profile(self.api, self.partition, self.vip_name)
        
check_vip_fb_persistence_profile = None
class CheckVipFbPersistenceProfile(IcontrolCommand):
    def __init__(self, partition, vip_name, state, *args, **kwargs):
        super(CheckVipFbPersistenceProfile, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name
        self.state = state

    def setup(self):
        LOG.info('Waiting for profile to equal {}'.format(self.state))
        return wait(lambda: _get_vip_fb_persistence_profile(self.api, self.partition, self.vip_name),
                    condition=lambda x: x == self.state,
                    progress_cb=lambda x: 'Fallback Persistence Profile: {}'.format(x),
                    timeout=20, interval=1)

get_vip_source_address_translation_type = None
class GetVipSourceAddressTranslationType(IcontrolCommand):
    
    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipSourceAddressTranslationType, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            satt = ic.LocalLB.VirtualServer.get_source_address_translation_type(virtual_servers=[self.vip_name])[0]
            return satt
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_vip_source_address_translation_snat_pool = None
class GetVipSourceAddressTranslationSnatPool(IcontrolCommand):

    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipSourceAddressTranslationSnatPool, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            pools = ic.LocalLB.VirtualServer.get_source_address_translation_snat_pool(virtual_servers=[self.vip_name])
            if pools:
                return pools[0]
            return None
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_vip_source_address = None
class GetVipSourceAddress(IcontrolCommand):
    
    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipSourceAddress, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            addrs = ic.LocalLB.VirtualServer.get_source_address(virtual_servers=[self.vip_name])
            if addrs:
                # The returned address is of the form <ip-address>%<route-domain>/<prefixlen>
                full_addr = addrs[0].split('/')
                ip_addr = full_addr[0].split('%')[0]
                prefixlen = full_addr[1]
                return (ip_addr, prefixlen)
            return (None, None)
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_vip_rules = None
class GetVipRules(IcontrolCommand):

    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetVipRules, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            rules = ic.LocalLB.VirtualServer.get_rule(virtual_servers=[self.vip_name])
            return rules[0]
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_xff_header_mode = None
class GetXffHeaderMode(IcontrolCommand):
    
    def __init__(self, partition, name, *args, **kwargs):
        super(GetXffHeaderMode, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.name = name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            mode = ic.LocalLB.ProfileHttp.get_insert_xforwarded_for_header_mode(profile_names=[self.name])
            return mode[0]['value']
        finally:
            ic.System.Session.set_active_folder(folder='/Common')
        return 'MISSING'

get_pipelining_mode = None
class GetPipeliningMode(IcontrolCommand):
    
    def __init__(self, partition, name, *args, **kwargs):
        super(GetPipeliningMode, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.name = name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            mode = ic.LocalLB.ProfileHttp.get_pipelining_mode(profile_names=[self.name])
            return mode[0]['value']
        finally:
            ic.System.Session.set_active_folder(folder='/Common')
        return 'MISSING'

get_default_pool_name = None
class GetDefaultPoolName(IcontrolCommand):
    
    def __init__(self, partition, vip_name, *args, **kwargs):
        super(GetDefaultPoolName, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.vip_name = vip_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            poolname = ic.LocalLB.VirtualServer.get_default_pool_name(virtual_servers=[self.vip_name])
            return poolname
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_pool_member_names = None
class GetPoolMemberNames(IcontrolCommand):
    
    def __init__(self, partition, pool_name, *args, **kwargs):
        super(GetPoolMemberNames, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.pool_name = pool_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            members = ic.LocalLB.Pool.get_member_v2(pool_names=[self.pool_name])
            return members
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_snat_pools = None
class GetSnatPools(IcontrolCommand):
    
    def __init__(self, partition, *args, **kwargs):
        super(GetSnatPools, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            return ic.LocalLB.SNATPool.get_list()
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_snat_members = None
class GetSnatMembers(IcontrolCommand):
    
    def __init__(self, partition, pool_name, *args, **kwargs):
        super(GetSnatMembers, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.pool_name = pool_name

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            members = ic.LocalLB.SNATPool.get_member_v2(snat_pools=[self.pool_name])
            if members:
                return members[0]
            else:
                return []
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

check_vips_state = None
class CheckVipsState(IcontrolCommand):
    '''
    In default this will check all vips within the partition to be
    green - 'Available'
    if stat='red', it will pass if one of the VIPs is in 'Down' state
    if stat='blue', it will pass if one of the VIPS is in 'Unknown' state
    '''

    def __init__(self, vip_cnt, stat='green', ptt='all', *args, **kwargs):
        super(CheckVipsState, self).__init__(*args, **kwargs)
        self.vip_cnt = vip_cnt
        self.stat = stat
        self.ptt = ptt

    def setup(self):
        ic = self.api
        if self.stat == 'green':
            status = 'AVAILABILITY_STATUS_GREEN'
        elif self.stat == 'red':
            status = 'AVAILABILITY_STATUS_RED'
        elif self.stat == 'blue':
            status = 'AVAILABILITY_STATUS_BLUE'

        if self.ptt == 'all':
            plist = ic.Management.Partition.get_partition_list()
        else:
            plist = [{'partition_name': self.ptt}]

        try:
            for pt in plist:
                if pt['partition_name'] != 'Common':
                    pt_name = _fix_partition(pt['partition_name'])
                    LOG.info('Checking Partition {}'.format(pt_name))
                    self.api.System.Session.set_active_folder(folder=pt_name)
                    vips = self.api.LocalLB.VirtualServer.get_list()
                    if len(vips) != self.vip_cnt:
                        raise Exception('Expect total {} VIPs in partition {} '
                                       'to present, got {} instead\n{}'
                                       .format(self.vip_cnt, pt_name, len(vips), vips))
                    for vip in vips:
                        vip_state = ic.LocalLB.VirtualServer.get_object_status(virtual_servers=[vip])
                        if vip_state[0]['availability_status'] != status:
                            if self.stat == 'green':
                                raise Exception('VIP "{}" in "{}" => not Available'
                                                .format(vip, pt_name))
                        else:
                            LOG.info('Virtual {} is in expected state: {}'
                                     .format(vip, self.stat))
                            if self.stat != 'green':
                                return
            if self.stat != 'green':
                raise Exception('No Virtual are in expected state: {}'.format(self.stat))

        finally:
            ic.System.Session.set_active_folder(folder='/Common')

def _get_vips_states(ic, partition):
    ret = []
    if partition is not None:
        plist = [{'partition_name': partition}]
    else:
        plist = ic.Management.Partition.get_partition_list()

    for pt in plist:
        pt_name = _fix_partition(pt['partition_name'])
        LOG.info('Getting VIP states from {}'.format(pt_name))
        ic.System.Session.set_active_folder(folder=pt_name)
        vips = ic.LocalLB.VirtualServer.get_list()
        LOG.debug('vips from {} = {}'.format(pt_name, vips))
        for vip in vips:
            vip_state = ic.LocalLB.VirtualServer.get_object_status(virtual_servers=[vip])
            ret.append(vip_state[0]['availability_status'])
    ic.System.Session.set_active_folder(folder='/Common')
    LOG.debug('returning {}'.format(ret))
    return ret

get_vips_states = None
class GetVipsStates(IcontrolCommand):
    '''
    Return availability_status of VIPs. By default, return VIPs from all
    partitions except for Common.
    '''
    def __init__(self, partition=None, *args, **kwargs):
        super(GetVipsStates, self).__init__(*args, **kwargs)
        self.partition = partition

    def setup(self):
        return _get_vips_states(self.api, self.partition)


wait_vips_states = None
class WaitVipsStates(IcontrolCommand):
    '''
    Return availability_status of VIPs. By default, return VIPs from all
    partitions.
    '''
    def __init__(self, state='green', *args, **kwargs):
        super(WaitVipsStates, self).__init__(*args, **kwargs)
        self.state = state
        
    def setup(self):
        wait(lambda: _get_vips_states(self.api, None),
             condition=lambda ret: len(ret) == sum(1 for x in ret if x ==
                                                   VIP_STATES[self.state]),
             progress_cb=lambda ret: 'VIPs:{}, In {}:{}. States: {}'.format(
                                      len(ret), self.state,
                                      sum(1 for x in ret
                                        if x == VIP_STATES[self.state]), 
                                      ret))


get_nodes = None
class GetNodes(IcontrolCommand):
    '''
    Return availability_status of VIPs. By default, return VIPs from all
    partitions.
    '''
    
    def setup(self):
        ic = self.api
        ret = list()
        try:
            partitions = ic.Management.Partition.get_partition_list()
            for partition in partitions:
                pt_name = _fix_partition(partition['partition_name'])
                LOG.info('Getting Nodes from {}'.format(pt_name))
                ic.System.Session.set_active_folder(folder=pt_name)
                nodes = ic.LocalLB.NodeAddressV2.get_list()
                LOG.debug('Nodes from {}: {}'.format(pt_name, nodes))
                ret.extend(nodes)
        finally:
            ic.System.Session.set_active_folder(folder='/Common')
        return ret

get_pools = None
class GetPools(IcontrolCommand):
    '''
    Return total all pools in BIG-IP.
    '''
    def setup(self):
        ic = self.api
        ret = list()
        partitions = ic.Management.Partition.get_partition_list()
        for partition in partitions:
            pt_name = _fix_partition(partition['partition_name'])
            LOG.info('Getting Pools from {}'.format(pt_name))
            ic.System.Session.set_active_folder(folder=pt_name)
            pools = ic.LocalLB.Pool.get_list()
            ret.extend(pools)
        ic.System.Session.set_active_folder(folder='/Common')
        return ret

wait_partition_deleted = None
class WaitPartitionDeleted(IcontrolCommand):
    '''
    Wait for a partition to be deleted. We use this after deleting
    all graphs owned by a tenant to ensure that they've been deleted.
    '''
    def __init__(self, partition, timeout=180, *args, **kwargs):
        super(WaitPartitionDeleted, self).__init__(*args, **kwargs)
        self.partition = partition
        self.timeout = timeout

    def setup(self):
        ic = self.api

        def _get_partition_names():
            '''
            get_partitions returns a list of dictionaries--extract
            just the names from the list
            '''
            partitions = ic.Management.Partition.get_partition_list()
            return map(lambda partition: partition.get('partition_name'),
                       partitions)

        wait(_get_partition_names,
             condition=lambda partitions: self.partition not in partitions,
             progress_cb=lambda _: 'Waiting for tenant partition cleanup', 
             timeout=self.timeout)

"""
wait_no_device_failover_groups = None
class WaitNoDeviceFailoverGroups(IcontrolCommand):
    '''
    Waits for the device to be cleaned up. We know it's been
    cleaned up because there are no device failover groups
    left. We'll wait up to 30 seconds. Throws an error if it's not
    cleaned up.
    '''
    def setup(self):
        ic = self.api
        def _get_device_group_types():
            '''
            Return a list of the types (not names) of each device group
            '''
            device_groups = ic.Management.DeviceGroup.get_list()
            device_group_types = ic.Management.DeviceGroup.get_type(device_groups)
            return device_group_types

        wait(_get_device_group_types,
             condition=lambda types: 'DGT_FAILOVER' not in types,
             progress_cb=lambda _: 'Waiting for device group cleanup')

"""

get_app_names = None
class GetAppNames(IcontrolCommand):
    '''
    Return the names of all the apps.
    '''
    def __init__(self, partition, *args, **kwargs):
        super(GetAppNames, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            ic.System.Session.set_recursive_query_state(state='STATE_ENABLED')
            apps = ic.Management.ApplicationService.get_list()
            ic.System.Session.set_recursive_query_state(state='STATE_DISABLED')
            return apps
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_app_vars = None
class GetAppVars(IcontrolCommand):
    '''
    Get all the scalar variables in an app
    '''
    def __init__(self, partition, app, *args, **kwargs):
        super(GetAppVars, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.app = app

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            ic.System.Session.set_recursive_query_state(state='STATE_ENABLED')
            scalar_vars = self.api.Management.ApplicationService.get_scalar_vars(apps=[self.app])
            ic.System.Session.set_recursive_query_state(state='STATE_DISABLED')
            # We get back a list of lists: one list per app. We only want
            # vars from one app, so return that.
            return scalar_vars[0]
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

get_app_tables = None
class GetAppTables(IcontrolCommand):
    '''
    Get all the table variables in an app
    '''
    def __init__(self, partition, app, *args, **kwargs):
        super(GetAppTables, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.app = app

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            ic.System.Session.set_recursive_query_state(state='STATE_ENABLED')
            table_vars = ic.Management.ApplicationService.get_table_vars(apps=[self.app])
            ic.System.Session.set_recursive_query_state(state='STATE_DISABLED')
            # We get back a list of lists: one list per app. We only want
            # vars from one app, so return that.
            return table_vars[0]
        finally:
            ic.System.Session.set_active_folder(folder='/Common')


# debug function
get_vlan_list = None
class GetVlanList(IcontrolCommand):

    def setup(self):
        ic = self.api
        partitions = ic.Management.Partition.get_partition_list()
        vlanlist = []
        for partition in partitions:
            pt_name = _fix_partition(partition['partition_name'])
            try:
                ic.System.Session.set_active_folder(folder=pt_name)
                LOG.info('Getting VLANS from {}'.format(pt_name))
                vlans = ic.Networking.VLAN.get_list()
                for vlan in vlans:
                    LOG.info('Found VLAN {}'.format(vlan))
                    vlanlist.append(vlan)
            except:
                LOG.info('Failure getting VLANs from {}'.format(pt_name))
        ic.System.Session.set_active_folder(folder='/Common')
        return vlanlist

# cleanup we should not have to do...
delete_host_vlans = None
class DeleteHostVlans(IcontrolCommand):
    
    def setup(self):
        ic = self.api
        # first, delete all vlans on all guests
        force_cleanup = False
        guests = ic.System.VCMP.get_list()
        ic.System.Session.set_active_folder(folder='/Common')
        clientvlans = ic.System.VCMP.get_vlan(guests=guests)
        for guest, vlanlist in zip(guests, clientvlans):
            LOG.info('list of vlans for {}: {}'.format(guest, vlanlist))
            for vlan in vlanlist:
                name = vlan.replace('/Common/', '')
                try:
                    ic.System.VCMP.remove_vlan(guests=[guest], vlans=[name])
                except Exception as e:
                    LOG.error('Failure deleting client vlan: Error:\n {}'.format(e))
                    force_cleanup = True
        ic.System.VCMP.remove_all_vlans(guests=guests)
        vlans = ic.Networking.VLAN.get_list()
        if len(vlans) > 0:
            for vlan in vlans:
                LOG.error('BZ581787: Deleting vlan {} on vcmp host'.format(vlan))
                try:
                    ic.Networking.VLAN.delete_vlan(vlans=[vlan])
                except Exception as e:
                    LOG.error('Failure deleting vlan: Error:\n {}'.format(e))
                    force_cleanup = True
        return force_cleanup


delete_all_vlans = None
class DeleteAllVlans(IcontrolCommand):
    def setup(self):
        ic = self.api
        partitions = ic.Management.Partition.get_partition_list()
        for partition in partitions:
            pt_name = _fix_partition(partition['partition_name'])
            try:
                ic.System.Session.set_active_folder(folder=pt_name)
                LOG.info('Getting VLANS from {}'.format(pt_name))
                vlans = ic.Networking.VLAN.get_list()
                for vlan in vlans:
                    try:
                        LOG.info('Deleting vlan {}'.format(vlan))
                        ic.Networking.VLAN.delete_vlan(vlans=[vlan])
                    except Exception as e:
                        LOG.error('Failure deleting vlan: Error:\n {}'.format(e))
            except:
                LOG.info('Failure getting VLANs from {}'.format(pt_name))
        ic.System.Session.set_active_folder(folder='/Common')


# Verify that the list of VLANs matches the expected list passed in as parameter.
# Used currently to verify presence or absence of HA VLANs.
check_vlan_list = None
class CheckVlanList(IcontrolCommand):
    def __init__(self, exp=[], *args, **kwargs):
        super(CheckVlanList, self).__init__(*args, **kwargs)
        self.exp = exp

    def setup(self):
        ic = self.api
        vlans = ic.Networking.VLAN.get_list()
        if vlans.sort() != self.exp.sort():
            raise Exception('Expected VLAN list: "{}" Got: "{}"'.format(self.exp, vlans))

# Verify that the list of SelfIPs matches the expected list passed in as parameter.
# Used currently to verify presence or absence of HA SelfIPs.
check_selfip_list = None
class CheckSelfipList(IcontrolCommand):
    def __init__(self, exp=[], *args, **kwargs):
        super(CheckSelfipList, self).__init__(*args, **kwargs)
        self.exp = exp

    def setup(self):
        ic = self.api
        sips = ic.Networking.SelfIPV2.get_list()
        if sips.sort() != self.exp.sort():
            raise Exception('Expected SelfIP list: "{}" Got: "{}"'.format(self.exp, sips))

get_selfip_info = None
class GetSelfipInfo(IcontrolCommand):
    def __init__(self, partition, targetname, *args, **kwargs):
        super(GetSelfipInfo, self).__init__(*args, **kwargs)
        self.partition = _fix_partition(partition)
        self.targetname = targetname

    def setup(self):
        ic = self.api
        try:
            ic.System.Session.set_active_folder(folder=self.partition)
            sips = ic.Networking.SelfIPV2.get_list()
            for sipname in sips:
                if sipname == self.targetname:
                    addrlist = ic.Networking.SelfIPV2.get_address(self_ips=[sipname])
                    masklist = ic.Networking.SelfIPV2.get_netmask(self_ips=[sipname])
                    portaccesslist = ic.Networking.SelfIPV2.get_allow_access_list(self_ips=[sipname])
                    if len(addrlist) != 1 or len(masklist) != 1 or len(portaccesslist) != 1:
                        raise Exception('Invalid data for selfip')
                    return addrlist[0], masklist[0], portaccesslist[0]
        finally:
            ic.System.Session.set_active_folder(folder='/Common')

wait_selfip_deleted = None
class WaitSelfipDeleted(IcontrolCommand):
    '''
    Wait for the named SelfIP to be deleted. We use this to ensure that
    the HA SelfIP is cleaned up after an LDevVip is deleted.
    '''
    def __init__(self, name, *args, **kwargs):
        super(WaitSelfipDeleted, self).__init__(*args, **kwargs)
        self.name = name

    def setup(self):
        ic = self.api
        return wait(lambda: ic.Networking.SelfIPV2.get_list(),
                    condition=lambda x: self.name not in x,
                    progress_cb=lambda x: 'Waiting for SelfIP: {} to be removed from: {}'.format(self.name, x),
                    timeout=60, interval=5)

wait_vlan_deleted = None
class WaitVlanDeleted(IcontrolCommand):
    '''
    Wait for the named VLAN to be deleted. We use this to ensure that
    the HA VLAN is cleaned up after an LDevVip is deleted.
    '''
    def __init__(self, name, timeout=20, *args, **kwargs):
        super(WaitVlanDeleted, self).__init__(*args, **kwargs)
        self.name = name
        self.timeout = timeout

    def setup(self):
        ic = self.api
        return wait(lambda: ic.Networking.VLAN.get_list(),
                    condition=lambda x: self.name not in x,
                    progress_cb=lambda x: 'Waiting for VLAN: {} to be removed from: {}'.format(self.name, x),
                    timeout=self.timeout, interval=2)
