'''
Created on December 4, 2015

@author: langer
'''
import logging
from httplib import HTTP_PORT

from f5test.commands.rest.biqmgmtcm.system import (CM_GLOBAL_ADC_NAME, import_service_config, get_machine_id,
                                                   DEFAULT_CM_ADC_DEVICE_GROUP)
from f5test.interfaces.rest.emapi.objects import DeviceResolver
from f5test.interfaces.rest.emapi.objects.bigip import Rule, Pool, Node, VirtualServer, SelfIp
from f5test.interfaces.rest.emapi.objects.biqmgmtcm.unified_discovery import DeviceDiscovery
from f5test.utils.icrd import get_full_path, split_full_path
from f5test.utils.rest import filter_search_for_item
from f5test.utils.wait import wait_args
from .base import IcontrolRestCommand
from ...interfaces.rest.emapi.objects.adccore import (AdcDeployConfigTask, AdcDeclareMgmtAuthorityTask, WorkingLtmIrule,
                                                      WorkingLtmNode, WorkingLtmPool, WorkingLtmPoolMember,
                                                      WorkingLtmVip, WorkingLtmVipProfile, WorkingNetTrafficGroup,
                                                      WorkingNetSelfIp, WorkingNetVlan)
from ...interfaces.rest.emapi.objects.base import ReferenceList, TaskError


LOG = logging.getLogger(__name__)

DEFAULT_BIGIP_PARTITION = 'Common'
DEFAULT_IPV4_MASK = '255.255.255.255'
DEFAULT_VIP_LOAD_BALANCING_MODE = 'round-robin'
DEFAULT_VIP_SOURCE_ADDRESS = '0.0.0.0/0'

REFRESH_CURRENT_CONFIG_TIMEOUT = 300
REFRESH_WORKING_CONFIG_TIMEOUT = 300


deploy_adc_objects = None
class DeployAdcObjects(IcontrolRestCommand):  # @IgnorePep8
    """Deploy ADC objects to bigip using the adc-core API
       (used for BIG-IQ 5.0 and above).

    @param name: deploy task name
    @type name: string

    @description: description of the deploy task
    @type: string

    @device_state_list: the list of the target bigip device states
    @type: list

    @timeout: timeout value in seconds
    @type: int

    """
    def __init__(self, name, description, device_state_list, skip_distribution=False, timeout=240, *args, **kwargs):
        super(DeployAdcObjects, self).__init__(*args, **kwargs)
        self.name = name
        self.description = description
        self.skip_distribution = skip_distribution
        self.device_state_list = device_state_list
        self.timeout = timeout

    def setup(self):
        super(DeployAdcObjects, self).setup()
        LOG.info("Deploy adc object to BigIP devices")
        payload = AdcDeployConfigTask()
        payload.name = self.name
        payload.description = self.description
        payload.skipDistribution = self.skip_distribution
        payload.deviceReferences = ReferenceList()

        for device_state in self.device_state_list:
            device_reference = 'https://localhost' + DeviceResolver.DEVICE_URI % (DEFAULT_CM_ADC_DEVICE_GROUP, device_state.uuid)
            payload.deviceReferences = ReferenceList()
            payload.deviceReferences.append({'link': device_reference})

            task = self.api.post(AdcDeployConfigTask.URI, payload)
            payload.wait(self.api, task, timeout=self.timeout)


refresh_adc_current_config = None
class RefreshAdcCurrentConfig(IcontrolRestCommand):  # @IgnorePep8
    """
    Re-discovers ADC/LTM service (i.e. re-imports current config) for a trusted BIGIP
    raises AddServiceException on failure
    @param device: An instance of f5test.interfaces.config.DeviceAccess
    @param timeout: Timeout in seconds for refresh operation
    @return: None
    """
    def __init__(self, device, timeout=REFRESH_CURRENT_CONFIG_TIMEOUT, *args, **kwargs):
        super(RefreshAdcCurrentConfig, self).__init__(*args, **kwargs)
        self.device = device
        self.timeout = timeout
        self.uri = None

    def set_uri(self, task):
        self.uri = DeviceDiscovery.ITEM_URI % task.id

    def setup(self):
        super(RefreshAdcCurrentConfig, self).setup()
        LOG.info("refresh current config on {0}".format(str(self.device.get_discover_address())))
        machine_id = get_machine_id(self.device)

        existing_discovery_task = filter_search_for_item(base_uri=DeviceDiscovery.URI,
                                                         search_key='deviceReference/link',
                                                         search_value='*' + machine_id)

        module_list = [{'module': CM_GLOBAL_ADC_NAME}]
        payload = DeviceDiscovery(moduleList=module_list,
                                  status='STARTED')
        self.set_uri(existing_discovery_task)
        self.api.patch(self.uri, payload=payload)
        resp = wait_args(self.api.get, func_args=[self.uri],
                         condition=lambda x: x.status in DeviceDiscovery.FINAL_STATUSES,
                         interval=10,
                         timeout=self.timeout,
                         timeout_message='Re-discovery did not complete in {0} seconds')
        if resp.status == DeviceDiscovery.FAIL_STATE:
            raise TaskError("Re-discovery failed for {0} for ADC service".format(self.device.get_discover_address()))


refresh_adc_working_config = None
class RefreshAdcWorkingConfig(IcontrolRestCommand):  # @IgnorePep8
    """
    Re-imports ADC/LTM service (i.e. re-imports working config) for a trusted BIGIP
    raises ImportServiceException on failure
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param use_bigiq_for_conflict: Boolean flag for conflict resolution
    @param snapshot_working_config: Snapshot working config, Same as Import checkbox on UI
    @return: None
    """
    def __init__(self, device, use_bigiq_for_conflict=True, snapshot_working_config=False, *args, **kwargs):
        super(RefreshAdcWorkingConfig, self).__init__(*args, **kwargs)
        self.device = device
        self.service = CM_GLOBAL_ADC_NAME
        if use_bigiq_for_conflict is True:
            self.resolution = 'USE_BIGIQ'
        else:
            self.resolution = 'USE_BIGIP'
        self.snapshot_working_config = snapshot_working_config

    def setup(self):
        super(RefreshAdcWorkingConfig, self).setup()
        LOG.debug('RefreshAdcWorkingConfig.setup()')
        machine_id = get_machine_id(self.device)
        LOG.info('Finding existing import task...')
        old_task = filter_search_for_item(base_uri=AdcDeclareMgmtAuthorityTask.URI,
                                          search_key='deviceReference/link',
                                          search_value='*' + machine_id)
        LOG.info('Deleting existing import task...')
        # Hopefully we won't need to wait for this, but the response contains a job status,
        # so it might be possible that the delete won't finish quickly.
        delete_resp = self.api.delete(AdcDeclareMgmtAuthorityTask.URI_ITEM.format(old_task.id))
        LOG.info('Re-importing ADC...')
        import_service_config(self.device, CM_GLOBAL_ADC_NAME)


create_irule_on_bigip = None
class CreateIruleOnBigip(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates an iRule directly on BIG-IP via icrd
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of iRule to create
    @param body: body of iRule. should be ready to be posted directly (all characters escaped as necessary)
    @param partition: partition in which to create the object
    @return: None
    """
    def __init__(self, device, name, body=None, partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreateIruleOnBigip, self).__init__(device, *args, **kwargs)
        self.device = device
        self.name = name
        self.body = body
        self.partition = partition

    def run(self):
        super(CreateIruleOnBigip, self).run()
        LOG.debug('starting create_irule_on_bigip')
        payload = Rule(name=self.name,
                       partition=self.partition)
        if self.body:
            payload.apiAnonymous = self.body

        response = self.api.post(Rule.URI, payload)

        return response


create_node_on_bigip = None
class CreateNodeOnBigip(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a Node directly on BIG-IP via icrd
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of node to create
    @param address: IP address of node
    @param path: path/folder in which to create the node
    @param partition: partition in which to create the object
    @return: None
    """
    def __init__(self, device, name, address, path='', partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreateNodeOnBigip, self).__init__(device, *args, **kwargs)
        self.device = device
        self.name = name
        self.address = address
        self.path = path
        self.partition = partition

    def run(self):
        super(CreateNodeOnBigip, self).run()
        LOG.debug('starting create_node_on_bigip')
        payload = Node(name=self.name,
                       partition=self.partition,
                       address=self.address)

        if self.path:
            payload.subPath = self.path

        response = self.api.post(Node.URI, payload)

        return response


create_pool_on_bigip = None
class CreatePoolOnBigip(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a Pool directly on BIG-IP via icrd
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of pool to create
    @param members: list of (node_name, port) tuples to add as members to the pool
    @param path: path/folder in which to create the pool
    @param partition: partition in which to create the object
    @return: None
    """
    def __init__(self, device, name, members=None, path='', partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreatePoolOnBigip, self).__init__(device, *args, **kwargs)
        # TODO: Support more properties
        self.device = device
        self.name = name
        self.members = members
        if self.members is None:
            self.members = []
        self.path = path
        self.partition = partition

    def run(self):
        super(CreatePoolOnBigip, self).run()
        LOG.debug('starting create_pool_on_bigip')
        payload = Pool(name=self.name,
                       partition=self.partition)

        if self.members:
            payload.members = []
            for node_name, port in self.members:
                member = "{0}:{1}".format(node_name, port)
                payload.members.append({'name': member})

        if self.path:
            payload.subPath = self.path

        response = self.api.post(Pool.URI, payload)

        return response


create_virtual_on_bigip = None
class CreateVirtualOnBigip(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a Virtual Server directly on BIG-IP via icrd
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of virtual server to create
    @param address: IP address to associate with the virtual server
    @param port: port to associate with the virtual server
    @param pool: pool name to attach to the virtual server
    @param irule_list: list of iRule names to attach to the virtual server
    @param path: path/folder in which to create the virtual server
    @param description: description for the virtual server
    @param ip_protocol: ipProtocol for the virtual server
    @param profiles: list of profile names for directing and managing traffic for the virtual server
    @param persist: persistence profiles for the virtual server
    @param source_addr_translation: source address translation setting for the virtual server
    @param set_defaults: sets some basic default values for test purposes
    @param partition: partition in which to create the object
    @return: None
    """
    def __init__(self, device, name, address, port=HTTP_PORT, pool='', irule_list=None, path='', description='',
                 ip_protocol='', profiles='', persist='', source_addr_translation='',
                 set_defaults=False, partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreateVirtualOnBigip, self).__init__(device, *args, **kwargs)
        self.device = device
        self.name = name
        self.address = address
        self.port = port
        self.pool = pool
        self.irule_list = irule_list
        self.path = path
        self.description = description
        self.ip_protocol = ip_protocol
        self.profiles = profiles
        self.persist = persist
        self.source_addr_translation = source_addr_translation
        self.set_defaults = set_defaults
        self.partition = partition

    def run(self):
        super(CreateVirtualOnBigip, self).run()
        LOG.debug('starting create_virtual_on_bigip')
        destination = ('/' + self.partition + '/{0}:{1}').format(self.address, self.port)
        payload = VirtualServer(name=self.name,
                                partition=self.partition,
                                destination=destination)

        if self.set_defaults:
            payload.set_all_defaults()
        if self.pool:
            payload.pool = self.pool
        if self.irule_list:
            payload.rules = self.irule_list
        if self.path:
            payload.subPath = self.path
        if self.description:
            payload.description = self.description
        if self.ip_protocol:
            payload.ipProtocol = self.ip_protocol
        if self.profiles:
            payload.profiles = [{'name': x for x in self.profiles}]
        if self.persist:
            payload.persist = [{'name': self.persist}]
        if self.source_addr_translation:
            payload.sourceAddressTranslation = {'type': self.source_addr_translation}

        response = self.api.post(VirtualServer.URI, payload)

        return response


create_irule_on_bigiq = None
class CreateIruleOnBigiq(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates an iRule in the BIG-IQ's working-config
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of iRule to create
    @param body: body of iRule. should be ready to be posted directly (all characters escaped as necessary)
    @param partition: partition in which to create the object
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, name, body=None, partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreateIruleOnBigiq, self).__init__(*args, **kwargs)
        self.name = name
        self.body = body
        self.partition = partition

    def run(self):
        super(CreateIruleOnBigiq, self).run()
        LOG.debug('starting create_irule_on_bigiq')
        payload = WorkingLtmIrule(name=self.name,
                                  partition=self.partition)
        if self.body:
            payload.body = self.body

        response = self.api.post(WorkingLtmIrule.URI, payload)

        return response


create_node_on_bigiq = None
class CreateNodeOnBigiq(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a node in the BIG-IQ's working-config
    @param device_id: the id of BIG-IP on which to create the object
    @param name: name of node to create
    @param address: IP address of node
    @param path: path/folder in which to create the node
    @param partition: partition in which to create the object
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, device_id, name, address, path='', partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(CreateNodeOnBigiq, self).__init__(*args, **kwargs)
        self.device_id = device_id
        self.name = name
        self.address = address
        self.path = path
        self.partition = partition

    def run(self):
        super(CreateNodeOnBigiq, self).run()
        LOG.debug('starting create_node_on_bigiq')
        device_ref = {'link': 'https://localhost' + DeviceResolver.DEVICE_URI % (DEFAULT_CM_ADC_DEVICE_GROUP,
                                                                                 self.device_id)}
        payload = WorkingLtmNode(name=self.name,
                                 partition=self.partition,
                                 address=self.address,
                                 deviceReference=device_ref)

        if self.path:
            payload.subPath = self.path

        response = self.api.post(WorkingLtmNode.URI, payload)

        return response


add_pool_member_to_bigiq_virtual = None
class AddPoolMemberToBigiqVirtual(IcontrolRestCommand):  # @IgnorePep8
    """
    Adds a pool member in the BIG-IQ's working-config
    @param pool_id: the id of pool on which to create the object
    @param node_ref: reference (link) of node to attach
    @param port: port number to use for pool member
    @param partition: partition in which to create the object
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, pool_id, node_ref, port=HTTP_PORT, partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(AddPoolMemberToBigiqVirtual, self).__init__(*args, **kwargs)
        self.pool_id = pool_id
        self.node_ref = node_ref
        self.port = port
        self.partition = partition

    def run(self):
        super(AddPoolMemberToBigiqVirtual, self).run()
        LOG.debug('starting create_pool_member_on_bigiq')
        node = self.api.get(self.node_ref)

        payload = WorkingLtmPoolMember(name='{0}:{1}'.format(node.name, self.port),
                                       partition=self.partition,
                                       nodeReference={'link': self.node_ref},
                                       port=self.port)

        response = self.api.post(WorkingLtmPoolMember.URI % self.pool_id, payload)

        return response


create_pool_on_bigiq = None
class CreatePoolOnBigiq(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a pool in the BIG-IQ's working-config

    @param device_id: the id of BIG-IP on which to create the object
    @param name: name of pool to create
    @param members: list of (node.selfLink, port) tuples to add as members to the pool
    @param loadBalancingMode: load balancing mode to use for pool
    @param partition: partition in which to create the object
    @param subPath: path/folder in which to create the pool
    @param allowNat: sets allowNat property to given value (bool)
    @param allowSnat: sets allowSnat property to given value (bool)
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, device_id, name, members=None, loadBalancingMode=DEFAULT_VIP_LOAD_BALANCING_MODE,
                 partition=DEFAULT_BIGIP_PARTITION, subPath=None, allowNat=None, allowSnat=None, *args, **kwargs):
        super(CreatePoolOnBigiq, self).__init__(*args, **kwargs)
        # TODO: Support more properties
        self.device_id = device_id
        self.name = name
        self.members = members
        if self.members is None:
            self.members = []
        self.load_balancing_mode = loadBalancingMode  # Camel cased for easier kwarg passing
        self.partition = partition
        self.subPath = subPath
        self.allowNat = allowNat
        self.allowSnat = allowSnat
        self.optional_attributes = ['allowNat', 'allowSnat', 'subPath']

    def run(self):
        super(CreatePoolOnBigiq, self).run()
        LOG.debug('starting create_pool_on_bigiq')
        device_ref = {'link': 'https://localhost' + DeviceResolver.DEVICE_URI % (DEFAULT_CM_ADC_DEVICE_GROUP,
                                                                                 self.device_id)}
        payload = WorkingLtmPool(name=self.name,
                                 partition=self.partition,
                                 deviceReference=device_ref,
                                 loadBalancingMode=self.load_balancing_mode)

        for attrib in self.optional_attributes:
            if getattr(self, attrib) is not None:
                setattr(payload, attrib, getattr(self, attrib))

        response = self.api.post(WorkingLtmPool.URI, payload)

        # Attach pool members after we get the pool's ID
        for node_name, port in self.members:
            nodes = filter_search_for_item(WorkingLtmNode.URI, 'name', node_name, return_top_result=False)
            # Just in case you did a bad thing and have multiple nodes with the same names on different devices.
            node = [x for x in nodes if x.deviceReference.id == self.device_id][0]
            add_pool_member_to_bigiq_virtual(response.id, node.selfLink, port)

        return response


create_virtual_on_bigiq = None
class CreateVirtualOnBigiq(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a virtual server in the BIG-IQ's working-config
    @param device_id: the id of BIG-IP on which to create the object
    @param name: name of virtual server to create
    @param destination: destination "IP address:port" to associate with the virtual server
    @param partition: partition in which to create the object
    @param mask: destination mask
    @param sourceAddress: source address/mask to associate with the virtual server
    @param pool_ref: pool reference (link) to attach to the virtual server
    @param description: description for the virtual server
    @param irules: list of iRule names (str) or references (link dict) to attach to the virtual server
    @param profiles: list of profile names or references to attach to the virtual server in 'all' context
    @param path: path/folder in which to create the pool
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, device_id, name, destination, partition=DEFAULT_BIGIP_PARTITION, mask=DEFAULT_IPV4_MASK,
                 sourceAddress=DEFAULT_VIP_SOURCE_ADDRESS, pool_ref=None, description='', irules=None, profiles=None,
                 path='', *args, **kwargs):
        super(CreateVirtualOnBigiq, self).__init__(*args, **kwargs)
        self.device_id = device_id
        self.name = name
        self.destination = destination
        self.partition = partition
        self.mask = mask
        self.source_address = sourceAddress  # Input intentionally camel cased to make it easier to supply kwargs.
        self.pool_ref = pool_ref
        self.description = description
        self.irules = irules
        self.profiles = profiles
        self.path = path

    def run(self):
        super(CreateVirtualOnBigiq, self).run()
        LOG.debug('starting create_virtual_on_bigiq')
        device_ref = {'link': 'https://localhost' + DeviceResolver.DEVICE_URI % (DEFAULT_CM_ADC_DEVICE_GROUP,
                                                                                 self.device_id)}
        payload = WorkingLtmVip(name=self.name,
                                partition=self.partition,
                                deviceReference=device_ref,
                                sourceAddress=self.source_address,
                                destination=self.destination,
                                mask=self.mask)

        if self.pool_ref:
            payload.poolReference = self.pool_ref
        if self.description:
            payload.description = self.description
        if self.irules:
            irule_references = []
            for irule in self.irules:
                if isinstance(irule, dict):
                    irule_references.append(irule)
                else:
                    irule_references.append({'link': filter_search_for_item(
                            WorkingLtmIrule.URI, 'name', irule).selfLink})

            payload.iRuleReferences = irule_references

        if self.path:
            payload.subPath = self.path

        response = self.api.post(WorkingLtmVip.URI, payload)

        if self.profiles:
            add_profiles_to_bigiq_virtual(response.uuid, self.profiles, context='all')

        return response


add_profiles_to_bigiq_virtual = None
class AddProfilesToBigiqVirtual(IcontrolRestCommand):  # @IgnorePep8
    """
    Adds a profile to a virtual server in the BIG-IQ's working-config
    @param virtual_id: the id of virtual server on which to create the object
    @param names: list of names of profiles to attach
    @param context: context in which to attach profiles
    @param partition: partition in which to create the object
    @return: list of POST responses from BIG-IQ (contains object)
    """
    def __init__(self, virtual_id, names, context='all', partition=DEFAULT_BIGIP_PARTITION, *args, **kwargs):
        super(AddProfilesToBigiqVirtual, self).__init__(*args, **kwargs)
        self.virtual_id = virtual_id
        self.names = names
        self.context = context  # TODO: Maybe allow (name, context) tuples?
        self.profiles_dict = {}
        self.uri = WorkingLtmVipProfile.URI % self.virtual_id
        self.partition = partition

    def setup(self):
        super(AddProfilesToBigiqVirtual, self).setup()
        # NOTE: Keep an eye on this filter query. tokumon doesn't support '*', but the
        # legacy still indexer works for working config... for now.
        uri = "/mgmt/shared/index/config?$filter=kind eq 'cm:adc-core:working-config:ltm:profile:*'"
        resp = self.api.get(uri)
        # Filters out all of the profile collections and builds a {name: selfLink} dict for all ltm profiles
        self.profiles_dict = {x['name']: x['selfLink'] for x in resp['items'] if x.get('name')}
        bad_names = [x for x in self.names if x not in self.profiles_dict]
        if bad_names:
            raise ValueError('Requested profiles were not found: {0}'.format(str(bad_names)))

        # Remove existing profiles that match the ones we're attaching, in case the context is different.
        existing_profiles = self.api.get(self.uri)['items']
        profiles_to_delete = [x.selfLink for x in existing_profiles if x in self.names]
        for link in profiles_to_delete:
            self.api.delete(link)

    def run(self):
        super(AddProfilesToBigiqVirtual, self).run()
        responses = []
        for name in self.names:
            reference = self.profiles_dict[name]
            reference_chunks = reference.split('/')
            if len(reference_chunks) > 1:
                profile_type = reference_chunks[-2]
                reference_key = 'profile' + profile_type.title() + 'Reference'
            else:
                raise ValueError(('Could not determine type of requested profile! '
                                  'Profile reference: {0}'.format(reference)))

            link_ref = {'link': reference}
            payload = WorkingLtmVipProfile(name=name,
                                           partition=self.partition,
                                           context=self.context)
            setattr(payload, reference_key, link_ref)

            responses.append(self.api.post(self.uri, payload))

        return responses


create_selfip_on_bigip = None
class CreateSelfipOnBigip(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a Self IP directly on BIG-IP via icrd
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param name: name of node to create
    @param address: IP address of node
    @param vlan: path/folder in which to create the node
    @param partition: partition in which to create the object
    @param subPath: subPath in which to create the object
    @param floating: Enables or disables floating IP valid values: ('enabled', 'disabled')
    @param inheritedTrafficGroup: boolean that sets whether traffic group is inherited from partition/path
    @param trafficGroup: name of traffic group self ip should reference
    @return: POST response from BIG-IP (contains object)
    """
    def __init__(self, device, name, address, vlan, partition=DEFAULT_BIGIP_PARTITION, subPath=None, floating=None,
                 inheritedTrafficGroup=None, trafficGroup=None, *args, **kwargs):
        super(CreateSelfipOnBigip, self).__init__(device, *args, **kwargs)
        self.device = device
        self.name = name
        self.address = address
        self.vlan = vlan
        self.partition = partition
        self.subPath = subPath
        self.floating = floating
        self.inheritedTrafficGroup = inheritedTrafficGroup
        self.trafficGroup = trafficGroup
        self.simple_optional_attributes = ['subPath', 'floating', 'inheritedTrafficGroup', 'trafficGroup']
        # Not sure what these two are for, but they don't seem to be needed the tests we have at the moment
        # "addressSource" : "from-user",
        # "unit" : 0,

    def run(self):
        super(CreateSelfipOnBigip, self).run()
        LOG.debug('starting create_selfip_on_bigip')
        payload = SelfIp(name=self.name,
                         partition=self.partition,
                         address=self.address,
                         vlan=self.vlan)

        for attrib in self.simple_optional_attributes:
            if getattr(self, attrib) is not None:
                setattr(payload, attrib, getattr(self, attrib))

        response = self.api.post(SelfIp.URI, payload)

        return response


create_selfip_on_bigiq = None
class CreateSelfipOnBigiq(IcontrolRestCommand):  # @IgnorePep8
    """
    Creates a Self IP in the BIG-IQ's working-config
    @param device_id: the id of BIG-IP on which to create the object
    @param name: name of virtual server to create
    @param address: IP address of node
    @param vlan: path/folder in which to create the node
    @param partition: partition in which to create the object
    @param inheritedTrafficGroup: boolean that sets whether traffic group is inherited from partition/path
    @param trafficGroup: name of traffic group self ip should reference
    @param allowServices: list of service:port mappings
    @param subPath: subPath in which to create the object
    @return: POST response from BIG-IQ (contains object)
    """
    def __init__(self, device_id, name, address, vlan, floating, partition=DEFAULT_BIGIP_PARTITION,
                 inheritedTrafficGroup=None, trafficGroup=None, allowServices=None, subPath=None, *args, **kwargs):
        super(CreateSelfipOnBigiq, self).__init__(*args, **kwargs)
        self.device_id = device_id
        self.name = name
        self.address = address
        self.vlan = vlan
        self.floating = floating
        self.partition = partition
        self.inheritedTrafficGroup = inheritedTrafficGroup
        self.trafficGroup = trafficGroup
        self.allowServices = allowServices
        self.subPath = subPath
        self.simple_optional_attributes = ['inheritedTrafficGroup', 'allowServices', 'subPath']

    def run(self):
        super(CreateSelfipOnBigiq, self).run()
        LOG.debug('starting create_selfip_on_bigiq')
        device_ref = {'link': 'https://localhost' + DeviceResolver.DEVICE_URI % (DEFAULT_CM_ADC_DEVICE_GROUP,
                                                                                 self.device_id)}
        payload = WorkingNetSelfIp(name=self.name,
                                   partition=self.partition,
                                   deviceReference=device_ref,
                                   address=self.address,
                                   floating=self.floating)

        _, vlan_partition, vlan_name = self.vlan.split('/')  # Hopefully no one is silly and uses a vlan with a subPath

        vlans = filter_search_for_item(WorkingNetVlan.URI, 'name', vlan_name, return_top_result=False)
        vlan_link = [x.selfLink for x in vlans if x.deviceReference.id == self.device_id and
                     x.partition == vlan_partition][0]
        payload.vlanReference = {'link': vlan_link}

        if self.trafficGroup:
            traffic_group_link = filter_search_for_item(WorkingNetTrafficGroup.URI, 'name', self.trafficGroup).selfLink
            payload.trafficGroupReference = {'link': traffic_group_link}

        for attrib in self.simple_optional_attributes:
            if getattr(self, attrib) is not None:
                setattr(payload, attrib, getattr(self, attrib))

        response = self.api.post(WorkingNetSelfIp.URI, payload)

        return response

get_bigiq_monitors = None
class GetBigiqMonitors(IcontrolRestCommand):  # @IgnorePep8
    """
    Returns one or more monitors from a BIG-IQ

    THIS IS UNFINISHED.

    @return: dict of monitors {fullPath: selfLink}
    """
    def __init__(self, monitor_fullpath=None, *args, **kwargs):
        super(GetBigiqMonitors, self).__init__(*args, **kwargs)
        self.partition = None
        self.sub_path = None
        self.name = None
        if monitor_fullpath:
            self.partition, self.sub_path, self.name = split_full_path(monitor_fullpath)

    def run(self):
        super(GetBigiqMonitors, self).run()
        if self.partition and self.name:
            uri = '/mgmt/cm/adc-core/working-config/ltm/monitor'  # TODO: Build item URI here. Currently totally broken.
        else:
            uri = "/mgmt/shared/index/config?$filter=kind eq 'cm:adc-core:working-config:ltm:monitor:*'"
        resp = self.api.get(uri)
        # Filter out all of the monitor collections and build a {fullPath: selfLink} dict for all ltm monitors
        monitor_dict = {get_full_path(x): x['selfLink'] for x in resp['items'] if x.get('name')}

        return monitor_dict
