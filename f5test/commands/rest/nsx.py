'''
Created on Mar 18, 2015

@author: marepally
'''


import logging
from f5test.interfaces.rest.netx.resources import NetxResourceError
from f5test.utils.wait import wait_args, wait, StopWait
from f5test.commands.rest.base import NetxCommand
from f5test.commands.base import CommandError
from f5test.base import Options
from f5test.interfaces.rest.netx.objects.nsx import ServiceInstances, LoadBalancer, \
    ServiceManagers, Pool, Virtualserver, ServiceInstanceTemplates, \
    Edges, Runtime
import json
import copy
import pyVmomi
from pyVim import connect
import atexit
from operator import itemgetter
import time

LOG = logging.getLogger(__name__)

uninstall_runtime = None


class UninstallRuntime(NetxCommand):
    """ Uninstall service runtime from NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    @param service_runtime_id: Service Runtime Id #mandatory
    @type service_runtime_id: string

    @return: If service runtime is uninstalled?
    @type: Boolean

    """

    def __init__(self,
                 service_instance_id,
                 *args, **kwargs):
        super(UninstallRuntime, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.nsx = kwargs.get('device')

    def setup(self):

        def wait_on_uninstall(ret):
            if (ret.serviceInstanceRuntimeInfos and
                    ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo):
                    return (ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.status == 'OUT_OF_SERVICE' and
                            ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.installState == 'NOT_INSTALLED')
            return False

        try:
            ret = self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id))
            srid = ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.id
            self.nsx_rst_api.post(Runtime.CONFIG_URI % (self.service_instance_id,
                                                        srid),
                                  params_dict={'action': 'uninstall'})

            if srid:
                # This will not be true for adding existing BIGIP to NSX case
                # Check with vcenter if the VM is deleted on HOST
                wait(lambda: GetVM(vm_id=srid, device=self.nsx).run(),
                     condition=lambda VMobj: len(VMobj) == 0,
                     progress_cb=lambda x: "Waiting on vcenter to delete = {0}".format(srid),
                     timeout=60, interval=5,
                     timeout_message="VM = {0} not deleted on vcenter".format(srid))

        finally:
            wait(lambda: self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id)),
                 condition=wait_on_uninstall,
                 progress_cb=lambda x: "Waiting for runtime id={0} to UNINSTALL"
                 .format(self.service_runtime_id),
                 timeout=20, interval=4,
                 timeout_message="Failed to UNINSTALL runtime, id={0}"
                 .format(srid))
            LOG.debug("UNINSTALLED runtime id = {0} on NSX".format(srid))

disable_runtime = None


class DisableRuntime(NetxCommand):
    """ Power-off the service runtime on NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    @param service_runtime_id: Service Runtime Id #mandatory
    @type service_runtime_id: string

    @return: If service runtime is Powered-OFF?
    @type: Boolean

    """

    def __init__(self,
                 service_instance_id,
                 service_runtime_id,
                 *args, **kwargs):
        super(DisableRuntime, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.service_runtime_id = service_runtime_id

    def setup(self):

        def wait_on_disable(ret):
            if ret and ret.serviceInstanceRuntimeInfos and ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                if isinstance(ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo, list):
                    for sir in ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                        if int(sir.id) == self.service_runtime_id:
                            return (sir.installState == 'DISABLED' and
                                    sir.status == 'OUT_OF_SERVICE')
                else:
                    return (ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.installState == 'DISABLED' and
                            ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.status == 'OUT_OF_SERVICE')
            return False
        LOG.debug("Powering off runtime id = {0} on NSX".format(self.service_runtime_id))
        try:
            self.nsx_rst_api.post(Runtime.CONFIG_URI % (self.service_instance_id,
                                                        self.service_runtime_id),
                                  params_dict={'action': 'disable'})
        finally:
            wait(lambda: self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id)),
                 condition=wait_on_disable,
                 progress_cb=lambda x: "Waiting for runtime id={0} to power-off"
                 .format(self.service_runtime_id),
                 timeout=20, interval=4,
                 timeout_message="runtime, id={0} could not be power-off"
                 .format(self.service_runtime_id))

enable_runtime = None


class EnableRuntime(NetxCommand):
    """ Power-On the service runtime on NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    @param service_runtime_id: Service Runtime Id #mandatory
    @type service_runtime_id: string

    @return: If service runtime is Powered-ON?
    @type: Boolean

    """

    def __init__(self,
                 service_instance_id,
                 service_runtime_id,
                 *args, **kwargs):
        super(EnableRuntime, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.service_runtime_id = service_runtime_id

    def setup(self):

        def wait_on_enable(ret):
            if ret and ret.serviceInstanceRuntimeInfos and ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                if isinstance(ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo, list):
                    for sir in ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                        if int(sir.id) == self.service_runtime_id:
                            return sir.installState == 'ENABLED'
                else:
                    return ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo.installState == 'ENABLED'
            return False
        LOG.debug("Powering ON runtime id = {0} on NSX".format(self.service_runtime_id))
        try:
            self.nsx_rst_api.post(Runtime.CONFIG_URI % (self.service_instance_id,
                                                        self.service_runtime_id),
                                  params_dict={'action': 'enable'})
        except NetxResourceError:
            pass  # ignore on error as on return we check for NOT_INSTALLED state else fail
        wait(lambda: self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id)),
             condition=wait_on_enable,
             progress_cb=lambda x: "Waiting for runtime id={0} to power-on"
             .format(self.service_runtime_id),
             timeout=180, interval=10,
             timeout_message="runtime, id={0} could not be powered-on"
             .format(self.service_runtime_id))

remove_runtime = None


class RemoveRuntime(NetxCommand):

    """ Removes service runtime from NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    @param service_runtime_id: Service Runtime Id #mandatory
    @type service_runtime_id: string

    @return: If service runtime is deleted?
    @type: Boolean

    """

    def __init__(self,
                 service_instance_id,
                 service_runtime_id,
                 *args, **kwargs):
        super(RemoveRuntime, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.service_runtime_id = service_runtime_id

    def setup(self):
        LOG.debug("Deleting runtime id = {0} on NSX".format(self.service_runtime_id))
        try:
            self.nsx_rst_api.delete(Runtime.ITEM_URI % (self.service_instance_id, self.service_runtime_id))
        except NetxResourceError:
            pass  # ignore on error as on return we check for delete state else fail
        wait(lambda: self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id)),
             condition=lambda ret: ret.serviceInstanceRuntimeInfos is None,
             progress_cb=lambda x: "Waiting for runtime id={0} to be deleted".format(self.service_runtime_id),
             timeout=20, interval=4,
             timeout_message="runtime, id={0} could not be deleted".format(self.service_runtime_id))

remove_service_manager = None


class RemoveServiceManager(NetxCommand):
    """ Removes service manager from NSX

    @param manager_id: NSX Service Manager Id #mandatory
    @type manager_id: string

    @return: If service manager is removed/deleted?
    @type: Boolean

    """

    def __init__(self,
                 manager_id,
                 *args, **kwargs):
        super(RemoveServiceManager, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.manager_id = manager_id

    def self(self):
        LOG.debug("Delete NSX service manager id = {0}".format(self.manager_id))
        try:
            self.nsx_rst_api.delete(ServiceManagers.ITEM_URI % self.manager_id)
        except NetxResourceError:
            pass
        wait(lambda x: self.nsx_rst_api.get(ServiceManagers.URI),
             condition=lambda ret: self.manager_id in [sm.objectId for sm in ret.serviceManagers.serviceManager if sm.objectId == self.manager_id],
             progress_cb=lambda x: "Waiting on service manager deletion, id={0}".format(self.manager_id),
             timeout=20, interval=4,
             timeout_message="service manager, id={0} was not removed".format(self.manager_id))

check_service_manager = None


class CheckServiceManager(NetxCommand):
    """ Checks service manager on NSX

    @param manager_id: NSX Service Manager Id #mandatory
    @type manager_id: string

    @return: If service manager is available or not?
    @type: Boolean

    """

    def __init__(self,
                 manager_id,
                 *args, **kwargs):
        super(CheckServiceManager, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.manager_id = manager_id

    def self(self):
        LOG.debug("Checking NSX service manager id = {0}".format(self.manager_id))
        wait(lambda x: self.nsx_rst_api.get(ServiceManagers.URI),
             condition=lambda ret: self.manager_id in [sm.objectId for sm in ret.serviceManagers.serviceManager if sm.objectId == self.manager_id],
             progress_cb=lambda x: "Waiting on service manager deletion, id={0}".format(self.manager_id),
             timeout=20, interval=4,
             timeout_message="service manager, id={0} was not removed".format(self.manager_id))
        LOG.debug("NSX service manager id = {0} deleted on NSX".format(self.manager_id))

get_old_service_instance_template = None


class GetOldServiceInstanceTemplate(NetxCommand):
    """ Verifies service instance template on NSX Manager

    @param service_id: NSX service Id #mandatory
    @type service_id: String

    @param template_name: NSX service instance template name #mandatory
    @type service_id: String

    """
    F5_ADC_NEW = "F5-ADC-NEW-BIG-IP"
    F5_ADC_EXISTING = "F5-ADC-EXISTING-BIG-IP"
    F5_ADC_HOST_NAME_KEY = 'F5-BIG-IP-VE-FQ-HOST-NAME'
    F5_ADC_ADDRESS_NAME_KEY = 'F5-BIG-IP-ADDRESS'
    F5_ADC_OVF_NAME_KEY = 'F5-BIG-IP-VE-OVF-NAME'
    F5_ADC_OVF_URL_KEY = 'F5-BIG-IP-VE-OVF-URL'
    F5_ADC_ADMIN_PASS_KEY = 'F5-BIG-IP-VE-ADMIN-PASSWORD'
    F5_ADC_OLD_PROVISION_KEY = 'F5-BIG-IP-MAKE-VE'

    def __init__(self,
                 service_id,
                 template_name,
                 *args, **kwargs):
        super(GetOldServiceInstanceTemplate, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_id = service_id
        self.template_name = template_name

    def setup(self):
        service = self.nsx_rst_api.get(ServiceInstanceTemplates.URI % self.service_id)
        template = service.serviceInstanceTemplates.serviceInstanceTemplate

        for currtemplate in template:
            if self.template_name == self.F5_ADC_NEW and currtemplate.instanceTemplateId == self.template_name:
                self.verify_adc_new_template(currtemplate)
                return (currtemplate.id, currtemplate.typedAttributes.typedAttribute)

            elif self.template_name == self.F5_ADC_EXISTING and currtemplate.instanceTemplateId == self.template_name:
                self.verify_adc_existing_template(currtemplate)
                return currtemplate

        raise Exception("Matching service instance template not found on NSX Service, \n {0} \n".format(service))

    def verify_adc_new_template(self, template):
        """ This function verifies service instance template used for creating new BIGIP """
        for attr in template.typedAttributes.typedAttribute:
            if attr.key == self.F5_ADC_OLD_PROVISION_KEY:
                if not (attr.type == 'STRING' and attr.value == 'yes'):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            if attr.key in (self.F5_ADC_OVF_NAME_KEY, self.F5_ADC_OVF_URL_KEY, self.F5_ADC_ADMIN_PASS_KEY,
                            self.F5_ADC_HOST_NAME_KEY):
                if not (attr.type == "STRING"):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            raise Exception("Unknown typed attribute found for template id = {0}, service id = {0} ".format(template.id, self.service_id))
        return

    def verify_adc_existing_template(self, template):
        """ This function verifies service instance template used for adding existing BIGIP """
        for attr in template.typedAttributes.typedAttribute:
            if attr.key == self.F5_ADC_ADDRESS_NAME_KEY:
                if not (attr.type == "IP_ADDRESS"):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue
            if attr.key in (self.F5_ADC_OLD_PROVISION_KEY):
                if not (attr.type == "STRING"):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            raise Exception("Unknown typed attribute found for template id = {0}, service id = {0} ".format(template.id, self.service_id))
        return


get_service_instance_template = None


class GetServiceInstanceTemplate(NetxCommand):
    """ Verifies service instance template on NSX Manager

    @param service_id: NSX service Id #mandatory
    @type service_id: String

    @param template_name: NSX service instance template name #mandatory
    @type service_id: String

    """
    F5_ADC_NEW = "F5-ADC-NEW-BIG-IP"
    F5_ADC_EXISTING = "F5-ADC-EXISTING-BIG-IP"
    F5_ADC_HOST_NAME_KEY = 'F5-BIG-IP-VE-FQ-HOST-NAME'
    F5_ADC_ADDRESS_NAME_KEY = 'F5-BIG-IP-ADDRESS'
    F5_ADC_PROVISION_KEY = 'F5-BIG-IP-PROVISION-VE'

    def __init__(self,
                 service_id,
                 template_name,
                 *args, **kwargs):
        super(GetServiceInstanceTemplate, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_id = service_id
        self.template_name = template_name

    def setup(self):
        service = self.nsx_rst_api.get(ServiceInstanceTemplates.URI % self.service_id)
        template = service.serviceInstanceTemplates.serviceInstanceTemplate

        for currtemplate in template:
            if self.template_name == self.F5_ADC_NEW and currtemplate.instanceTemplateId == self.template_name:
                self.verify_adc_new_template(currtemplate)
                return (currtemplate.id, currtemplate.typedAttributes.typedAttribute)

            elif self.template_name == self.F5_ADC_EXISTING and currtemplate.instanceTemplateId == self.template_name:
                self.verify_adc_existing_template(currtemplate)
                return currtemplate

        raise Exception("Matching service instance template not found on NSX Service, \n {0} \n".format(service))

    def verify_adc_new_template(self, template):
        """ This function verifies service instance template used for creating new BIGIP """
        for attr in template.typedAttributes.typedAttribute:
            if attr.key == self.F5_ADC_PROVISION_KEY:
                if not (attr.type == 'STRING' and attr.value == 'yes' and str(attr.editable) == 'false'):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            if attr.key == self.F5_ADC_HOST_NAME_KEY:
                if not (attr.type == "STRING" and str(attr.editable) == 'true'):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            raise Exception("Unknown typed attribute found for template id = {0}, service id = {0} ".format(template.id, self.service_id))
        return

    def verify_adc_existing_template(self, template):
        """ This function verifies service instance template used for adding existing BIGIP """
        for attr in template.typedAttributes.typedAttribute:
            if attr.key == self.F5_ADC_PROVISION_KEY:
                if not (attr.type == 'STRING' and attr.value == 'no' and str(attr.editable) == 'false'):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            if attr.key == self.F5_ADC_ADDRESS_NAME_KEY:
                if not (attr.type == "IP_ADDRESS" and str(attr.editable) == 'true'):
                    raise Exception("Incorrect type/value on service instance template, key={0}".format(attr.key))
                else:
                    continue

            raise Exception("Unknown typed attribute found for template id = {0}, service id = {0} ".format(template.id, self.service_id))
        return

create_service_instance_for_new = None


class CreateServiceInstanceForNew(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """ Creates a service instance on NSX

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param instance_name: Service instance name    #mandatory
    @type instance_name: String

    @param si_template_name: Service instance pay load template name    #mandatory only while creating service instance
    @type si_template_name: String

    @param vnics_template_name: Runtime vnic information pay load template name    #mandatory only while creating service instance
    @type vnics_template_name: String

    @param specs: Specification to successfully create a service instance    #mandatory
    @type specs: Attrdict

    @param template_format: A service instance pay load template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 instance_name,
                 si_template_name,
                 vnics_template_name,
                 specs,
                 floating_ip_template_name=None,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateServiceInstanceForNew, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.instance_name = instance_name
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.si_template_name = si_template_name
        self.vnics_template_name = vnics_template_name
        self.floating_ip_template_name = floating_ip_template_name
        self.nsx = kwargs.pop('device')  # Get the NSX device object
        self.specs = specs
        self.template_format = template_format

    def setup(self):
        LOG.debug("Creating NSX service instance on edge, id={0}".format(self.edge_id))
        payload = ServiceInstances().from_file(self.template_dir, self.si_template_name, fmt=self.template_format)
        floating_payload = None

        # Change the name of the service instance runtime vm
        payload.serviceInstance.name = self.instance_name
        payload.serviceInstance.description = self.instance_name

        if self.specs.typed_attributes:
            payload.serviceInstance.config.instanceTemplateTypedAttributes.typedAttribute = self.specs.typed_attributes

        if self.specs.template_id:
            payload.serviceInstance.config.instanceTemplate.id = self.specs.template_id

        if self.specs.enable_ha:
            for attr in payload.serviceInstance.config.implementationAttributes.attribute:
                if attr.key == "haEnabled":
                    attr.value = True
                elif attr.key == "tenantId":
                    attr.value = self.specs.tenant if self.specs.tenant else attr.value

        # replacing data store and resource pool corresponding to the NSX environment
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.resourcePool = self.nsx.specs.resourcePool
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.datastore = (self.specs.datastoreId
                                                                                      if self.specs.datastoreId else self.nsx.specs.datastore)

        # associate the edge-id
        payload.serviceInstance.config.baseRuntimeConfig.runtimeInstanceId = self.edge_id
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.nics.runtimeNicInfo = []

        if self.specs.nic_interfaces:
            for ifc in self.specs.nic_interfaces:
                vnic_payload = ServiceInstances().from_file(self.template_dir,
                                                            self.vnics_template_name,
                                                            fmt=self.template_format)
                vnic_payload.runtimeNicInfo.label = ifc.label
                vnic_payload.runtimeNicInfo.index = ifc.index
                vnic_payload.runtimeNicInfo.network.objectId = ifc.network.object_id
                vnic_payload.runtimeNicInfo.connectivityType = ifc.connectivity_type
                vnic_payload.runtimeNicInfo.ipAllocationType = ifc.ip_allocation_type
                vnic_payload.runtimeNicInfo.ipPool.objectId = ifc.ippool.object_id
                if ifc.connected:
                    vnic_payload.runtimeNicInfo.connected = ifc.connected
                if ifc.default_route:
                    vnic_payload.runtimeNicInfo.defaultRoute = ifc.default_route
                if ifc.floating_ip and ifc.floating_ip.use:
                    floating_payload = ServiceInstances().from_file(self.template_dir,
                                                                    self.floating_ip_template_name,
                                                                    fmt=self.template_format)
                    floating_payload.secondaryAddresses.runtimeNicSecondaryAddress.name = ifc.floating_ip.name
                    floating_payload.secondaryAddresses.runtimeNicSecondaryAddress.ipPool.objectId = ifc.floating_ip.ip_pool.object_id
                    vnic_payload.runtimeNicInfo.update(copy.deepcopy(floating_payload))
                elif vnic_payload.runtimeNicInfo.secondaryAddresses:
                    vnic_payload.runtimeNicInfo.pop("secondaryAddresses")
                payload.serviceInstance.config.baseRuntimeConfig.\
                    deploymentScope.nics.runtimeNicInfo \
                    .append(copy.deepcopy(vnic_payload.runtimeNicInfo))

        if self.specs.service_id:
            payload.serviceInstance.service.objectId = self.specs.service_id

        return self.nsx_rst_api.post(ServiceInstances.POST_URI, payload)

create_service_instance_for_existing = None


class CreateServiceInstanceForExisting(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """ Creates a service instance on NSX

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param instance_name: Service instance name    #mandatory
    @type instance_name: String

    @param si_template_name: Service instance pay load template name    #mandatory only while creating service instance
    @type si_template_name: String

    @param vnics_template_name: Runtime vnic information pay load template name    #mandatory only while creating service instance
    @type vnics_template_name: String

    @param specs: Specification to successfully create a service instance    #mandatory
    @type specs: Attrdict

    @param template_format: A service instance pay load template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 instance_name,
                 si_template_name,
                 vnics_template_name,
                 specs,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateServiceInstanceForExisting, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.instance_name = instance_name
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.si_template_name = si_template_name
        self.vnics_template_name = vnics_template_name
        self.nsx = kwargs.pop('device')
        self.specs = specs
        self.template_format = template_format

    def setup(self):
        LOG.debug("Creating NSX service instance on edge, id={0}".format(self.edge_id))
        payload = ServiceInstances().from_file(self.template_dir, self.si_template_name, fmt=self.template_format)

        # Change the name of the service instance runtime vm
        payload.serviceInstance.name = self.instance_name
        payload.serviceInstance.description = self.instance_name

        if self.specs.typed_attributes:
            payload.serviceInstance.config.instanceTemplateTypedAttributes = self.specs.typed_attributes

        if self.specs.template_id:
            payload.serviceInstance.config.instanceTemplateTypedAttributes.id = self.specs.template_id

        # replacing data store and resource pool corresponding to the NSX environment
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.resourcePool = self.nsx.specs.resourcePool
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.datastore = self.nsx.specs.datastore

        # associate the edge-id
        payload.serviceInstance.config.baseRuntimeConfig.runtimeInstanceId = self.edge_id
        payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.nics.runtimeNicInfo = []

        if self.specs.nic_interfaces:
            for ifc in self.specs.nic_interfaces:
                    vnic_payload = ServiceInstances().from_file(self.template_dir, self.vnics_template_name, fmt=self.template_format)
                    vnic_payload.runtimeNicInfo.label = ifc.label
                    vnic_payload.runtimeNicInfo.index = ifc.index
                    vnic_payload.runtimeNicInfo.network.objectId = ifc.network.object_id
                    vnic_payload.runtimeNicInfo.connectivityType = ifc.connectivity_type
                    vnic_payload.runtimeNicInfo.ipAllocationType = ifc.ip_allocation_type
                    if ifc.ip_allocation_type == "IP_POOL":
                        vnic_payload.runtimeNicInfo.ipPool.objectId = ifc.ippool.object_id
                    elif ifc.ip_allocation_type == "DHCP":
                        vnic_payload.runtimeNicInfo.pop("ipPool")
                    payload.serviceInstance.config.baseRuntimeConfig.deploymentScope.nics.runtimeNicInfo.append(vnic_payload.runtimeNicInfo)

        if self.specs.service_id:
            payload.serviceInstance.service.objectId = self.specs.service_id

        return self.nsx_rst_api.post(ServiceInstances.ITEM_URI, payload)

check_service_instance = None


class CheckServiceInstance(NetxCommand):
    """ Checks for service instance on NSX

    @param service_intance_id: Service instance id    #mandatory
    @type service_intance_id: String

    """

    def __init__(self,
                 service_intance_id,
                 *args, **kwargs):
        super(CheckServiceInstance, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_intance_id = service_intance_id

    def wait_on_remove(self):
        try:
            instances = self.nsx_rst_api.get(ServiceInstances.URI)
            if instances and instances.serviceInstances and instances.serviceInstances.serviceInstance:
                if isinstance(instances.serviceInstances.serviceInstance, list):
                    for si in instances.serviceInstances.serviceInstance:
                        if si.objectId == self.service_intance_id:
                            return False
                elif instances.serviceInstances.serviceInstance.objectId == self.service_intance_id:  # When there is only 1 instance on NSX
                    return False
            return True  # When there are no service instances on NSX
        except NetxResourceError:
            return False

    def setup(self):
        LOG.debug("Check for service instance id = {0} on NSX".format(self.service_intance_id))
        wait_args(self.wait_on_remove,
                  condition=lambda x: x,
                  progress_cb=lambda x: "checking for service instance id={0}".format(self.service_intance_id),
                  timeout=20, interval=4,
                  timeout_message="Service instance, id={0} was not removed on edge".format(self.service_intance_id))
        LOG.debug("service instance id = {0} deleted on NSX".format(self.service_intance_id))

delete_service_instance = None


class DeleteServiceInstance(NetxCommand):
    """ Removes service instance on NSX

    @param service_intance_id: Service instance id    #mandatory
    @type service_intance_id: String

    """

    def __init__(self,
                 service_instance_id,
                 *args, **kwargs):
        super(DeleteServiceInstance, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id

    def setup(self):
        LOG.debug("Deleting service instance id = {0} on NSX".format(self.service_instance_id))
        try:
            self.nsx_rst_api.delete(ServiceInstances.ITEM_URI + "/%s" % (self.service_instance_id))
        except NetxResourceError:
            # Issue delete only once
            pass


create_load_balancer_for_new = None


class CreateLoadBalancerForNew(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """ Creates load balancer service on NSX edge

    @param edge_id: NSX edge id #mandatory
    @type edge_id: String

    @param instance_name: Load balancer service name    #mandatory
    @type instance_name: String

    @param lb_template_name: A load balancer pay load template name    #mandatory only while inserting load balancer
    @type lb_template_name: String

    @param vnics_template_name: Runtime vnic information pay load template name    #mandatory only while creating service instance
    @type vnics_template_name: String

    @param specs: Specification to successfully insert a load balancer service on NSX edge    #mandatory
    @type specs: Attrdict

    @param template_format: A load balancer service pay load template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 instance_name,
                 lb_template_name,
                 vnics_template_name,
                 specs,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateLoadBalancerForNew, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.instance_name = instance_name
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.lb_template_name = lb_template_name
        self.vnics_template_name = vnics_template_name
        self.template_format = template_format
        self.specs = specs

    def setup(self):
        LOG.debug("Inserting load balancer service on nsx edge, id={0}".format(self.edge_id))
        template = LoadBalancer().from_file(self.template_dir, self.lb_template_name, fmt=self.template_format)
        vnic_payload = ServiceInstances().from_file(self.template_dir, self.vnics_template_name, fmt=self.template_format)
        gsi = template.loadBalancer.globalServiceInstance

        if self.specs.service_instance_id:
            gsi.serviceInstanceId = self.specs.service_instance_id

        gsi.name = self.instance_name

        if self.specs.service_id:
            gsi.serviceId = self.specs.service_id

        if self.specs.service_name:
            gsi.serviceName = self.specs.service_name

        if self.specs.template_id:
            gsi.instanceTemplateId = self.specs.template_id
            gsi.instanceTemplateUniqueId = self.specs.template_id

        if self.specs.typed_attributes:
            gsi.instanceTemplateTypedAttributes.typedAttribute = self.specs.typed_attributes

        if self.specs.deployment_spec_id:
            gsi.versionedDeploymentSpecId = self.specs.deployment_spec_id

        gsi.runtimeNicInfo = []
        if self.specs.nic_interfaces:
            for ifc in self.specs.nic_interfaces:
                vnic_payload.runtimeNicInfo.label = ifc.label
                vnic_payload.runtimeNicInfo.index = ifc.index
                vnic_payload.runtimeNicInfo.network.objectId = ifc.network.object_id
                vnic_payload.runtimeNicInfo.connectivityType = ifc.connectivity_type
                vnic_payload.runtimeNicInfo.ipAllocationType = ifc.ip_allocation_type
                vnic_payload.runtimeNicInfo.ipPool.objectId = ifc.ippool.object_id
                gsi.runtimeNicInfo.append(copy.deepcopy(vnic_payload.runtimeNicInfo))

        wait_args(self.retry_insert_lb, func_args=[template], condition=lambda state: state,
                  progress_cb=lambda state: "Waiting to PUT global service instance",
                  timeout=60, interval=20,
                  timeout_message="Failed to insert loadbalancer service after {0}s")

        return True

    def retry_insert_lb(self, payload):
        """ Check whether previous PUT succeeded """

        time.sleep(5)
        lb = self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id)
        if not lb.loadBalancer.globalServiceInstance:  # if previous PUT failed, retry
            lb.loadBalancer.update(payload.loadBalancer)
            try:
                self.nsx_rst_api.put(LoadBalancer.URI % self.edge_id, payload=lb)
            except NetxResourceError:
                return False
        elif lb.loadBalancer.globalServiceInstance and lb.loadBalancer.globalServiceInstance.serviceInstanceId == self.specs.service_instance_id:
            return True
        elif lb.loadBalancer.globalServiceInstance and lb.loadBalancer.globalServiceInstance.serviceInstanceId != self.specs.service_instance_id:
            msg = json.dumps(lb, sort_keys=True, indent=4, ensure_ascii=False)
            raise StopWait("{0} has an existing global service instance that's not removed. Edge cannot be used \n {1}".format(self.edge_id, msg))

create_load_balancer_for_existing = None


class CreateLoadBalancerForExisting(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """ Creates load balancer service on NSX edge

    @param edge_id: NSX edge id #mandatory
    @type edge_id: String

    @param instance_name: Load balancer service name    #mandatory
    @type instance_name: String

    @param lb_template_name: A load balancer pay load template name    #mandatory only while inserting load balancer
    @type lb_template_name: String

    @param vnics_template_name: Runtime vnic information pay load template name    #mandatory only while creating service instance
    @type vnics_template_name: String

    @param specs: Specification to successfully insert a load balancer service on NSX edge    #mandatory
    @type specs: Attrdict

    @param template_format: A load balancer service pay load template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 instance_name,
                 lb_template_name,
                 vnics_template_name,
                 specs,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateLoadBalancerForExisting, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.instance_name = instance_name
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.lb_template_name = lb_template_name
        self.vnics_template_name = vnics_template_name
        self.template_format = template_format
        self.specs = specs

    def setup(self):
        LOG.debug("Inserting load balancer service on nsx edge, id={0}".format(self.edge_id))
        template = LoadBalancer().from_file(self.template_dir, self.lb_template_name, fmt=self.template_format)
        gsi = template.loadBalancer.globalServiceInstance

        if self.specs.service_instance_id:
            gsi.serviceInstanceId = self.specs.service_instance_id

        gsi.name = self.instance_name

        if self.specs.service_id:
            gsi.serviceId = self.specs.service_id

        if self.specs.service_name:
            gsi.serviceName = self.specs.service_name

        if self.specs.template_id:
            gsi.instanceTemplateId = self.specs.template_id
            gsi.instanceTemplateUniqueId = self.specs.template_id

        if self.specs.typed_attributes:
            gsi.instanceTemplateTypedAttributes = self.specs.typed_attributes

        gsi.runtimeNicInfo = []
        if self.specs.nic_interfaces:
            for ifc in self.specs.nic_interfaces:
                vnic_payload = ServiceInstances().from_file(self.template_dir, self.vnics_template_name, fmt=self.template_format)
                vnic_payload.runtimeNicInfo.label = ifc.label
                vnic_payload.runtimeNicInfo.index = ifc.index
                vnic_payload.runtimeNicInfo.network.objectId = ifc.network.object_id
                vnic_payload.runtimeNicInfo.connectivityType = ifc.connectivity_type
                vnic_payload.runtimeNicInfo.ipAllocationType = ifc.ip_allocation_type
                if ifc.ip_allocation_type == "IP_POOL":
                    vnic_payload.runtimeNicInfo.ipPool.objectId = ifc.ippool.object_id
                elif ifc.ip_allocation_type == "DHCP":
                    vnic_payload.runtimeNicInfo.pop("ipPool")
                gsi.runtimeNicInfo.append(vnic_payload.runtimeNicInfo)

        wait_args(self.retry_insert_lb, func_args=[template], condition=lambda state: state,
                  progress_cb=lambda state: "Waiting to PUT global service instance",
                  timeout=60, interval=20,
                  timeout_message="Failed to insert loadbalancer service after {0}s")

        return True

    def retry_insert_lb(self, payload):
        """ Check whether previous PUT succeeded """
        time.sleep(5)
        lb = self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id)
        if not lb.loadBalancer.globalServiceInstance:  # if previous PUT failed, retry
            lb.loadBalancer.update(payload.loadBalancer)
            try:
                self.nsx_rst_api.put(LoadBalancer.URI % self.edge_id, payload=lb)
            except NetxResourceError:
                return False
        elif lb.loadBalancer.globalServiceInstance and lb.loadBalancer.globalServiceInstance.serviceInstanceId == self.specs.service_instance_id:
            return True
        elif lb.loadBalancer.globalServiceInstance and lb.loadBalancer.globalServiceInstance.serviceInstanceId != self.specs.service_instance_id:
            msg = json.dumps(lb, sort_keys=True, indent=4, ensure_ascii=False)
            raise StopWait("{0} has an existing global service instance. Edge cannot be used \n {1}".format(self.edge_id, msg))

remove_load_balancer = None


class RemoveLoadBalancer(NetxCommand):
    """

    @param edge_id: NSX edge id #mandatory
    @type edge_id: String

    @param pay_load: pay load to remove load balancer service    #mandatory
    @type pay_load: Attrdict

    """

    def __init__(self,
                 edge_id,
                 pay_load,
                 *args, **kwargs):
        super(RemoveLoadBalancer, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.pay_load = pay_load

    def setup(self):
        LOG.debug('Removing the load balancer service on NSX edge id = {0}'.format(self.edge_id))
        wait_args(lambda: self.nsx_rst_api.put(LoadBalancer.URI % self.edge_id, payload=self.pay_load),
                  condition=lambda _: self.check_lb_state,
                  progress_cb=lambda x: "Waiting to remove load balancer on nsx edge, id={0}".format(self.edge_id),
                  timeout=20, interval=5,
                  timeout_message="load balancer was not removed on edge, id={0}".format(self.edge_id))

    def check_lb_state(self, _):
        time.sleep(5)
        lb = self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id)
        if not lb.loadBalancer.globalServiceInstance:
            return True
        return False

create_pool = None


class CreatePool(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param pool_name: pool name    #mandatory
    @type pool_name: String

    @param algorithm: load balancing algorithm for application delivery    #mandatory
    @type algorithm: String

    @param specs: Specification to successfully insert a pool with pool members on NSX edge    #mandatory
    @type specs: Attrdict

    @param pool_template_name: A pool pay load template name    #mandatory only while creating a pool on NSX edge
    @type pool_template_name: String

    @param member_template_name: A pool member pay load template name    #mandatory only while creating a pool member on NSX edge in a given pool
    @type member_template_name: String

    @param template_format: referenced template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 pool_name,
                 algorithm,
                 specs,
                 pool_template_name,
                 member_template_name,
                 template_format='xml',
                 *args, **kwargs):
        super(CreatePool, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.pool_name = pool_name
        self.algorithm = algorithm
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.pool_template_name = pool_template_name
        self.member_template_name = member_template_name
        self.template_format = template_format
        self.specs = specs

    def setup(self):
        pload = Pool().from_file(self.template_dir, self.pool_template_name, self.template_format)
        mload = Pool().from_file(self.template_dir, self.member_template_name, self.template_format)
        pload.pool.name = self.pool_name
        pload.pool.algorithm = self.algorithm
        pload.pool.member = []
        if self.specs and self.specs.members:
            for item in self.specs.members:
                mload.member.update(item)
                pload.pool.member.append(copy.deepcopy(mload.member))

        self.nsx_rst_api.post(Pool().URI % self.edge_id, payload=pload)
        return True

add_pool_members = None


class AddPoolMembers(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param pool_name: pool name    #mandatory
    @type pool_name: String

    @param algorithm: load balancing algorithm for application delivery    #mandatory
    @type algorithm: String

    @param specs: Specification to successfully insert a pool with pool members on NSX edge    #mandatory
    @type specs: Attrdict

    @param pool_template_name: A pool pay load template name    #mandatory only while creating a pool on NSX edge
    @type pool_template_name: String

    @param member_template_name: A pool member pay load template name    #mandatory only while creating a pool member on NSX edge in a given pool
    @type member_template_name: String

    @param template_format: referenced template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 pool_id,
                 specs,
                 member_template_name,
                 template_format='xml',
                 *args, **kwargs):
        super(AddPoolMembers, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.pool_id = pool_id
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.member_template_name = member_template_name
        self.template_format = template_format
        self.specs = specs

    def retry_update_pool(self, payload):
        try:
            self.nsx_rst_api.put(Pool().ITEM_URI % (self.edge_id, self.pool_id), payload=payload)
            return True
        except NetxResourceError:
            return self.update_check()

    def update_check(self):
        resp = self.nsx_rst_api.get(Pool().ITEM_URI % (self.edge_id, self.pool_id))
        if resp and resp.pool and isinstance(resp.pool.member, list):
            for member in resp.pool.member:
                if member.name in (test_member.name for test_member in self.specs.members):
                    return True
        elif resp and resp.pool and resp.pool.member:
            if resp.pool.member.name in (test_member.name for test_member in self.specs.members):
                return True
        return False

    def setup(self):
        pload = self.nsx_rst_api.get(Pool().ITEM_URI % (self.edge_id, self.pool_id))
        mload = Pool().from_file(self.template_dir, self.member_template_name, self.template_format)

        # Get existing members on the pool.
        # If there is only 1 existing member, then prepare a list to add more members
        if pload.pool.member is None:
            pload.pool.member = []
        elif pload.pool.member and not isinstance(pload.pool.member, list):
            member = []
            member.append(pload.pool.member)
            pload.pool.member = member

        if self.specs and self.specs.members:
            for item in self.specs.members:
                mload.member.update(item)
                pload.pool.member.append(copy.deepcopy(mload.member))

        wait_args(self.retry_update_pool, func_args=[pload],
                  condition=lambda updated: updated,
                  progress_cb=lambda state: "Waiting to add pool member",
                  timeout=25, interval=5,
                  timeout_message="Failed to add pool member after {0}s")
        return True


remove_pool_members = None


class RemovePoolMembers(NetxCommand):
    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param pool_name: pool name    #mandatory
    @type pool_name: String

    @param pool_members: pool members    #mandatory
    @type pool_members: List

    """

    def __init__(self,
                 edge_id,
                 pool_name,
                 pool_members,
                 *args, **kwargs):
        super(RemovePoolMembers, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_id = edge_id
        self.pool_name = pool_name
        self.pool_members = pool_members

    def setup(self):
        def wait_on_remove(pool):
            for node in pool.pool.member:
                if node.memberId in [pool_member.memberId
                                     for pool_member in self.pool_members]:
                    return False
            return True

        nsx_pool = self.nsx_rst_api.get(Pool.ITEM_URI %
                                        (self.edge_id, self.pool_name))

        if nsx_pool.pool.member is None:
            return True
        else:
            for pool_member in self.pool_members:
                for index, node in enumerate(nsx_pool.pool.member):
                    if node.memberId == pool_member.memberId:
                        nsx_pool.pool.member.pop(index)
                        break

        LOG.debug('Removing the pool members in {0} from NSX'.format(self.pool_name))
        try:
            self.nsx_rst_api.put(Pool.ITEM_URI % (self.edge_id, self.pool_name), payload=nsx_pool)
        except NetxResourceError:
            pass
        wait(lambda: self.nsx_rst_api.get(Pool.ITEM_URI %
                                          (self.edge_id,
                                           self.pool_name)),
             condition=lambda ret: wait_on_remove,
             progress_cb=lambda x: "Waiting to remove pool members on edge, id={0}".format(self.edge_id),
             timeout=120, interval=10,
             timeout_message="Pool members were not removed on edge, id={0}".format(self.edge_id))

get_pool = None


class GetPool(NetxCommand):
    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param pool_name: pool name    #mandatory
    @type pool_name: String

    """

    def __init__(self,
                 edge_id,
                 pool_name,
                 *args, **kwargs):
        super(GetPool, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_id = edge_id
        self.pool_name = pool_name

    def setup(self):
        lb = self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id)
        if lb.loadBalancer.pool and isinstance(lb.loadBalancer.pool, list):
            for pool in lb.loadBalancer.pool:
                if pool.name == self.pool_name:
                    return pool.poolId
        elif lb.loadBalancer.pool:
            return lb.loadBalancer.pool.poolId
        else:
            return None

remove_pool = None


class RemovePool(NetxCommand):
    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param pool_name: pool name    #mandatory
    @type pool_name: String

    @param payload: pay load to remove pool from load balancer service    #mandatory
    @type payload: Attrdict

    """

    def __init__(self,
                 edge_id,
                 pool_name,
                 pay_load,
                 *args, **kwargs):
        super(RemovePool, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_id = edge_id
        self.pool_name = pool_name
        self.pay_load = pay_load

    def setup(self):

        def wait_on_remove(lb_resp):
            return lb_resp.loadBalancer.pool is None

        LOG.debug('Removing the pool = {0} from NSX'.format(self.pool_name))
        try:
            self.nsx_rst_api.put(LoadBalancer.URI % self.edge_id, payload=self.pay_load)
        except NetxResourceError:
            pass
        wait(lambda: self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id),
             condition=lambda ret: ret.loadBalancer.pool is None,
             progress_cb=lambda x: "Waiting to remove pool nsx edge, id={0}".format(self.edge_id),
             timeout=20, interval=4,
             timeout_message="Pool was not removed on edge, id={0}".format(self.edge_id))

create_virtual_server = None


class CreateVirtualServer(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param virtual_server_name: virtual server name    #mandatory
    @type virtual_server_name: String

    @param pool_id: existing pool id on NSX edge. This will be the default pool on the virtual server being created.    #mandatory
    @type pool_id: String

    @param vendor: vendor template on NSX edge. Corresponds to catalog on Big-IQ.    #mandatory
    @type vendor: String

    @param pay_load: pay load to create virtual server from load balancer service    #mandatory
    @type pay_load: Attrdict

    @param template_name: A virtual server pay load template name    #mandatory only while creating a virtual server NSX edge
    @type template_name: String

    @param template_format: referenced template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 virtual_server_name,
                 pool_id,
                 vendor,
                 specs,
                 template_name,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateVirtualServer, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.virtual_server_name = virtual_server_name
        self.pool_id = pool_id
        self.vendor = vendor
        self.nsx = kwargs.pop('device')
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.template_name = template_name
        self.template_format = template_format
        self.specs = specs

    def setup(self):
        LOG.debug("Creating Virtual Server: {0}".format(self.virtual_server_name))
        payload = Virtualserver().from_file(self.template_dir, self.template_name, fmt=self.template_format)
        payload.virtualServer.name = self.virtual_server_name

        payload.virtualServer.defaultPoolId = self.pool_id

        payload.virtualServer.vendorProfile.vendorTemplateName = self.vendor.name
        payload.virtualServer.vendorProfile.vendorTemplateId = self.vendor.id
        payload.virtualServer.ipPoolId = self.nsx.specs.ext_nic.ip_pool_id
        payload.virtualServer.ipPoolName = self.nsx.specs.ext_nic.ip_pool_name

        if self.specs.ssl_cert and self.specs.ssl_key:  # used only when deploying ssl-offload iapp
            for attr in payload.virtualServer.vendorProfile.vendorTypedAttributes.typedAttribute:
                if attr.key in "ssl__cert":
                    attr.value = self.specs.ssl_cert
                elif attr.key in "ssl__key":
                    attr.value = self.specs.ssl_key

        self.nsx_rst_api.post(Virtualserver.URI % self.edge_id, payload=payload)

        vs = self.nsx_rst_api.get(Virtualserver.URI % self.edge_id)
        if isinstance(vs.loadBalancer.virtualServer, list):
            for vs_item in vs.loadBalancer.virtualServer:
                if vs_item.name == self.virtual_server_name:
                    return vs_item.virtualServerId
        else:
            return vs.loadBalancer.virtualServer.virtualServerId


update_virtual_server = None


class UpdateVirtualServer(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param virtual_server_name: virtual server name    #mandatory
    @type virtual_server_name: String

    @param pool_id: existing pool id on NSX edge. This will be the default pool on the virtual server being created.    #mandatory
    @type pool_id: String

    @param vendor: vendor template on NSX edge. Corresponds to catalog on Big-IQ.    #mandatory
    @type vendor: String

    @param pay_load: pay load to create virtual server from load balancer service    #mandatory
    @type pay_load: Attrdict

    @param template_name: A virtual server pay load template name    #mandatory only while creating a virtual server NSX edge
    @type template_name: String

    @param template_format: referenced template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_id,
                 virtual_server_id,
                 specs,
                 template_name=None,
                 template_format='xml',
                 *args, **kwargs):
        super(UpdateVirtualServer, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.virtual_server_id = virtual_server_id
        self.nsx = kwargs.pop('device')
        self.specs = specs

    def setup(self):
        LOG.debug("Updating Virtual Server: {0}".format(self.virtual_server_id))
        pload = self.nsx_rst_api.get(Virtualserver.ITEM_URI % (self.edge_id,
                                                               self.virtual_server_id))
        for spec in self.specs:
            if spec.update_attribute == "pool_hosts":
                """
                    self.specs must be data structure matching the typedAttribute on virtualServer
                """
                spec.pop("update_attribute")
                if isinstance(pload.virtualServer.vendorProfile, list):
                    for vendor in pload.virtualServer.vendorProfile:
                        if vendor.vendorTemplateId == self.vendor_profile_id:
                            vendor.vendorTables.rows.update(spec)
                            break
                else:
                    pload.virtualServer.vendorProfile.vendorTables.rows.update(spec)

            elif spec.update_attribute == "defaultPoolId":
                """
                    Update the virtual server
                """
                pload.virtualServer.defaultPoolId = spec.defaultPoolId

            else:
                raise NetxResourceError("cannot update virtual server with unknown attribute \n {0}"
                                        .format(spec))

        self.nsx_rst_api.put(Virtualserver.ITEM_URI % (self.edge_id, self.virtual_server_id),
                             payload=pload)


remove_virtual_server = None


class RemoveVirtualServer(NetxCommand):

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param virtual_server_id: virtual server name    #mandatory
    @type virtual_server_id: String

    @param pay_load: pay load to remove virtual server from load balancer service    #mandatory
    @type pay_load: Attrdict

    """

    def __init__(self,
                 edge_id,
                 virtual_server_id,
                 pay_load,
                 *args, **kwargs):
        super(RemoveVirtualServer, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.virtual_server_id = virtual_server_id
        self.pay_load = pay_load

    def setup(self):
        LOG.debug('Removing the virtual server = {0} from NSX'.format(self.virtual_server_id))
        try:
            self.nsx_rst_api.put(LoadBalancer.URI % self.edge_id, payload=self.pay_load)
        except NetxResourceError:
            pass
        wait(lambda: self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id),
             condition=lambda ret: ret.loadBalancer.virtualServer is None,
             progress_cb=lambda x: "Waiting to remove virtual server on nsx edge, id={0}".format(self.edge_id),
             timeout=20, interval=4,
             timeout_message="Virtual Server was not removed on edge, id={0}".format(self.edge_id))
        LOG.debug('Removed the virtual server = {0} from NSX'.format(self.virtual_server_id))

check_virtual_server = None


class CheckVirtualServer(NetxCommand):

    """

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param virtual_server_id: virtual server name    #mandatory
    @type virtual_server_id: String

    """

    def __init__(self,
                 edge_id,
                 virtual_server_id,
                 *args, **kwargs):
        super(CheckVirtualServer, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api
        self.virtual_server_id = virtual_server_id

    def setup(self):
        LOG.debug('Checking for the virtual server = {0} from NSX'.format(self.virtual_server_id))
        wait(lambda: self.nsx_rst_api.get(LoadBalancer.URI % self.edge_id),
             condition=lambda ret: ret.loadBalancer.virtualServer is None,
             progress_cb=lambda x: "Waiting to remove virtual server on edge, id={0}".format(self.edge_id),
             timeout=20, interval=4,
             timeout_message="Virtual Server was not removed on edge, id={0}".format(self.edge_id))
        LOG.debug('Removed the virtual server, id = {0} from NSX'.format(self.virtual_server_id))

create_undeployed_edge = None


class CreateUndeployedEdge(NetxCommand):
    DEFAULT_DIRECTORY = "/project_data/api/xml/"

    """ Creates edge in undeployed mode on NSX

    @param nsx_edge_id: NSX edge id #mandatory
    @type nsx_edge_id: String

    @param edge_name: Name of the edge to be created #mandatory
    @type edge_name: String

    @param template_name: Edge pay load template name    #mandatory only while creating NSX edge
    @type template_name: String

    @param template_format: referenced template format    # not mandatory and has a default value
    @type template_format: String

    """

    def __init__(self,
                 edge_name,
                 specs,
                 template_name,
                 template_format='xml',
                 *args, **kwargs):
        super(CreateUndeployedEdge, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_name = edge_name
        self.nsx = kwargs.pop('device')
        self.template_dir = specs.template_dir if specs.template_dir else self.DEFAULT_DIRECTORY
        self.template_name = template_name
        self.template_format = template_format
        self.specs = specs

    def setup(self):
            payload = Edges().from_file(self.template_dir, self.template_name, fmt=self.template_format)
            payload.edge.appliances.appliance.datastoreId = self.specs.datastoreId if self.specs.datastoreId else self.nsx.specs.datastore
            payload.edge.appliances.appliance.hostId = self.specs.hostId if self.specs.hostId else self.nsx.specs.hostId
            payload.edge.appliances.appliance.resourcePoolId = self.nsx.specs.resourcePool
            payload.edge.datacenterMoid = self.nsx.specs.datacenterMoid
            payload.edge.name = self.edge_name
            if self.specs.enable_ha:
                payload.edge.features.highAvailability.enabled = self.specs.enable_ha
            if self.specs.tenant:
                payload.edge.tenant = self.specs.tenant
            try:
                self.nsx_rst_api.post(Edges.URI, payload=payload)
                LOG.debug("created NSX {0} in undeployed mode".format(self.edge_name))
            except NetxResourceError:
                raise CommandError("failed to create a nsx edge in undeployed mode")

get_edge_id = None


class GetEdgeId(NetxCommand):

    """ Get's an edge on NSX

    @param edge_name: Name of the edge #mandatory
    @type edge_name: String

    @return edge_id: NSX edge id corresponding to edge_name
    @type: String

    """

    def __init__(self,
                 edge_name,
                 *args, **kwargs):
        super(GetEdgeId, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_name = edge_name

    def setup(self):
        edges = self.nsx_rst_api.get(Edges.URI)
        if edges.pagedEdgeList and edges.pagedEdgeList.edgePage and edges.pagedEdgeList.edgePage.edgeSummary:
            if isinstance(edges.pagedEdgeList.edgePage.edgeSummary, list):
                for es in edges.pagedEdgeList.edgePage.edgeSummary:
                    if es.name == self.edge_name:
                        return es.objectId
            else:
                es = edges.pagedEdgeList.edgePage.edgeSummary
                if es.name == self.edge_name:
                    return es.objectId
        else:
            raise AssertionError("The edge {0} was not found NSX.".format(self.edge_name))

check_edge = None


class CheckEdge(NetxCommand):

    """ Checks for an edge on NSX

    @param edge_id: edge Id on NSX #mandatory
    @type edge_id: String

    @return : True if edge is available on NSX
    @type: Boolean

    """

    def __init__(self,
                 edge_id,
                 *args, **kwargs):
        super(CheckEdge, self).__init__(*args, **kwargs)
        self.edge_id = edge_id
        self.nsx_rst_api = self.api

    def setup(self):
        edges = self.nsx_rst_api.get(Edges.URI)
        if edges.pagedEdgeList and edges.pagedEdgeList.edgePage and edges.pagedEdgeList.edgePage.edgeSummary:
            if isinstance(edges.pagedEdgeList.edgePage.edgeSummary, list):
                for es in edges.pagedEdgeList.edgePage.edgeSummary:
                    if es.objectId == self.edge_id:
                        return True
            else:
                es = edges.pagedEdgeList.edgePage.edgeSummary
                if es.objectId == self.edge_id:
                    return True
        else:
            return False

delete_edge = None


class DeleteEdge(NetxCommand):

    """ Deletes an edge on NSX

    @return edge_id: NSX edge id
    @type: String

    """

    def __init__(self,
                 edge_id,
                 *args, **kwargs):
        super(DeleteEdge, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.edge_id = edge_id

    def check(self, edges):
        if edges and edges.pagedEdgeList and edges.pagedEdgeList.edgePage and edges.pagedEdgeList.edgePage.edgeSummary:
            if isinstance(edges.pagedEdgeList.edgePage.edgeSummary, list):
                for es in edges.pagedEdgeList.edgePage.edgeSummary:
                    if es.objectId == self.edge_id:
                        return False
            else:
                es = edges.pagedEdgeList.edgePage.edgeSummary
                if es.objectId == self.edge_id:
                    return False
        return True

    def setup(self):
        try:
            self.nsx_rst_api.delete(Edges.ITEM_URI % self.edge_id)
        except NetxResourceError:
            pass
        wait_args(self.check, func_args=[self.nsx_rst_api.get(Edges.URI)],
                  condition=lambda x: x,
                  progress_cb=lambda x: "Waiting for edge, id={0} to be deleted".format(self.edge_id),
                  timeout=20, interval=4,
                  timeout_message="edge, id={0} could not be deleted".format(self.edge_id))

get_next_datastore = None


class GetNextDatastore(NetxCommand):

    """ To calculate free space on all data stores and get the largest

    @return datastore_id: ESXi DataStore id
    @type: String

    """

    def __init__(self,
                 *args, **kwargs):
        super(GetNextDatastore, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.nsx = kwargs.pop('device')  # Get the NSX device object
        self.esxi_summary = Options()

    def setup(self):
        try:
            connect.ssl.CERT_REQUIRED = False
            vcenter = connect.SmartConnect(host=self.nsx.specs.vcenter_address,
                                           user=self.nsx.specs.vcenter_username,
                                           pwd=self.nsx.specs.vcenter_password,
                                           port=443)
            if not vcenter:
                self.fail("Could not connect to the vcenter {0} using specified "
                          "username and password".format(self.nsx.specs.vcenter_address))

            atexit.register(connect.Disconnect, vcenter)

            content = vcenter.RetrieveContent()
            # Search for all ESXi hosts
            objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                              [pyVmomi.vim.HostSystem],
                                                              True)
            esxi_hosts = objview.view
            objview.Destroy()

            for esxi_host in esxi_hosts:
                per_esxi_datastores = []
                datastore_obj = Options()
                storage_system = esxi_host.configManager.storageSystem
                host_volume_info = storage_system.fileSystemVolumeInfo.mountInfo
                # Map all file systems
                for host_mount_info in host_volume_info:
                    # Extract only VMFS volumes
                    if host_mount_info.volume.type == "VMFS":
                        datastore_obj.capacity = int(host_mount_info.volume.capacity)
                        datastore_obj.name = str(host_mount_info.volume.name)
                        datastore_obj.associated_host_name = esxi_host._GetMoId()
                        datastore_obj.associated_host_address = str(esxi_host.name)
                        datastore_obj.freespace, datastore_obj.id = self.get_datastore_summary(esxi_host.datastore, str(host_mount_info.volume.name))
                        LOG.debug(" \n host {0} \n , \n datastore info: \n {1} \n ".format(esxi_host.name, datastore_obj))
                    else:
                        continue

                    per_esxi_datastores.append(copy.deepcopy(datastore_obj))

                # associate ESXi host with the datastore
                self.esxi_summary[esxi_host.name] = per_esxi_datastores

            return self.get_largest_datastore()

        except pyVmomi.vmodl.MethodFault as error:
            raise Exception("Caught vmodl fault : " + error.msg)

    def get_datastore_summary(self, esxi_datastores, ds_name):
        """
            For a give data store, get the current free space.
        """
        for ds in esxi_datastores:
            if ds.summary.name == ds_name:
                return (int(ds.summary.freeSpace), str(ds._GetMoId()))
        raise Exception("datastore moid not found on vcenter for {0}".format(ds_name))

    def get_largest_datastore(self):
        datastores = []
        for esxi_name in list(self.esxi_summary.keys()):
            """
                 get all datastores on esxi. The datastore obj has association with host identifier
            """
            if isinstance(self.esxi_summary[esxi_name], list):
                for ds in self.esxi_summary[esxi_name]:
                    datastores.append(ds)
            else:
                datastores.append(self.esxi_summary[esxi_name])

        return (sorted(datastores, key=itemgetter('freespace'), reverse=True)[0])

get_vm = None


class GetVM(NetxCommand):

    """ To return the VM object when found on vcenter

    @return datastore_id: ESXi DataStore id
    @type: String

    """

    def __init__(self,
                 vm_id,
                 *args, **kwargs):
        super(GetVM, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.vm_id = vm_id
        self.nsx = kwargs.get('device')    # Get the NSX device object

    def prep(self):
        pass

    def setup(self):
        try:
            connect.ssl.CERT_REQUIRED = False
            vcenter = connect.SmartConnect(host=self.nsx.specs.vcenter_address,
                                           user=self.nsx.specs.vcenter_username,
                                           pwd=self.nsx.specs.vcenter_password,
                                           port=443)
            if not vcenter:
                self.fail("Could not connect to the vcenter {0} using specified "
                          "username and password".format(self.nsx.specs.vcenter_address))

            atexit.register(connect.Disconnect, vcenter)

            content = vcenter.RetrieveContent()
            # Search for all ESXi hosts
            objView = content.viewManager.CreateContainerView(content.rootFolder,
                                                              [pyVmomi.vim.VirtualMachine],
                                                              True)
            vmList = objView.view
            objView.Destroy()
            return [vm._moId for vm in vmList if vm._moId == self.vm_id]

        except pyVmomi.vmodl.MethodFault as e:
            print(("Caught vmodl fault : " + e.msg))
        except Exception as e:
            print(("Caught pyvmomi exception : " + str(e)))

product_full_name = None


class ProductFullName(NetxCommand):

    """
        This class returns vCenter server system information
    """

    def __init__(self,
                 *args, **kwargs):
        super(ProductFullName, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.nsx = kwargs.get('device')    # Get the NSX device object

    def prep(self):
        pass

    def setup(self):
        try:
            connect.ssl.CERT_REQUIRED = False
            vcenter = connect.SmartConnect(host=self.nsx.specs.vcenter_address,
                                           user=self.nsx.specs.vcenter_username,
                                           pwd=self.nsx.specs.vcenter_password,
                                           port=443)
            if not vcenter:
                self.fail("Could not connect to the vcenter {0} using specified "
                          "username and password".format(self.nsx.specs.vcenter_address))

            atexit.register(connect.Disconnect, vcenter)

            content = vcenter.RetrieveContent()
            return content.about.fullName

        except pyVmomi.vmodl.MethodFault as e:
            print(("Caught vmodl fault : " + e.msg))
        except Exception as e:
            print(("Caught pyvmomi exception : " + str(e)))

uninstall_cluster = None


class UninstallCluster(NetxCommand):
    """man Uninstall BIGIP HA cluster from NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    """

    def __init__(self,
                 service_instance_id,
                 *args, **kwargs):
        super(UninstallCluster, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.nsx = kwargs.get('device')    # Get the NSX device object

    def setup(self):

        def is_cluster_uninstalled(ret):
            if ret and ret.serviceInstanceRuntimeInfos and ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                for sir in ret.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                    if (sir.status == "NEEDS_ATTENTION" or
                        sir.installState == 'DISABLED' or
                            sir.installState == 'ENABLED'):
                        # issue UNINSTALL command again
                        self.nsx_rst_api.post(Runtime.CONFIG_URI %
                                              (self.service_instance_id, sir.id),
                                              params_dict={'action': 'uninstall'})
                    elif (sir.status == "OUT_OF_SERVICE" and
                          sir.installState == "NOT_INSTALLED"):
                        return True
            return True

        runtimes = self.nsx_rst_api.get(Runtime.URI % (self.service_instance_id))
        if runtimes and runtimes.serviceInstanceRuntimeInfos and runtimes.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
            for sir in runtimes.serviceInstanceRuntimeInfos.serviceInstanceRuntimeInfo:
                LOG.debug("Uninstalling runtime id = {0} on NSX".format(sir.id))
                try:
                    self.nsx_rst_api.post(Runtime.CONFIG_URI %
                                          (self.service_instance_id, sir.id),
                                          params_dict={'action': 'uninstall'})

                    if sir.runtimeInstanceId:
                        # This will not be true for adding existing BIGIP to NSX case
                        # Check with vcenter if the VM is deleted on HOST
                        wait(lambda: GetVM(vm_id=sir.runtimeInstanceId, device=self.nsx).run(),
                             condition=lambda VMobj: len(VMobj) == 0,
                             progress_cb=lambda x: "Waiting on vcenter to delete = {0}".format(sir.runtimeInstanceId),
                             timeout=60, interval=5,
                             timeout_message="VM = {0} not deleted on vcenter".format(sir.runtimeInstanceId))
                except NetxResourceError:
                    pass    # Issue UNINSTALL command only once

            wait(lambda: self.nsx_rst_api.get(Runtime.ITEM_URI % (self.service_instance_id, sir.id)),
                 condition=is_cluster_uninstalled,
                 progress_cb=lambda x: "Waiting for HA cluster to uninstall on {0}".format(self.service_instance_id),
                 timeout=60, interval=5,
                 timeout_message="HA cluster not removed on {0}".format(self.service_instance_id))

uninstall_runtime_on_cluster = None


class UninstallRuntimeOnCluster(NetxCommand):
    """ Uninstall service runtime on a HA cluster from NSX

    @param service_instance_id: Service instance Id #mandatory
    @type service_instance_id: string

    @param service_runtime_id: Service Runtime Id #mandatory
    @type service_runtime_id: string

    """

    def __init__(self,
                 service_instance_id,
                 service_runtime_id,
                 *args, **kwargs):
        super(UninstallRuntimeOnCluster, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.service_instance_id = service_instance_id
        self.service_runtime_id = service_runtime_id
        self.nsx = kwargs.get('device')

    def setup(self):

        def wait_on_uninstall(sid, srid):
            ret = self.nsx_rst_api.get(Runtime.ITEM_URI %
                                       (self.service_instance_id,
                                        self.service_runtime_id))
            if ret and ret.serviceInstanceRuntimeInfo \
                    and ret.serviceInstanceRuntimeInfo.installState == 'NOT_INSTALLED':
                        return True
            return False

        LOG.debug("Uninstalling runtime id = {0} on NSX".format(self.service_runtime_id))
        try:
            sir = self.nsx_rst_api.get(Runtime.ITEM_URI %
                                       (self.service_instance_id,
                                        self.service_runtime_id))
            self.nsx_rst_api.post(Runtime.CONFIG_URI
                                  % (self.service_instance_id,
                                     self.service_runtime_id),
                                  params_dict={'action': 'uninstall'})

            if sir.runtimeInstanceId:
                # This will not be true for adding existing BIGIP to NSX case
                # Check with vcenter if the VM is deleted on HOST
                wait(lambda: GetVM(vm_id=sir.runtimeInstanceId, device=self.nsx).run(),
                     condition=lambda VMobj: len(VMobj) == 0,
                     progress_cb=lambda x: "Waiting on vcenter to delete = {0}".format(sir.runtimeInstanceId),
                     timeout=60, interval=5,
                     timeout_message="VM = {0} not deleted on vcenter".format(sir.runtimeInstanceId))

        except NetxResourceError:
            pass    # ignore on error as on return we check for uninstall state else fail
        wait_args(wait_on_uninstall,
                  func_args=[self.service_instance_id, self.service_runtime_id],
                  condition=lambda ret: ret,
                  progress_cb=lambda x: "Waiting for runtime id={0} to uninstall".format(self.service_runtime_id),
                  timeout=20, interval=5,
                  timeout_message="runtime, id={0} could not be uninstalled".format(self.service_runtime_id))

connect_to_vcenter = None


class ConnectToVcenterServer(NetxCommand):
    """
        # This class return the vCenter Server content object
        # content object holds the complete view of vCenter server
    """

    def __init__(self,
                 nsx_device,
                 *args, **kwargs):
        super(ConnectToVcenterServer, self).__init__(*args, **kwargs)
        self.__nsx = nsx_device
        self._vcenterContent = None

    def prep(self):
        pass

    def setup(self):
        try:
            connect.ssl.CERT_REQUIRED = False
            vcenter = connect.SmartConnect(host=self.__nsx.specs.vcenter_address,
                                           user=self.__nsx.specs.vcenter_username,
                                           pwd=self.__nsx.specs.vcenter_password,
                                           port=443)
            if not vcenter:
                self.fail("Could not connect to the vcenter {0} using specified "
                          "username and password".format(self.nsx.specs.vcenter_address))

            atexit.register(connect.Disconnect, vcenter)

            self._vcenterContent = vcenter.RetrieveContent()
            return self.get_vCenter_content()

        except pyVmomi.vmodl.MethodFault as e:
            print(("Caught vmodl fault : " + e.msg))
        except Exception as e:
            print(("Caught pyvmomi exception : " + str(e)))

    def get_vCenter_content(self):
        return self._vcenterContent

get_data_center = None


class GetDataCenter(NetxCommand):
    """
        This class gives the ESXI Name given the physical host
    """

    def __init__(self,
                 host,
                 *args, **kwargs):
        super(GetDataCenter, self).__init__(*args, **kwargs)
        self.nsx_rst_api = self.api
        self.__host = host
        self.__nsx = kwargs.pop('device')    # Get the NSX device object

    def setup(self):
        try:
            content = ConnectToVcenterServer(self.__nsx).run()

            # Search for all ESXi hosts
            objview = content.viewManager.CreateContainerView(content.rootFolder,
                                                              [pyVmomi.vim.Datacenter],
                                                              True)
            datacenter_view = objview.view

            for dc in datacenter_view:
                return dc

        except pyVmomi.vmodl.MethodFault as error:
            raise Exception("Caught vmodl fault : " + error.msg)
