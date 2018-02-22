'''
Created on May 26, 2015

@author: zhan
'''

from .base import IcontrolRestCommand
from f5test.base import NEXT_NUMBER
from f5test.commands.rest.device import DEFAULT_ADC_GROUP
from f5test.interfaces.testcase import ContextHelper
from ...interfaces.rest.emapi.objects.shared import ConfigDeploy,\
    RefreshWorkingConfig, RefreshCurrentConfig
from ...interfaces.rest.emapi.objects.system import MachineIdResolver
from f5test.interfaces.rest.emapi.objects.adccore import (WorkingLtmNode,
                                                          WorkingLtmPool,
                                                          WorkingLtmPoolMember,
                                                          WorkingLtmVip)
from f5test.interfaces.rest.emapi.objects.shared import DeviceResolver
import logging


LOG = logging.getLogger(__name__)

LTM_NODE = 'ltm/node'
LTM_POOL = 'ltm/pool'
LTM_VIRTUAL = 'ltm/virtual'
LTM_VIRTUAL_ADDRESS = 'ltm/virtual-address'
LTM_RULE = 'ltm/rule'
LTM_PROFILE_HTTP = 'ltm/profile/http'
LTM_MONITOR_HTTP = 'ltm/monitor/http'

POOL_MEMBER_TRANS_URI = 'https://localhost/mgmt/cm/shared/config/transform/ltm/pool/members'
POOL_MEMBER_STATE_KIND = 'cm:shared:config:%s:ltm:pool:members:poolmemberstate'

PARTITION = 'Common'


# This is for BigIQ 4.6 and lower. For 5.0 and above, use DeployAdcObjects2
deploy_adc_objects = None
class DeployAdcObjects(IcontrolRestCommand):  # @IgnorePep8
    """Deploy ADC objects to bigip.

    @param name: deploy task name
    @type name: string

    @description: description of the deploy task
    @type: string

    @device_id: the id of the target bigip device
    @type: string

    """
    def __init__(self, name, description, device_id, timeout=60, *args, **kwargs):
        super(DeployAdcObjects, self).__init__(*args, **kwargs)
        self.name = name
        self.description = description
        self.device_id = device_id
        self.timeout = timeout

    def setup(self):
        LOG.info("Deploy adc object to machine %s ..." % self.device_id)
        payload = ConfigDeploy()
        payload.name = self.name
        payload.description = self.description
        payload.configPaths.append({'icrObjectPath': LTM_NODE})
        payload.configPaths.append({'icrObjectPath': LTM_POOL})
        payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL})
        # if self.ifc.version >= 'bigiq 4.6.0':
        if self.ifc.version >= 'bigiq 5.0.0':
            LOG.info("For new object models after 5.0.0")
            payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL_ADDRESS})
            payload.configPaths.append({'icrObjectPath': LTM_RULE})
            payload.configPaths.append({'icrObjectPath': LTM_PROFILE_HTTP})
            payload.configPaths.append({'icrObjectPath': LTM_MONITOR_HTTP})
        payload.kindTransformMappings.append(
            {'managementAuthorityKind': POOL_MEMBER_STATE_KIND % 'current',
             'transformUri': POOL_MEMBER_TRANS_URI}
            )
        payload.kindTransformMappings.append(
            {'managementAuthorityKind': POOL_MEMBER_STATE_KIND % 'working',
             'transformUri': POOL_MEMBER_TRANS_URI}
            )
        payload.deviceReference.set('https://localhost' + MachineIdResolver.ITEM_URI % self.device_id)
        task = self.api.post(ConfigDeploy.URI, payload)
        ConfigDeploy.wait(self.api, task, timeout=self.timeout)


# This is for BigIQ 4.6 and lower.
sync_adc_objects = None
class SyncAdcObjects(IcontrolRestCommand):  # @IgnorePep8
    """Syn working config and current config from bigip ...

    @device_id: the id of the target bigip device
    @type: string

    """
    def __init__(self, device_id, *args, **kwargs):
        super(SyncAdcObjects, self).__init__(*args, **kwargs)
        self.device_id = device_id

    def setup(self):
        LOG.info("Syn working config and current config from bigip ...")
        LOG.debug('device_id is %s' % self.device_id)
        payload = RefreshCurrentConfig()
        payload.configPaths.append({'icrObjectPath': LTM_NODE})
        payload.configPaths.append({'icrObjectPath': LTM_POOL})
        payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL})
        payload.configPaths.append({'icrObjectPath': LTM_RULE})
        # if self.ifc.version >= 'bigiq 4.6.0':
        if self.ifc.version >= 'bigiq 5.0.0':
            LOG.info("For new object models after 5.0.0")
            payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL_ADDRESS})
            payload.configPaths.append({'icrObjectPath': LTM_PROFILE_HTTP})
            payload.configPaths.append({'icrObjectPath': LTM_MONITOR_HTTP})
        payload.deviceReference.set('https://localhost' + MachineIdResolver.ITEM_URI % self.device_id)
        task = self.api.post(RefreshCurrentConfig.URI, payload)
        RefreshCurrentConfig.wait(self.api, task)

        payload = RefreshWorkingConfig()
        payload.configPaths.append({'icrObjectPath': LTM_NODE})
        payload.configPaths.append({'icrObjectPath': LTM_POOL})
        payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL})
        payload.configPaths.append({'icrObjectPath': LTM_RULE})
        # if self.ifc.version >= 'bigiq 4.6.0':
        if self.ifc.version >= 'bigiq 5.0.0':
            LOG.info("For new object models after 5.0.0")
            payload.configPaths.append({'icrObjectPath': LTM_VIRTUAL_ADDRESS})
            payload.configPaths.append({'icrObjectPath': LTM_PROFILE_HTTP})
            payload.configPaths.append({'icrObjectPath': LTM_MONITOR_HTTP})
        payload.deviceReference.set('https://localhost' + MachineIdResolver.ITEM_URI % self.device_id)
        task = self.api.post(RefreshWorkingConfig.URI, payload)
        RefreshWorkingConfig.wait(self.api, task)


def ipv4_address_generator(first=10, second=1, third=1, fourth=1):
    """ Programmatically generate IP v4 addresses, skipping 255 in the
    3rd or 4th place.
    """
    while second <= 255:
        yield '{0}.{1}.{2}.{3}'.format(first, second, third, fourth)

        if fourth >= 255:
            fourth = 0
            third += 1
        else:
            fourth += 1

        if third > 255:
            third = 0
            second += 1


create_adc_node_objects = None
class CreateAdcNodeObjects(IcontrolRestCommand):  # @IgnorePep8
    """ Create the specified number of ADC Node objects on the BIG-IQ for
        the specified BIG-IP.  Works for BIG-IQ 4.6.0 and later.

        You must deploy the ADC objects from the BIG-IQ to the BIG-IP(s) with
        a separate call.
    """
    def __init__(self, node_count, bigip, *args, **kwargs):
        """ Object initialization.

            @param node_count: The number of ADC nodes to create.
            @param bigip: BIG-IP device, as returned by MachineIdResolver.
        """
        super(CreateAdcNodeObjects, self).__init__(*args, **kwargs)
        self.node_count = node_count
        self.bigip = bigip
        self.object_counter = 0
        self.context = ContextHelper(__name__)
        self.cfgifc = self.context.get_config()
        self.ip_gen = ipv4_address_generator()

    def run(self):
        """ Generate the specified number of ADC Node objects for the given
            BIG-IP in the default BIG-IQ.

            @return: List of Node Names that were generated, a list of
            Node Addresses that were generated, and the Self-IP links for
            each node generated.  These are needed when generating Pools and
            Virtual Servers.
        """
        LOG.info("Creating {0} node(s) in the BigIQ working config..."
                 .format(self.node_count))
        node_names = []
        node_addresses = []
        node_selflinks = []

        for _ in range(self.node_count):
            num = NEXT_NUMBER.get_next_number()
            self.object_counter = NEXT_NUMBER.get_next_number()
            node_name = 'ScaleNode-%s-device%d-obj%d' %\
                        (self.cfgifc.get_session().name, num,
                         self.object_counter)
            node_names.append(node_name)
            node_address = next(self.ip_gen)
            node_addresses.append(node_address)

            payload = WorkingLtmNode(name=node_name,
                                     address=node_address,
                                     partition=PARTITION)
            payload.deviceReference.set('https://localhost' +
                                        DeviceResolver.DEVICE_URI %
                                        (DEFAULT_ADC_GROUP,
                                         self.bigip['machineId']))
            create_node_resp = self.api.post(WorkingLtmNode.URI, payload)
            node_selflinks.append(create_node_resp.selfLink)

        return node_names, node_addresses, node_selflinks


create_adc_pool_objects = None
class CreateAdcPoolObjects(IcontrolRestCommand):  # @IgnorePep8
    """ Create the specified number of ADC Pool objects on the BIG-IQ for
        the specified BIG-IP.  Works for BIG-IQ 4.6.0 and later.

        You must deploy the ADC objects from the BIG-IQ to the BIG-IP(s) with
        a separate call.
    """
    def __init__(self, pool_count, pool_member_count, bigip, node_names,
                 node_addresses, node_selflinks, *args, **kwargs):
        """ Object initialization.

            @param pool_count: The number of ADC pools to create.
            @param pool_member_count: The number of members per ADC pool to
            create.
            @param bigip: BIG-IP device, as returned by MachineIdResolver.
            @param node_names: List of Node Names to use to link up with
            the pool members.
            @param node_addresses: List of Node IP Addresses to use to link
            up with the pool members.
            @param node_selflinks: List of Node Selflinks to use to link up
            with the pool members.
        """
        super(CreateAdcPoolObjects, self).__init__(*args, **kwargs)
        self.pool_count = pool_count
        self.pool_member_count = pool_member_count
        self.bigip = bigip
        self.object_counter = 0
        self.context = ContextHelper(__name__)
        self.cfgifc = self.context.get_config()
        self.node_names = node_names
        self.node_addresses = node_addresses
        self.node_selflinks = node_selflinks
        self.ip_gen = ipv4_address_generator()

    def run(self):
        """ Generate the specified number of ADC Pool objects for the given
            BIG-IP in the default BIG-IQ.

            @returns: List of Pool names and list of Pool selflinks that
            were generated.
        """
        LOG.info("Creating {0} pool(s) in the BigIQ working config..."
                 .format(self.pool_count))
        pool_names = []
        pool_selflinks = []
        num = NEXT_NUMBER.get_next_number()

        for i in range(self.pool_count):
            self.object_counter = NEXT_NUMBER.get_next_number()
            pool_name = 'ScalePool-%s-device%d-obj%d' %\
                        (self.cfgifc.get_session().name, num,
                         self.object_counter)
            pool_names.append(pool_name)
            payload = WorkingLtmPool(name=pool_name,
                                     fullPath='/' + PARTITION + '/' +
                                     pool_name,
                                     partition=PARTITION,
                                     loadBalancingMode='round-robin')
            payload.deviceReference.set('https://localhost' +
                                        DeviceResolver.DEVICE_URI %
                                        (DEFAULT_ADC_GROUP,
                                         self.bigip['machineId']))
            create_pool_resp = self.api.post(WorkingLtmPool.URI, payload)
            pool_selflinks.append(create_pool_resp.selfLink)

            pool_member_port = 0
            for _ in range(self.pool_member_count):
                self.object_counter = NEXT_NUMBER.get_next_number()
                pool_member_port += 1
                # Will need reworking if we decide we need more than 65k
                # members per pool
                pool_member_name = '{0}:{1}'.format(self.node_names[i],
                                                    pool_member_port)
                payload = WorkingLtmPoolMember(name=pool_member_name,
                                               address=self.node_addresses[i],
                                               fullPath='/' + PARTITION +
                                               '/' + pool_member_name,
                                               partition=PARTITION)
                payload.nodeReference.set(self.node_selflinks[i])
                self.api.post(WorkingLtmPoolMember.URI %
                              create_pool_resp.id, payload)
        return pool_names, pool_selflinks


adc_vip_objects_create = None
class AdcVipObjectsCreate(IcontrolRestCommand):  # @IgnorePep8
    """ Create the specified number of ADC VIP objects on the BIG-IQ for
        the specified BIG-IP.  Works for BIG-IQ 4.6.0 and later.

        You must deploy the ADC objects from the BIG-IQ to the BIG-IP(s) with
        a separate call.
    """
    def __init__(self, vip_count, bigip, pool_names, pool_selflinks,
                 *args, **kwargs):
        """ Object initialization.

            @param vip_count: The number of ADC VIPs to create.
            @param bigip: BIG-IP device, as returned by MachineIdResolver.
            @param pool_names: Names of the Pools previously created.
            @param pool_selflinks: List of Pool Selflinks to use to link up
            with the VIPs.
        """
        super(AdcVipObjectsCreate, self).__init__(*args, **kwargs)
        self.vip_count = vip_count
        self.bigip = bigip
        self.object_counter = 0
        self.context = ContextHelper(__name__)
        self.cfgifc = self.context.get_config()
        self.pool_names = pool_names
        self.pool_selflinks = pool_selflinks
        self.ip_gen = ipv4_address_generator()

    def setup(self):
        """ Generate the specified number of ADC VIP objects for the given
            BIG-IP in the default BIG-IQ.
        """
        LOG.info("Creating {0} VIP(s) in the BigIQ working config..."
                 .format(self.vip_count))
        num = NEXT_NUMBER.get_next_number()

        for i in range(self.vip_count):
            self.object_counter = NEXT_NUMBER.get_next_number()
            vip_name = 'ScaleVip-%s-device%d-obj%d' %\
                       (self.cfgifc.get_session().name, num,
                        self.object_counter)
            vip_address = next(self.ip_gen)
            payload = WorkingLtmVip(name=vip_name,
                                    destination=vip_address + ':80',
                                    fullPath='/' + PARTITION + '/' +
                                    vip_name, partition=PARTITION,
                                    pool='/' + PARTITION + '/' +
                                    self.pool_names[i])
            payload.deviceReference.set('https://localhost' +
                                        DeviceResolver.DEVICE_URI %
                                        (DEFAULT_ADC_GROUP,
                                         self.bigip['machineId']))
            payload.poolReference.set(self.pool_selflinks[i])
            self.api.post(WorkingLtmVip.URI, payload)
