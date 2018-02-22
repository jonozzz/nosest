'''
Created on Dec 11, 2015
This module is the implementation of the Unified Device Discovery for bigiq-mgmt-cm Greenflash v5.0.0+
@author: elarson
'''
import logging
from netaddr import IPAddress
from netaddr import ipv6_full
from f5test.base import Options
from f5test.commands.rest.base import IcontrolRestCommand
from f5test.interfaces.rest.emapi import EmapiResourceError
from f5test.interfaces.rest.emapi.objects.base import CmTask
from f5test.interfaces.rest.emapi.objects.biqmgmtcm.unified_discovery import (DeviceTrust,
                                                                              DeviceDiscovery,
                                                                              DeviceRemoveMgmtAuthority,
                                                                              DeviceRemoveTrust,
                                                                              EstablishTrustException,
                                                                              AddServiceException,
                                                                              ImportServiceException,
                                                                              RemoveServiceException,
                                                                              RemoveTrustException)
from f5test.interfaces.rest.emapi.objects.shared import DeviceResolver
from f5test.interfaces.rest.emapi.objects.system import MachineIdResolver
from f5test.utils.rest import filter_search_for_item
from f5test.utils.wait import (wait, wait_args, StopWait)
# test
from f5test.commands.rest.biqmgmtcm.device import discover_dsc_clusters

LOG = logging.getLogger(__name__)
DEFAULT_DISCOVERY_DELAY = 180
VIPRION_DISCOVERY_DELAY = 300
ESTABLISH_TRUST_TIMEOUT = 360
DISCOVER_TIMEOUT = 300
IMPORT_TIMEOUT = 300
FRAMEWORK_UPDATE_TIMEOUT = 300
REMOVE_SERVICES_TIMEOUT = 60
REMOVE_TRUST_TIMEOUT = 65
HEALTH_CHECK_TIMEOUT = 180

"""
Device groups names. Names used when querying machineid-resolver for group members
Device-trust & device-discovery set these groups.
cm-bigip-AllBigipDevives - Default device group. All bigip's are in this group
cm-access-AllDevices - Access group. All devices disvovered into Access service
cm-adc-core-allDevices - ADC group, all devices discovered into LTM service
cm-asm-allDevices - ASM group, all devices discovered into ASM service
cm-firewall-allDevices - all devices discovered into firewall
cm-security-shared-allDevices - All devices in security-shared, all ASM + Firewall
"""
DEFAULT_CM_DEVICE_GROUP = 'cm-bigip-allBigIpDevices'
DEFAULT_CM_ACCESS_GROUP = 'cm-access-allDevices'
DEFAULT_CM_ACCESS_DEVICE_GROUP = 'cm-access-allBigIpDevices'
DEFAULT_CM_ADC_GROUP = 'cm-adccore-allDevices'
DEFAULT_CM_ADC_DEVICE_GROUP = 'cm-adccore-allbigipDevices'
DEFAULT_CM_ASM_GROUP = 'cm-asm-allDevices'
DEFAULT_CM_ASM_DEVICE_GROUP = "cm-asm-allAsmDevices"
DEFAULT_CM_FIREWALL_GROUP = 'cm-firewall-allDevices'
DEFAULT_CM_FIREWALL_DEVICE_GROUP = "cm-firewall-allFirewallDevices"
DEFAULT_CM_SECURITY_GROUP = 'cm-security-shared-allDevices'
DEFAULT_CM_SECURITY_DEVICE_GROUP = "cm-security-shared-allSharedDevices"
DEFAULT_CM_DNS_GROUP = 'cm-dns-allDevices'
DEFAULT_CM_DNS_DEVICE_GROUP = 'cm-dns-allBigIpDevices'

CM_GLOBAL_ACCESS_NAME = 'access'
CM_GLOBAL_ADC_NAME = 'adc_core'
CM_GLOBAL_ASM_NAME = 'asm'
CM_GLOBAL_FIREWALL_NAME = 'firewall'
CM_GLOBAL_SECURITY_NAME = 'security_shared'
CM_GLOBAL_DNS_NAME = 'dns'

PROPERTIES = 'properties'


get_machine_id = None
class GetMachineId(IcontrolRestCommand):  # @IgnorePep8
    """
    Retrieves Device ID from machineid-resolver. Used to retrieve id for BIG-IP
    to build link string for DeviceDiscovery, DMA & other API's
    @param device: an instance of f5test.interfaces.config.DeviceAccess
    @return: machineId or None
    """
    def __init__(self, device, *args, **kwargs):
        super(GetMachineId, self).__init__(*args, **kwargs)
        self.device = device

    def setup(self):

        resp = self.api.get(MachineIdResolver.URI)
        machine_id = None
        items = resp['items']
        for dev in items:
            if self.device.get_discover_address() == dev.address:
                LOG.debug("Looking for {0} EQ to {1}".format(self.device.get_discover_address(), dev.address))
                machine_id = dev.machineId
                break
        if machine_id is None:
            LOG.warning("No machineid reference found for {0}".format(self.device.get_discover_address()))
        return machine_id


get_discovered_services_list = None
class GetDiscoveredServicesList(IcontrolRestCommand):  # @IgnorePep8
    """
    Queries machineid-resolver and returns a list of discovered module
    for the specified device
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @return: A list of discovered services or empty list
    """
    def __init__(self, device, *args, **kwargs):
        super(GetDiscoveredServicesList, self).__init__(*args, **kwargs)
        self.device = device
        self.resp = None

    def prep(self):
        super(GetDiscoveredServicesList, self).prep()
        # This doesn't work in v5.5.0
        #f = Options(filter="product eq 'BIG-IP' and address eq '%s'" % self.device.get_discover_address())
        f = Options(filter="product eq 'BIG-IP' and deviceUri eq 'https://%s:443'" % self.device.get_discover_address())
        resp = self.api.get(MachineIdResolver.URI, odata_dict=f)
        items = resp['items']
        for item in items:
            LOG.debug("Looking for {0} EQ to {1}".format(self.device.get_discover_address(), item.address))
            if self.device.get_discover_address() == item.address:
                self.resp = item
                break
        if self.resp is None:
            LOG.warning("No machineid reference found for {0}".format(self.device.get_discover_address()))

    def setup(self):
        services_list = []
        if self.resp:
            if DEFAULT_CM_ACCESS_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_ACCESS_NAME)
            if DEFAULT_CM_ADC_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_ADC_NAME)
            if DEFAULT_CM_ASM_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_ASM_NAME)
            if DEFAULT_CM_DNS_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_DNS_NAME)
            if DEFAULT_CM_FIREWALL_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_FIREWALL_NAME),
            if DEFAULT_CM_SECURITY_DEVICE_GROUP in self.resp[PROPERTIES]:
                services_list.append(CM_GLOBAL_SECURITY_NAME)

        return services_list


establish_device_trust = None
class EstablishDeviceTrust(IcontrolRestCommand):  # @IgnorePep8
    """
    Adds BIG-IP to device trust inventory
    POST the device-trust
    wait for status of FINISHED or PENDING ROOT_CREDENTIAL for framework upgrade for all devices in batch
        if PENDING_ROOT_CREDENTIAL, supply root credentials for framework upgrade
    raises EstablishTrustException on failure
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param cluster: an optional string for assigning a security cluster
    @param timeout: Override the default establish device trust timeout value
    @param use_bigiq_sync: True: BIG-IQ will push config to all members of cluster,
                           False: (Default)BIG-IQ will push config of active device to all members of cluster for sync
    @return: None
    """
    def __init__(self, device, cluster=None, timeout=FRAMEWORK_UPDATE_TIMEOUT, use_bigiq_sync=False, *args, **kwargs):
        super(EstablishDeviceTrust, self).__init__(*args, **kwargs)
        self.device = device
        self.cluster = cluster
        self.use_bigiq_sync = use_bigiq_sync
        self.timeout = timeout
        self.id = None

    def framework_update(self):
        LOG.info("Updating device framework for {0}".format(self.device.get_discover_address()))
        payload = DeviceTrust(rootUser=self.device.get_root_creds().username,
                              rootPassword=self.device.get_root_creds().password,
                              confirmFrameworkUpgrade=True,
                              status='STARTED')
        return self.api.patch(DeviceTrust.ITEM_URI % self.id, payload=payload)

    def setup(self):
        LOG.info("establish device trust with {0}".format(self.device.get_discover_address()))
        payload = DeviceTrust(address=self.device.get_discover_address(),
                              userName=self.device.get_admin_creds().username,
                              password=self.device.get_admin_creds().password)
        if self.cluster is not None:
            payload.clusterName = self.cluster
            payload.useBigiqSync = self.use_bigiq_sync
        resp = self.api.post(DeviceTrust.URI, payload=payload)
        self.id = resp.id

        if resp.status not in DeviceTrust.PENDING_STATUSES:
            raise EstablishTrustException("Failed to start Device Trust for {0}".format(self.device.get_discover_address()),
                                          address=self.device.get_discover_address())

        def is_trust_done_yet():
            resp = self.api.get(DeviceTrust.ITEM_URI % self.id)
            if resp.status in DeviceTrust.FINAL_STATUSES and resp.currentStep == DeviceTrust.UPDATE_STEP:
                resp = self.framework_update()
            return resp

        resp = wait(is_trust_done_yet,
                    condition=lambda x: x.status in DeviceTrust.FINAL_STATUSES,
                    timeout=self.timeout,
                    interval=5,
                    timeout_message="device trust not complete after {0}s.")
        if resp.status == DeviceTrust.FAIL_STATE:
                    raise EstablishTrustException("Device Trust FAILED for {0}".format(self.device.get_discover_address()),
                                                  address=self.device.get_discover_address())


add_services = None
class AddServices(IcontrolRestCommand):  # @IgnorePep8
    """
    Adds services for a trusted BIGIP
    raises AddServiceException on failure
    @param device: An instance of f5test.interfaces.config.DeviceAccess
    @param services_list: a list of services DeviceDiscovery.SERVICES
    @param timeout: Override default DISCOVER_TIMEOUT for add services
    @return: list of AttrDict of service: status, i.e. 'adc_core': 'DISCOVERED'
    """
    def __init__(self, device, services_list=None, timeout=DISCOVER_TIMEOUT, *args, **kwargs):
        super(AddServices, self).__init__(*args, **kwargs)
        self.device = device
        self.services_list = services_list[:] if isinstance(services_list, list) else []
        self.timeout = timeout

    def set_uri(self, item):
        self.uri = DeviceDiscovery.ITEM_URI % item.id

    def prep(self):
        super(AddServices, self).prep()
        machineid = get_machine_id(self.device, ifc=self.ifc)
        # asm and firewall require security_shared, add to list
        if ((CM_GLOBAL_ASM_NAME in self.services_list or
                CM_GLOBAL_FIREWALL_NAME in self.services_list) and
                CM_GLOBAL_SECURITY_NAME not in self.services_list):
            self.services_list.append(CM_GLOBAL_SECURITY_NAME)
        # locate existing task
        self.discover_task = filter_search_for_item(base_uri=DeviceDiscovery.URI,
                                                    search_key='deviceReference/link',
                                                    search_value='*' + machineid,
                                                    ifc=self.ifc)
        self.device_reference = {'link': 'https://localhost' + MachineIdResolver.ITEM_URI % machineid}

        if self.services_list:
            bad_names = set(self.services_list) - set(DeviceDiscovery.SERVICES)
            if bad_names:
                raise AddServiceException("{0} Invalid service(s) {1}".format(self.device.get_discover_address(), bad_names),
                                          address=self.device.get_discover_address(), service=bad_names)

    def setup(self):
        LOG.info("device discovery on {0}".format(str(self.device.get_discover_address())))
        temp_modules = []
        if self.services_list:
            for service in self.services_list:
                temp_modules.append({'module': service})
            payload = DeviceDiscovery(moduleList=temp_modules)
            if self.discover_task:
                LOG.debug("patching existing discover task")
                payload.status = 'STARTED'
                resp = self.api.patch(DeviceDiscovery.ITEM_URI % self.discover_task.id, payload=payload)
            else:
                LOG.debug("posting new discover task")
                payload.deviceReference = self.device_reference
                resp = self.api.post(DeviceDiscovery.URI, payload=payload)
            self.set_uri(resp)
            resp = wait_args(self.api.get, func_args=[self.uri],
                             condition=lambda x: x.status in DeviceDiscovery.FINAL_STATUSES,
                             interval=10,
                             timeout=self.timeout,
                             timeout_message='Discovery did not complete in {0} seconds')
            if resp.status == DeviceDiscovery.FAIL_STATE:
                raise AddServiceException("Device Discovery failed for {0}: {1}".format(self.device.get_discover_address(),
                                                                                        resp.errorMessage),
                                          address=self.device.get_discover_address(), service=self.services_list)
        else:
            LOG.info("empty services list")


remove_services = None
class RemoveServices(IcontrolRestCommand):  # @IgnorePep8
    """ Removes service from a discovered BIGIP
        Removes services in moduleList, or all if moduleList is empty
        raises RemoveServiceException on error
    @param devices: an f5test.interface.config.DeviceAddress instance
    @param moduleList: a list of services must be in DeviceDiscovery.MODULES
    @param timeout: Override the default remove services timeout value
    @return: None
    """
    def __init__(self, device, services_list=None, timeout=REMOVE_SERVICES_TIMEOUT, *args, **kwargs):
        super(RemoveServices, self).__init__(*args, **kwargs)
        self.device = device
        self.services_list = services_list or []
        self.timeout = timeout

    def prep(self):
        super(RemoveServices, self).prep()
        self.machineid = get_machine_id(self.device, ifc=self.ifc)
        self.current_modules = get_discovered_services_list(self.device, ifc=self.ifc)

    def set_uri(self, taskid):
        self.uri = DeviceRemoveMgmtAuthority.ITEM_URI % taskid

    def setup(self):

        remove_modules = []
        if self.services_list:
            for module in self.services_list:
                remove_modules.append({'module': module})
        else:
            for module in self.current_modules:
                remove_modules.append({"module": module})
        if remove_modules:
            LOG.info("removing services {0} for {1}".format(remove_modules, self.device.get_discover_address()))
            payload = DeviceRemoveMgmtAuthority(deviceReference={'link': 'https://localhost' + MachineIdResolver.ITEM_URI % self.machineid},
                                                moduleList=remove_modules)
            resp = self.api.post(DeviceRemoveMgmtAuthority.URI, payload=payload)
            self.set_uri(resp.id)
            resp = wait_args(self.api.get, func_args=[self.uri],
                             condition=lambda x: x.status in DeviceRemoveMgmtAuthority.FINAL_STATUSES,
                             timeout=self.timeout,
                             timeout_message='Remove Management Authority did not complete in {0} seconds')
            if resp.status == DeviceRemoveMgmtAuthority.FAIL_STATE:
                raise RemoveServiceException("Remove Mgmt Authority failed on {0} for services {1} resp:{2}".format(self.device.get_discover_address(),
                                                                                                                    remove_modules, resp),
                                             address=self.device.get_discover_address(), service=remove_modules)


remove_device_trust = None
class RemoveDeviceTrust(IcontrolRestCommand):  # @IgnorePep8
    """
    Removes big-ip from device trust
    All services must be removed before removing trust
    raises RemoveTrustException on error
    @param device: A list of f5test.interfaces.config.DeviceAccess instances.
    @param timeout: Override the default remove device trust timeout value
    @return: None
    """
    def __init__(self, device, timeout=REMOVE_TRUST_TIMEOUT, *args, **kwargs):
        super(RemoveDeviceTrust, self).__init__(*args, **kwargs)
        self.device = device
        self.timeout = timeout

    def prep(self):
        super(RemoveDeviceTrust, self).prep()
        self.machineid = get_machine_id(self.device, ifc=self.ifc)

    def set_uri(self, taskid):
        self.uri = DeviceRemoveTrust.ITEM_URI % taskid

    def setup(self):
        if self.machineid:
            LOG.info("remove device trust for {0}".format(str(self.device.get_discover_address())))
            payload = DeviceRemoveTrust(deviceReference={'link': 'https://localhost' + MachineIdResolver.ITEM_URI % self.machineid})
            resp = self.api.post(DeviceRemoveTrust.URI, payload=payload)
            self.set_uri(resp.id)
            resp = wait_args(self.api.get, func_args=[self.uri],
                             condition=lambda x: x.status in DeviceRemoveTrust.FINAL_STATUSES,
                             timeout=self.timeout,
                             timeout_message='Failed to remove device trust in {0} sec')

            if resp.status == DeviceRemoveTrust.FAIL_STATE:
                raise RemoveTrustException("Failed to remove trust for {0} resp:{1}".format(self.device.get_discover_address(), resp),
                                           address=self.device.get_discover_address())


import_service_config = None
class ImportServiceConfig(IcontrolRestCommand):  # @IgnorePep8
    """
    Perform the configuration import function for access, adc_core,
    asm, and firewall emulating the import button on the UI
    raises ImportServiceException on failure
    Note: access currently skipped, perform using f5test/commands/rest/access.py create_access_group()
    @param device: an f5test.interfaces.config.DeviceAccess instance
    @param service: Text string representing the service to be imported
    @param from_bigiq: Boolean flag for conflict resolution
    @param cluster: Cluster name (firewall, as entered in Add Device dialog)
    @param snapshot_working_config: Snapshot working config, Same as Import checkbox on UI
    @param timeout: override default timeout value
    @param bypass_validation: If true, then add a parameter to the DMA call
    to tell it to NOT run ADC validations (used for Scale testing).  Default
    is False.
    @return: None
    """
    def __init__(self, device, service, from_bigiq=True, cluster=None, use_bigiq_sync=False,
                 snapshot_working_config=False, timeout=IMPORT_TIMEOUT,
                 bypass_validation=False, *args, **kwargs):
        super(ImportServiceConfig, self).__init__(*args, **kwargs)
        self.device = device
        self.service = service
        self.from_bigiq = from_bigiq
        self.cluster = cluster  # firewall
        self.snapshot_working_config = snapshot_working_config
        self.timeout = timeout
        self.bypass_validation = bypass_validation

    def set_uri(self):
        path = 'adc-core' if self.service == CM_GLOBAL_ADC_NAME else self.service
        self.uri = CmTask.BASE_URI % (path, 'declare-mgmt-authority')

    def prep(self):
        super(ImportServiceConfig, self).prep()
        assert self.service, "ImportConfig.prep(): A service must be specified for import"

        if self.service not in set(DeviceDiscovery.SERVICES):
            raise ImportServiceException("Invalid service(s) for {0}: {1}".format(self.device.get_discover_address(), self.service),
                                         address=self.device.get_discover_address(), service=self.service)
        self.machineid = get_machine_id(self.device, ifc=self.ifc)
        self.set_uri()
        if self.service == CM_GLOBAL_ASM_NAME or self.service == CM_GLOBAL_FIREWALL_NAME:
            self.create_child_tasks = True
        else:
            self.create_child_tasks = False

    def setup(self):
        if self.service == CM_GLOBAL_ACCESS_NAME:
            # access has their own solution
            return

        LOG.debug('ImportServiceConfig.setup()')

        LOG.info('Finding existing import task...')
        device_reference_link = 'https://localhost' + MachineIdResolver.URI + '/' + self.machineid
        old_task = filter_search_for_item(base_uri=self.uri,
                                          search_key='deviceReference/link',
                                          search_value=device_reference_link,
                                          ifc=self.ifc)
        if old_task:
            LOG.info('Deleting existing import task...')
            self.api.delete("{0}/{1}".format(self.uri, old_task.id))

        if self.from_bigiq:
            resolution = 'USE_BIGIQ'
        else:
            resolution = 'USE_BIGIP'

        LOG.info("import {0} config for {1}...".format(self.service, self.device.get_discover_address()))
        dma = CmTask(createChildTask=self.create_child_tasks,
                     skipDiscovery=True,
                     deviceReference={'link': 'https://localhost' + MachineIdResolver.ITEM_URI % self.machineid},
                     snapshotWorkingConfig=self.snapshot_working_config)
        if self.cluster:
            dma.clusterName = self.cluster
        if self.bypass_validation:
            dma.validationBypassMode = "BYPASS_ALL"
        task = self.api.post(self.uri, payload=dma)

        def wait_for_conflicts():
            resp = self.api.get(task.selfLink)
            if (resp.status not in ('STARTED',) and
                    resp.currentStep in ('PENDING_CONFLICTS', 'PENDING_CHILD_CONFLICTS')):
                LOG.info('Conflicts detected, setting resolution: %s' % resolution)
                payload = Options(status='STARTED',
                                  conflicts=resp.conflicts[:])
                for conflict in payload.conflicts:
                    conflict.resolution = resolution
                resp = self.api.patch(task.selfLink, payload=payload)
            return resp
        # emulate CmTask Wait without the babbling
        wait(wait_for_conflicts, timeout=self.timeout, interval=2,
             condition=lambda x: x.status != 'CREATED',
             timeout_message="DMA task did not create in {0} seconds")
        resp = wait(wait_for_conflicts, timeout=self.timeout, interval=3,
                    condition=lambda x: x.status != 'STARTED',
                    timeout_message="DMA task did not complete in {0} seconds")
        if resp.status == dma.FAIL_STATE:
            raise ImportServiceException("{0} import config for {1} Failed resp:{2.errorMessage}".format(self.service,
                                                                                            self.device.get_discover_address(),
                                                                                            resp),
                                         address=self.device.get_discover_address(), service=self.service)


discover = None
class Discover(IcontrolRestCommand):  # @IgnorePep8
    """
    Establish device trust and discover BIG-IP's into specified modules
    Operations performed according following table:

    services_list | refresh_config | import_config || TRUST | Discover | Import | Re-Discover | Re-Import
    ===============================================||===================================================
       FALSE      |     FALSE      |    FALSE      ||   X   |          |        |             |
    -----------------------------------------------||---------------------------------------------------
       TRUE       |     FALSE      |    FALSE      ||   X   |    X     |        |             |
    -----------------------------------------------||---------------------------------------------------
       TRUE       |     TRUE       |    FALSE      ||   X   |    X     |        |     X       |
    -----------------------------------------------||---------------------------------------------------
       TRUE       |     FALSE      |    TRUE       ||   X   |    X     |   X    |             |
    -----------------------------------------------||---------------------------------------------------
       TRUE       |     TRUE       |    TRUE       ||   X   |    X     |   X    |     X       |    X

    1. Trust only performed if device trust does not exist with BIG-IP
    2. Omitting a services list renders refresh_config and import_config false
    3. Services_list FALSE = empty, TRUE = value(s) assigned

    @param devices: An iterable container of f5test.interfaces.config.DeviceAccess instances.
    @param services_list: list of services to add BIG-IP, must be in DeviceDiscovery.SERVICES
    @param cluster: Name of a security cluster to add devices to
    @param use_bigiq_sync: True: BIG-IQ will push config to all members of cluster,
                           False: (Default)BIG-IQ will push config of active device to all members of cluster for sync
    @param snapshot_working_config: Performs snapshot of working config before import
    @param refresh_config: Perform a re-discovery if true
    @param import_config: Perform the import on the Discovered modules
    @param trust_timeout: Override the default establish device trust timeout value.
    @param discover_timeout: Override the default discovery timeout
    @param import_timeout: Override the default import (dma) timeout
    @param bypass_validation: If true, then add a parameter to the DMA call
    in import config to tell it to NOT run ADC validations (used for Scale
    testing).  Default is False.
    @param skip_bigip_cluster_discovery: If True, then don't do the BIG-IP
    Cluster discovery step, to save time in cases where you either don't want
    clusters to be discovered or you know that there are no clusters to
    discover.  Default is False.
    @param wait_for_health_stats: If True, then wait for the BIG-IP's health
    stats to come back before completing the discovery.  If False, don't wait
    for this to complete.  Default is True.
    @return: device-resolver inventory of cm-bigip-allBigipDevices
    """
    def __init__(self, devices, services_list=None, cluster=None, use_bigiq_sync=False,
                 snapshot_working_config=False, refresh_config=True, import_config=True,
                 trust_timeout=None, discover_timeout=None,
                 import_timeout=None, bypass_validation=False,
                 skip_bigip_cluster_discovery=False, import_from_bigiq=True,
                 wait_for_health_stats=True, *args, **kwargs):
        super(Discover, self).__init__(*args, **kwargs)
        self.devices = list(devices)
        services_list = services_list or []
        self.services_list = [services_list] if not isinstance(services_list, list) else services_list
        self.cluster = cluster
        self.refresh_config = refresh_config
        self.import_config = import_config
        self.import_from_bigiq = import_from_bigiq
        self.use_bigiq_sync = use_bigiq_sync
        self.snapshot_working_config = snapshot_working_config
        self.trust_timeout = trust_timeout or kwargs.get('timeout', ESTABLISH_TRUST_TIMEOUT)
        self.discover_timeout = discover_timeout or kwargs.get('timeout', DISCOVER_TIMEOUT)
        self.import_timeout = import_timeout or kwargs.get('timeout', IMPORT_TIMEOUT)
        self.bypass_validation = bypass_validation
        self.skip_bigip_cluster_discovery = skip_bigip_cluster_discovery
        self.wait_for_health_stats = wait_for_health_stats

    def prep(self):
        super(Discover, self).prep()
        self.uri = DeviceResolver.DEVICES_URI % DEFAULT_CM_DEVICE_GROUP
        LOG.info('Waiting for REST framework to come up...')

        def is_up(*args):
            try:
                return self.api.get(*args)
            except EmapiResourceError, e:
                if 'Authorization failed' in e.msg:
                    raise StopWait(e)
                raise
        self.resp = wait_args(is_up, func_args=[self.uri],
                              timeout=self.discover_timeout)

        if not self.services_list:
            self.import_config = False

    def wait_for_availability(self, resource):
        stats_link = resource.selfLink + '/stats'
        return wait_args(self.api.get, func_args=[stats_link],
                         condition=lambda x: x.entries.get('health.summary.available', {}).get('value') == 1,
                         progress_cb=lambda x: 'Pending health check...',
                         timeout=HEALTH_CHECK_TIMEOUT,
                         timeout_message="Object %s not available after {0} seconds" % resource.selfLink)

    def import_configuration(self, device, services_to_import):
        if services_to_import:
            # sort adc_core to first in list
            if CM_GLOBAL_ADC_NAME in services_to_import:
                if services_to_import.index(CM_GLOBAL_ADC_NAME) != 0:
                    services_to_import.pop(services_to_import.index(CM_GLOBAL_ADC_NAME))
                    services_to_import.insert(0, CM_GLOBAL_ADC_NAME)
            for service in services_to_import:
                import_service_config(device, service,
                                      cluster=self.cluster,
                                      from_bigiq=self.import_from_bigiq,
                                      snapshot_working_config=self.snapshot_working_config,
                                      timeout=self.import_timeout,
                                      bypass_validation=self.bypass_validation,
                                      ifc=self.ifc)

    def completed(self, device):
        machineid = get_machine_id(device, ifc=self.ifc)
        ret = self.api.get(DeviceResolver.DEVICE_URI % (DEFAULT_CM_DEVICE_GROUP, machineid))
        assert ret.state in ['ACTIVE'], \
            'Discovery of {0} failed: {1}:{2}'.format(device.get_discover_address(), ret.state,
                                                      ret.errors)

        if self.wait_for_health_stats:
            LOG.info('Waiting on device health check...')
            self.wait_for_availability(ret)

    def setup(self):
        LOG.info("Discover bigip's in harness")

        for device in self.devices:
            device.discover_address = IPAddress(device.get_discover_address()).format(ipv6_full)

        inventory = dict([(IPAddress(x.address), x) for x in self.resp['items']])
        harness = dict([(IPAddress(x.get_discover_address()), x) for x in self.devices])

        for address in set(inventory) - set(harness):
            inventory.pop(address)

        inventory_active_set = set([x for x in inventory if inventory[x].state == 'ACTIVE'])
        not_active_set = set(inventory) - inventory_active_set
        for dev in not_active_set:
            LOG.error("device {0} is already in BIGIQ inventory with state {1} ".format(dev.IPAddress, dev.state))

        self.v = self.ifc.version
        assert self.v >= 'bigiq 5.0', (
            "Unified Discovery for use BIG-IQ 5.0 and above")

        for device in self.devices:
            # Only perform trust on undiscovered devices
            if IPAddress(device.get_discover_address()) in (set(harness) - inventory_active_set):
                establish_device_trust(device, cluster=self.cluster,
                                       use_bigiq_sync=self.use_bigiq_sync,
                                       timeout=self.trust_timeout,
                                       ifc=self.ifc)
            if self.services_list:
                current_modules = get_discovered_services_list(device,
                                                               ifc=self.ifc)
                services_to_add = []
                if self.refresh_config:
                    services_to_add = self.services_list[:]
                else:
                    services_to_add = list(set(self.services_list) - set(current_modules))
                add_services(device, services_to_add, timeout=self.discover_timeout,
                             ifc=self.ifc)
                if self.import_config:
                    self.import_configuration(device, services_to_add[:])
            self.completed(device)

        if self.skip_bigip_cluster_discovery is False:
            """
            Import DSC Clusters
            """
            LOG.info("Device Discovery complete - Checking for DSC Clusters")
            discover_dsc_clusters(ifc=self.ifc)

        return self.post_discovery_steps()

    def post_discovery_steps(self):
        """ Extract all devices self.devices from the device-resolver inventory and return """
        resp = self.api.get(DeviceResolver.DEVICES_URI % DEFAULT_CM_DEVICE_GROUP)
        inventory = {IPAddress(x.address): x for x in resp['items']}
        return {x: inventory[IPAddress(x.get_discover_address())] for x in self.devices}


delete = None
class Delete(IcontrolRestCommand):  # @IgnorePep8
    """
    Unmanage services from all devices and remove device trust
    @param devices: An iterable container of f5test.interfaces.common.DeviceAccess instances
    @param remove_services_timeout: Override default remove services timeout
    @param remove_trust_timeout: Override default remove trust timeout
    @return: None
    """
    def __init__(self, devices, remove_services_timeout=REMOVE_SERVICES_TIMEOUT,
                 remove_trust_timeout=REMOVE_TRUST_TIMEOUT, *args, **kwargs):
        super(Delete, self).__init__(*args, **kwargs)
        self.devices = list(devices)
        self.remove_services_timeout = remove_services_timeout
        self.remove_trust_timeout = remove_trust_timeout

    def setup(self):
        LOG.info("Removing all devices from BIG-IQ")
        for device in self.devices:
            remove_services(device, timeout=self.remove_services_timeout,
                            ifc=self.ifc)
            remove_device_trust(device, timeout=self.remove_trust_timeout,
                                ifc=self.ifc)
