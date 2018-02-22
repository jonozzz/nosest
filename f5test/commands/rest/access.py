'''
Created on Apr 29, 2015

@author: ivanitskiy
'''
import logging
import socket

from f5test.commands.rest.biqmgmtcm.system import (Discover,
                                                   PROPERTIES,
                                                   get_machine_id,
                                                   HEALTH_CHECK_TIMEOUT,
                                                   import_service_config,
                                                   DEFAULT_CM_ADC_DEVICE_GROUP,
                                                   DEFAULT_CM_ACCESS_DEVICE_GROUP,
                                                   CM_GLOBAL_ACCESS_NAME,
                                                   CM_GLOBAL_ADC_NAME)
from f5test.interfaces.rest.emapi.objects.base import TaskError
from f5test.interfaces.rest.emapi.objects.system import MachineIdResolver
from f5test.utils.wait import wait_args
from ...base import AttrDict
from ...commands.base import Command
from ...commands.rest.device import DEFAULT_ACCESS_GROUP, DEFAULT_ALL_GROUPS
from ...interfaces.rest.emapi.objects import access
from ...interfaces.rest.emapi.objects.shared import DeviceResolver
from .base import IcontrolRestCommand
from .device_group import GetGroupByName


LOG = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 60 * 9
ACCESS_EVENT_LOG_LISTENER_PORT = 9999


def is_group_exist(rsapi, group_name):
    retval = False
    uri = DeviceResolver.URI
    rest_access_group = rsapi.get(uri)
    for access_group in rest_access_group.get("items", []):
        if group_name in access_group["groupName"]:
            retval = True
            break
    return retval


add_devices_cluster = None
class AddDevicesCluster(IcontrolRestCommand):  # @IgnorePep8
    """
    Type: POST
    @param devices: devices to add into group
    @type list: list of instances of f5test.interfaces.config.DeviceAccess

    @param cluster_name
    @type cluster name string
    """
    task = access.AddDeviceClusterTask

    def __init__(self, devices, cluster_name, *args, **kwargs):
        super(AddDevicesCluster, self).__init__(*args, **kwargs)
        self.devices = devices
        self.cluster_name = cluster_name

    def setup(self):
        """Add a devices to BIG-IQ cluster"""
        uri = DeviceResolver.DEVICES_URI % DEFAULT_ALL_GROUPS
        rest_devices = self.api.get(uri)
        for device in self.devices:
            device_address = device.get_address()
            for x in rest_devices["items"]:
                if x.address == device_address:
                    payload = self.task()
                    uri = access.AddDeviceClusterTask.URI
                    payload.clusterName = self.cluster_name
                    payload.deviceReference.link = x.selfLink
                    LOG.info("Add device '{0}' to cluster '{1}".format(device_address,
                                                                       self.cluster_name))
                    task = self.api.post(uri, payload=payload)
                    self.task_self_link = task.selfLink
                    payload.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                                 timeout_message="'bigip-cluster-mgmt' task did not complete")
                    break


create_access_group = None
class CreateAccessGroup(IcontrolRestCommand):  # @IgnorePep8
    """
    Type: POST
    @param group_name: group name, which should be unique, only letters and numbers
    @type group_name: string

    @param device: device to add into group
    @type instance of f5test.interfaces.config.DeviceAccess

    @return: the task status
    @rtype: attr dict json
    """
    task = access.AccessGroupTask

    def __init__(self, group_name, device, cluster_name=None,
                 *args, **kwargs):
        super(CreateAccessGroup, self).__init__(*args, **kwargs)
        self.group_name = group_name
        self.device = device
        self.task_self_link = None
        self.cluster_name = cluster_name

    def prep(self):
        super(CreateAccessGroup, self).prep()
        # we need to re-discover Access and adc_core prior to create an access group
        discover_access([self.device], refresh_config=True)

    def setup(self):
        """Add a device to access group"""
        uri = DeviceResolver.DEVICES_URI % DEFAULT_ACCESS_GROUP
        rest_devices = self.api.get(uri)
        device_reference = AttrDict()
        device_address = self.device.get_address()
        retst_resp = None
        for x in rest_devices["items"]:
            if x.address == device_address:
                retst_resp = x
                break
        if retst_resp is not None:
            device_reference = retst_resp.selfLink
        dma = self.task()
        # let's check the stats of the devices
        # Task will fail, if devices are not healthy
        check_device_availability([self.device])
        dma.properties["cm:access:access-group-name"] = self.group_name
        dma.deviceReference.link = device_reference
        dma.clusterName = self.cluster_name

        uri = access.AccessGroupTask.URI
        LOG.info("Creating access group '{0}' with device: '{1}".format(self.group_name, device_reference))
        task = self.api.post(uri, payload=dma)
        self.task_self_link = task.selfLink
        return dma.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                        timeout_message="Access 'declare-mgmt-authority' task did not complete in {0} seconds")


change_source_device_in_access_group = None
class ChangeSourceDeviceInAccessGroup(IcontrolRestCommand):  # @IgnorePep8
    """
    Type: POST, PATCH
    @param group_name: group name, which should be unique, only letters and numbers
    @type group_name: string

    @param source_device: a new source device (member of that group)
    @type instance of f5test.interfaces.config.DeviceAccess

    @return: the task status
    @rtype: attr dict json
    """
    task = access.ChangeSourceDeviceInAccessGroupTask

    def __init__(self, group_name, devices, source_device,
                 *args, **kwargs):
        super(ChangeSourceDeviceInAccessGroup, self).__init__(*args, **kwargs)
        self.group_name = group_name
        self.source_device = source_device
        self.task_self_link = None

    def setup(self):
        pass


reimport_source_device_in_access_group = None
class ReimportSourceDeviceInAccessGroup(IcontrolRestCommand):  # @IgnorePep8
    """
    Type: POST, PATCH
    @param group_name: group name, which should be unique, only letters and numbers
    @type group_name: string

    @return: the task status
    @rtype: attr dict json
    """
    task = access.ReimportSourceDeviceInAccessGroupTask

    def resolve_conflicts(self, resp):
        result = resp
        if resp.currentStep == "PENDING_CONFLICTS" and resp.status == "FINISHED":
            LOG.info("The re-import task requires resolving conflicts...")
            mgmt_summary_resp = self.api.get(resp.mgmtAuthoritySummaryReference.link)
            dma_task_ref_link = None
            for item in mgmt_summary_resp.devices:
                if item.dmaTaskReference is not None and item.currentStep == "PENDING_CONFLICTS":
                    dma_task_ref_link = item.dmaTaskReference.link
                    break

            if dma_task_ref_link is not None:
                payload = AttrDict()
                payload.dmaTaskReference = item.dmaTaskReference
                payload.status = "STARTED"
                payload.acceptConflicts = True

                task = self.api.patch(resp.selfLink, payload=payload)
                reimport_task = self.task()
                patched_task = reimport_task.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                                                  timeout_message="Task: 'mgmt-authority'; actionType: REIMPORT_SOURCE_DEVICE did not complete in {0} seconds")
                result = self.resolve_conflicts(patched_task)

            else:
                raise TaskError("Could not find dmaTaskReference in response\n%s" % resp)
        elif resp.currentStep == "COMPLETE" and resp.status == "FINISHED":
            LOG.info("Conflicts were resolved. re-import task completed.")
            return result
        else:
            LOG.debug("Current response for mgmt-authority task:\n %s" % resp)
            raise TaskError("Could not determine state of the task...")

    def __init__(self, group_name,
                 *args, **kwargs):
        super(ReimportSourceDeviceInAccessGroup, self).__init__(*args, **kwargs)
        self.group_name = group_name
        self.task_self_link = None

    def setup(self):
        # Get source device uuid
        uri = DeviceResolver.DEVICES_URI % self.group_name
        odata_dict = AttrDict(filter="'properties/cm:access:source-device' eq 'true'")
        rest_access_config = self.api.get(uri, odata_dict=odata_dict)
        source_ref = "https://localhost" + DeviceResolver.DEVICE_URI % (DEFAULT_ACCESS_GROUP, rest_access_config["items"][0].uuid)
        reimport_task = self.task()
        reimport_task.groupName = self.group_name
        reimport_task.sourceDevice.deviceReference.link = source_ref
        LOG.info("Re-importing source device for access group '{0}'".format(self.group_name))
        task = self.api.post(reimport_task.URI, payload=reimport_task)
        resp = reimport_task.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                                  timeout_message="Task: 'mgmt-authority'; actionType: REIMPORT_SOURCE_DEVICE did not complete in {0} seconds")
        result = self.resolve_conflicts(resp)
        return result

get_access_groups = None
class GetAccessGroups(IcontrolRestCommand):  # @IgnorePep8
    pass


get_access_group_by_name = None
class GetAccessGroupByName(GetGroupByName):  # @IgnorePep8
    pass


delete_by_display_name = None
class DeleteByDisplayName(IcontrolRestCommand):  # @IgnorePep8
    pass


delete_access_group_by_name = None
class DeleteAccessGroupByName(IcontrolRestCommand):  # @IgnorePep8

    def __init__(self, group_name=None, *args, **kwargs):
        super(DeleteAccessGroupByName, self).__init__(*args, **kwargs)
        self.group_name = group_name

    def setup(self):
        """Rest API to delete Access Group"""
        retval = None
        group = get_access_group_by_name(self.group_name)
        if group is not None:
            if self.ifc.version > 'bigiq 5.2.0':
                rma = access.RemoveGroupAccessGroupTask()
                rma.deviceGroupReference.link = group.selfLink
            else:
                rma = access.DeletingAccessGroupTask()
                rma.groupName = self.group_name

            LOG.info("Removing access group '%s'" % self.group_name)
            task = self.api.post(rma.URI, payload=rma)
            retval = rma.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                            timeout_message="Access delete access group ('mgmt-authority' task) did not complete in {0} seconds")
        return retval


delete_all_access_groups = None
class DeleteAllAccessGroups(IcontrolRestCommand):  # @IgnorePep8

    def setup(self):
        """Rest API command to delete All Access Groups"""
        uri = DeviceResolver.URI
        if self.ifc.version > 'bigiq 5.2.0':
            odata_dict = AttrDict(expand="devicesReference",
                                  filter="'properties/cm:access:access_group' eq 'true'")
        else:
            odata_dict = AttrDict(expand="devicesReference",
                                  filter="'properties/cm:access:config_group' eq 'true'")
        rest_access_config = self.api.get(uri, odata_dict=odata_dict)
        LOG.debug("Deleting already created access groups")
        for x in rest_access_config["items"]:
            group_name = x.groupName
            delete_access_group_by_name(group_name=group_name)


create_access_config_deployment = None
class CreateAccessConfigDeployment(IcontrolRestCommand):  # @IgnorePep8
    """Creates a new deployment
    Type: POST

    @param group_name: group name, which should be unique, only letters and numbers
    @type group_name: string

    @param devices: list devices to deploy to
    @type list: list of instances of f5test.interfaces.config.DeviceAccess

    @param options: deployment options
    @type AttrDict
            if options is None, then it will use default one:

            options.skipDistribution = False or True
                - False it deploys the configuration to devices.
                - True, it only evaluates the configuration.
            options.skipVerifyConfig = False or True
                -
                -
            options.properties = AttrDict()
            options.properties["cm:access:post-deploy-config:apply-policies"] = True or False
                - if below property is set to true then policies will be applied
                  after successfully deploying. If no properties are specified
                  default behavior is policies will be applied. If property value
                  is set to false policies will not be applied.

            options.properties["cm:access:post-deploy-config:kill-sessions"] = False

    @return: the task status
    @rtype: attr dict json
    """
    task = access.DeployConfigurationTask

    def __init__(self, group_name, devices, options=AttrDict(), *args, **kwargs):
        super(CreateAccessConfigDeployment, self).__init__(*args, **kwargs)
        self.group_name = group_name
        self.devices = devices
        self.options = AttrDict()
        if not options:
            options = AttrDict()
            options.skipDistribution = True
            options.skipVerifyConfig = True
            options.properties = AttrDict()
            options.properties["cm:access:post-deploy-config:apply-policies"] = True
            options.properties["cm:access:post-deploy-config:kill-sessions"] = False
        self.options.update(options)

    def setup(self):
        """add a device to access group"""
        group = get_access_group_by_name(self.group_name)
        rest_devices = self.api.get(DeviceResolver.DEVICES_URI % DEFAULT_ACCESS_GROUP)
        device_references = []
        for device in self.devices:
            device_address = device.get_address()
            retst_resp = None
            for x in rest_devices["items"]:
                if x.address == device_address:
                    retst_resp = x
                    break
            if retst_resp is not None:
                device_references.append({"link": retst_resp.selfLink})

        deployment = self.task()
        deployment.deviceGroupReference.link = group.selfLink
        deployment.deviceReferences = device_references
        deployment.update(self.options)
        LOG.info("Creating a new Access deployment '%s'..." % deployment.name)
        task = self.api.post(self.task.URI, payload=deployment)
        self.task_self_link = task.selfLink
        return deployment.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                               timeout_message="Access 'deploy-configuration' task did not complete in {0} seconds")


send_event_log = None
class SendEventLog(Command):  # @IgnorePep8
    """Sends log messages to device (big-iq)
    Sends data the event log listener port
    @param host: device ip or hostname to connect with
    @type host: string

    @param payload: Data to send
    @type payload: string

    @param tcp_port: tcp port
    @type tcp_port: integer, by default ACCESS_EVENT_LOG_LISTENER_PORT (9999)
    """
    def __init__(self, host, payload, tcp_port=ACCESS_EVENT_LOG_LISTENER_PORT,
                 *args, **kwargs):
        self.sock = None
        self.host = host
        self.port = tcp_port
        self.payload = payload

    def prep(self):
        super(SendEventLog, self).prep()
        # open TCP connection
        LOG.debug("Opening tcp socket to address: %s port: %s" % (self.host, self.port))
        self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)

#         LOG.info(self.host self.port, self.payload)

        self.sock.connect((self.host, self.port))

    def send_data(self, msg):
        totalsent = 0
        msglen = len(msg)
        while totalsent < msglen:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            totalsent = totalsent + sent

    def setup(self):
        # send event log data
        LOG.debug("Sending event log to %s:%s\n%s" % (self.host, self.port, self.payload))
        self.send_data(self.payload)
        LOG.debug("Successfully sent event log")

    def cleanup(self):
        # close TCP connection
        self.sock.close()
        super(SendEventLog, self).cleanup()


discover_access = None
class DiscoverAccess(Discover):  # @IgnorePep8
    """Establish device trust and discover BIG-IP's into specified adc_core and access modules
    This class implements some additional aspects to discover access devices:
        discover: adc_core and access services
        import: adc_core;

    @param devices: An iterable container of f5test.interfaces.config.DeviceAccess instances.
    @param services_list: list of services to add BIG-IP. By default ['adc_core','access']
    @param cluster: Name of a cluster to add devices to (ACCESS)
    @param use_bigiq_sync: Firewall flag
    @param snapshot_working_config: Performs snapshot of working config before import
    @param import_config: Perform the import on the Discovered modules
    @return: device-resolver inventory of cm-bigip-allBigipDevices
    """

    def __init__(self, devices, services_list=None, cluster=None, use_bigiq_sync=False,
                 snapshot_working_config=False, refresh_config=False,
                 *args, **kwargs):

        if services_list is None:
            services_list = [CM_GLOBAL_ADC_NAME, CM_GLOBAL_ACCESS_NAME]
        super(DiscoverAccess, self).__init__(devices=devices, services_list=services_list,
                                             cluster=cluster, use_bigiq_sync=use_bigiq_sync,
                                             snapshot_working_config=snapshot_working_config,
                                             import_config=False, refresh_config=refresh_config,
                                             *args, **kwargs)

    def setup(self):
        # make sure we will not import services for sure, only discover them
        self.import_config = False
        super(DiscoverAccess, self).setup()
        # at this point the discovery has been completed
        # we need to import only adc_core configuration
        # if adc_core imported on a device, then do not re-import
        for device in self.devices:
            uuid = get_machine_id(device)
            resp = self.api.get(MachineIdResolver.ITEM_URI % uuid)
            # assuming adc_core and access already discovered by setup already (in parent class)
            assert resp[PROPERTIES][DEFAULT_CM_ADC_DEVICE_GROUP] is not None, "adc_core services missed"
            assert resp[PROPERTIES][DEFAULT_CM_ADC_DEVICE_GROUP]["discovered"] is True, "adc_core is not discovered"
            assert resp[PROPERTIES][DEFAULT_CM_ACCESS_DEVICE_GROUP] is not None, "Accesss services missed"
            assert resp[PROPERTIES][DEFAULT_CM_ACCESS_DEVICE_GROUP]["discovered"] is True, "Access is not discovered"

            is_adc_core_imported = resp[PROPERTIES][DEFAULT_CM_ADC_DEVICE_GROUP]["imported"]
            # if adc_core already is not imported, then need to import
            if not is_adc_core_imported:
                resp = import_service_config(device, CM_GLOBAL_ADC_NAME, self.cluster,
                                             self.use_bigiq_sync, self.snapshot_working_config)
                self.completed(device)

        return self.post_discovery_steps()


check_device_availability = None
class CheckDeviceAvailability(IcontrolRestCommand):  # @IgnorePep8
    """Checks device availability status.
    Raises:
     - WaitTimedOut: timeout
     - ValueError when device UUID is not found

    @param devices: An iteraible container of f5test.interfaces.common.DeviceAccess instances
    @param timeout: Override checker services timeout
    @return: None
    """
    def __init__(self, devices, timeout=HEALTH_CHECK_TIMEOUT, *args, **kwargs):
        super(CheckDeviceAvailability, self).__init__(*args, **kwargs)
        self.devices = devices
        self.health_timeout = timeout

    def setup(self):
        for device in self.devices:
            LOG.info('Checking device "%s" availability...' % device)
            machineid = get_machine_id(device)
            if machineid is not None:
                resp = self.api.get(MachineIdResolver.ITEM_URI % machineid)

                self.wait_for_availability(resp)
            else:
                raise ValueError("Unable to locate uui for '%s' device" % device)
            LOG.info('Device "%s" is available...' % device)

    def wait_for_availability(self, resource):
        stats_link = resource.selfLink + '/stats'
        return wait_args(self.api.get, func_args=[stats_link],
                         condition=lambda x: x.entries.get('health.summary.available', {}).get('value') == 1,
                         timeout=self.health_timeout,
                         timeout_message="Object %s not available after {0} seconds" % resource.selfLink)


add_device_access_group = None
class AddDeviceAccessGroup(IcontrolRestCommand):  # @IgnorePep8
    """
    Type: POST
    @param group_name: group name, which should be unique, only letters and numbers
    @type group_name: string

    @param device: device to add into group
    @type instance of f5test.interfaces.config.DeviceAccess

    @return: the task status
    @rtype: attr dict json
    """

    task = access.AccessGroupTask

    def __init__(self, group_name, device, import_shared=True, cluster_name=None,
                 *args, **kwargs):
        super(AddDeviceAccessGroup, self).__init__(*args, **kwargs)
        self.group_name = group_name
        self.device = device
        self.import_shared = import_shared
        self.task_self_link = None
        self.cluster_name = cluster_name

    def prep(self):
        super(AddDeviceAccessGroup, self).prep()
        # we need to re-discover Access and adc_core prior to create an access group
        discover_access([self.device], refresh_config=True)

    def resolve_conflicts(self, resp):
        result = resp
        if resp.currentStep == "PENDING_CONFLICTS" and resp.status == "FINISHED":
            LOG.info("The re-import task requires resolving conflicts...")
            payload = AttrDict()
            payload.status = "STARTED"
            payload.properties = AttrDict()
            payload.properties["cm:access:conflict-resolution"] = "ACCEPT"

            task = self.api.patch(resp.selfLink, payload=payload)
            dma_task = self.task()
            patched_task = dma_task.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                             timeout_message="Task: 'mgmt-authority'; actionType: ADDING DEVICE did not complete in {0} seconds")
            result = self.resolve_conflicts(patched_task)
        elif resp.currentStep == "DONE" and resp.status == "FINISHED":
            LOG.info("Conflicts were resolved. re-import task completed.")
            return result
        else:
            LOG.debug("Current response for mgmt-authority task:\n %s" % resp)
            raise TaskError("Could not determine state of the task...")
        return result

    def setup(self):

        """Check if access group exists"""
        if not is_group_exist(self.api, self.group_name):
            raise Exception("The access group '%s' doesn't exist" % self.group_name)

        """Add a device to access group"""
        uri = DeviceResolver.DEVICES_URI % DEFAULT_ACCESS_GROUP
        rest_devices = self.api.get(uri)
        device_reference = AttrDict()
        device_address = self.device.get_address()
        retst_resp = None
        for x in rest_devices["items"]:
            if x.address == device_address:
                retst_resp = x
                break
        if retst_resp is not None:
            device_reference = retst_resp.selfLink
        dma = self.task()
        # let's check the stats of the devices
        # Task will fail, if devices are not healthy
        check_device_availability([self.device])
        dma.properties["cm:access:access-group-name"] = self.group_name
        dma.properties["cm:access:import-shared"] = self.import_shared
        dma.deviceReference.link = device_reference
        dma.clusterName = self.cluster_name

        uri = access.AccessGroupTask.URI
        LOG.info("Creating access group '{0}' with device: '{1}".format(self.group_name, device_reference))
        task = self.api.post(uri, payload=dma)
        self.task_self_link = task.selfLink
        resp = dma.wait(self.ifc, task, timeout=DEFAULT_TIMEOUT,
                        timeout_message="Access 'declare-mgmt-authority' task did not complete in {0} seconds")
        return self.resolve_conflicts(resp)
