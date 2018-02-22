'''
Created on Jan 9, 2014

/mgmt/[cm|tm]/cloud workers

@author: jono
'''
from .....base import AttrDict
from .....defaults import ADMIN_USERNAME, ADMIN_PASSWORD
from .base import Reference, ReferenceList, Task, DEFAULT_TIMEOUT
from .shared import DeviceResolver
from ...base import BaseApiObject
from .....utils.wait import wait


class Account(AttrDict):
    def __init__(self, *args, **kwargs):
        super(Account, self).__init__(*args, **kwargs)
        self.setdefault('userName', '')
        self.setdefault('roleName', '')


class ManagedDeviceCloud(AttrDict):
    URI = '/mgmt/cm/cloud/managed-devices'
    PENDING_STATES = ('PENDING', 'PENDING_DELETE',
                      'FRAMEWORK_DEPLOYMENT_PENDING', 'TRUST_PENDING',
                      'CERTIFICATE_INSTALL')

    def __init__(self, *args, **kwargs):
        super(ManagedDeviceCloud, self).__init__(*args, **kwargs)
        self.setdefault('deviceAddress', '')
        self.setdefault('username', ADMIN_USERNAME)
        self.setdefault('password', ADMIN_PASSWORD)


class Connector(Task):
    # Keep minimium required only. Do not modify this class here.
    URI = '/mgmt/cm/cloud/connectors/%s'  # connector type
    ITEM_URI = URI + '/%s'    # connector type/ id
    ITEM_STATS_URI = ITEM_URI + '/stats'    # connector type/ id
    CONFIGURE_HA_TASK_URI = "/mgmt//cm/cloud/tasks/configure-ha-devices"
    CONFIGURE_HA_TASK_ITEM_URI = "/mgmt//cm/cloud/tasks/configure-ha-devices/%s"
    CONFIGURE_DEVICE_NODE_TASK_URI = "/mgmt//cm/cloud/tasks/configure-device-node"

    # Service instance POJO on NSX connector
    SERVICE_INSTANCE_URI = ITEM_URI % ("vmware-nsx", "%s") + "/service-instances"
    SERVICE_INSTANCE_ITEM_URI = SERVICE_INSTANCE_URI + "/%s"
    SERVICE_RUNTIME_URI = SERVICE_INSTANCE_ITEM_URI + "/service-runtimes"
    SERVICE_RUNTIME_ITEM_URI = SERVICE_RUNTIME_URI + "/%s"

    def __init__(self, *args, **kwargs):
            super(Connector, self).__init__(*args, **kwargs)
            self.setdefault('name', 'test')
            self.setdefault('cloudConnectorReference', Reference())
            self.setdefault('parameters', [])

    @staticmethod
    def wait(rest, connector, timeout=DEFAULT_TIMEOUT, interval=1):
        selflink = connector.selfLink if isinstance(connector, dict) \
            else connector

        ret = wait(lambda: rest.get(selflink + '/stats'),
                   condition=lambda ret: ret.entries['health.summary'].value != 0.5,
                   progress_cb=lambda ret: 'Waiting for connector health...',
                   timeout=timeout, interval=interval)

        if ret.entries['health.summary'].value != 1:
            Task.fail("Connector creation failed", ret)

        return ret


class Tenant(BaseApiObject):
    # Keep minimium required only. Do not modify this class here.
    URI = '/mgmt/cm/cloud/tenants'
    ITEM_URI = '/mgmt/cm/cloud/tenants/%s'
    # TODO: Remove this and use UserCredentialData.URI instead
    userReferenceURI = '/mgmt/shared/authz/users'

    def __init__(self, *args, **kwargs):
        super(Tenant, self).__init__(*args, **kwargs)
        self.setdefault('name', 'tenant')


class TenantPlacement(BaseApiObject):
    URI = '/mgmt/cm/cloud/tenants/services/placements'

    def __init__(self, *args, **kwargs):
        super(TenantPlacement, self).__init__(*args, **kwargs)
        self.setdefault('tenant', 'tenant')
        self.setdefault('iAppTemplate', '')


class TenantServiceProperties(AttrDict):
    def __init__(self, *args, **kwargs):
        super(TenantServiceProperties, self).__init__(*args, **kwargs)
        self.setdefault('id', 'cloudConnectorReference')
        self.setdefault('value', '')


class TenantServiceVarItem(AttrDict):
    def __init__(self, *args, **kwargs):
        super(TenantServiceVarItem, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('value', '')


class TenantServiceTableItem(AttrDict):
    def __init__(self, *args, **kwargs):
        super(TenantServiceTableItem, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('columns', [])
        self.setdefault('rows', [])


class TenantService(Task):
    URI = Tenant.URI + '/%s/services/iapp'
    TenantTemplateReferenceURI = '/mgmt/cm/cloud/tenant/templates/iapp'
    ITEM_URI = Tenant.URI + '/%s/services/iapp/%s'

    def __init__(self, *args, **kwargs):
        super(TenantService, self).__init__(*args, **kwargs)
        self.setdefault('name', 'tenant-service')
        self.setdefault('tenantTemplateReference', Reference())
        self.setdefault('tenantReference', Reference())
        self.setdefault('vars', [])
        self.setdefault('tables', [])
        self.setdefault('properties', [])

    @staticmethod
    def wait(rest, tenant, service, health_stats="MINIMUM", *args, **kwargs):
        '''
            @param rest: the REST interface to use
            @type rest: icontrol rest interface
            @param tenant: the tenant that is being used
            @type tenant: str
            @param service: the iApp name
            @type service: str
            @param health_stats: What health stats to check. Defaults to just
                                 health.summary.placement
            @type health_stats: If argument is something other then MINIMUM,
                                check all health related stats.
        '''
        from .....commands.rest.device import DEFAULT_ALLBIGIQS_GROUP, DEFAULT_ALLBIGIQS_GROUP_OR

        # If we use fake nodes as web servers, health.summary will return a legit error message
        # Upon using fake nodes consider only health.summary.placement

        health_stats = ["health.summary.placement"] if health_stats == "MINIMUM"\
            else ["health.app", "health.placement", "health.summary",
                  "health.summary.app", "health.summary.placement"]

        def is_done(ret):
            # Need to wait until the key we are looking for populates on BIG-IQ
            import logging
            LOG = logging.getLogger(__name__)
            LOG.debug("Current stats: {}".format(ret.entries.keys()))
            for stat in health_stats:
                if stat not in ret.entries.keys():
                    return False

            resp = []
            for key in ret.entries.keys():
                if key in health_stats and not ret.entries[key].value.is_integer():
                    resp.append(ret.entries[key])
            return len(resp) == 0

        ret = wait(lambda: rest.get(TenantService.ITEM_URI % (tenant, service) + '/stats'),
                   condition=is_done,
                   progress_cb=lambda ret: 'Waiting until iApp is placed...',
                   *args, **kwargs)

        for key in ret.entries.keys():
            if key in health_stats and ret.entries[key].value != 1:
                resp = rest.get(TenantPlacement.URI)
                # The above URI can return a huge response. Below will show
                # response from the item of interest.
                for item in resp['items']:
                    if service in item.appName:
                        Task.fail("iApp deploy failed", rest.get(item.selfLink))
        return ret


class TenantServiceServerTiersInfoItem(AttrDict):
    def __init__(self, *args, **kwargs):
        super(TenantServiceServerTiersInfoItem, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('nodeTemplateReference', Reference())


class PolicyThresholdsItem(AttrDict):
    def __init__(self, *args, **kwargs):
        super(PolicyThresholdsItem, self).__init__(*args, **kwargs)
        self.setdefault('statType', '')
        self.setdefault('statName', '')
        self.setdefault('thresholdOperator', '')
        self.setdefault('thresholdLevel', '')
        self.setdefault('thresholdFactor', '')


class TenantServiceServerTiersPoliciesItem(AttrDict):
    def __init__(self, *args, **kwargs):
        super(TenantServiceServerTiersPoliciesItem, self).__init__(*args, **kwargs)
        self.setdefault('associatedServerTier', '')
        self.setdefault('minNumberOfNodes', '1')
        self.setdefault('maxNumberOfNodes', '3')
        self.setdefault('thresholds', [])


class TenantServiceWithPolicy(TenantService):
    def __init__(self, *args, **kwargs):
        super(TenantServiceWithPolicy, self).__init__(*args, **kwargs)
        self.setdefault('serverTiersInfo', [])
        self.setdefault('elasticityPolicy', AttrDict(serverTierPolicies=[]))


class TenantActivities(AttrDict):
    URI = Tenant.ITEM_URI + '/activities'
    ITEM_URI = Tenant.ITEM_URI + '/activities/%s'

    def __init__(self, *args, **kwargs):
        super(TenantActivities, self).__init__(*args, **kwargs)
        self.setdefault('activity', '')
        self.setdefault('resourceReferences', ReferenceList())
        self.setdefault('title', '')
        self.setdefault('message', '')


class TenantVirtualServers(AttrDict):
    URI = Tenant.ITEM_URI + '/virtual-servers'


class EventAnalyzerHistogramsItem(AttrDict):

    def __init__(self, *args, **kwargs):
        super(EventAnalyzerHistogramsItem, self).__init__(*args, **kwargs)
        self.setdefault('eventFilter', '')
        self.setdefault('mode', 'MAX')
        self.setdefault('selectionQueryType', 'ODATA')
        self.setdefault('timestampEventProperty', 'lastUpdateMicros')
        self.setdefault('sourceEventProperty', 'value')
        self.setdefault('description', '')
        self.setdefault('isRelativeToNow', True)
        self.setdefault('timeUpperBoundMicrosUtc', '1384289713791770')
        self.setdefault('durationTimeUnit', 'SECONDS')
        self.setdefault('durationLength', 300)
        self.setdefault('nBins', 10)


class EventAnalyzer(BaseApiObject):
    URI = '/mgmt/cm/cloud/tenants/%s/event-analyzers'

    def __init__(self, *args, **kwargs):
        super(EventAnalyzer, self).__init__(*args, **kwargs)
        self.setdefault('name', 'myEventAnalyzer')
        self.setdefault('targetReference', Reference())
        self.setdefault('cloudConnectorReference', Reference())
        self.setdefault('input', AttrDict(histograms=[]))


class IappTemplateProperties(AttrDict):

    def __init__(self, *args, **kwargs):
        super(IappTemplateProperties, self).__init__(*args, **kwargs)
        self.setdefault('id', 'cloudConnectorReference')
        self.setdefault('displayName', 'Cloud Connector')
        self.setdefault('isRequired', True)
        # self.setdefault('provider', '')
        self.setdefault('defaultValue', '')


class NsxNodeTemplate(BaseApiObject):

    def __init__(self, *args, **kwargs):
        super(NsxNodeTemplate, self).__init__(*args, **kwargs)
        self.setdefault('state', 'TEMPLATE')
        self.setdefault('properties', [])


class NsxServiceRuntimes(Task):
    PENDING = ('POST_INSTALL_CMD', 'WAIT_FOR_PUT_WITH_ENABLED_STATE', 'GET_CONNECTOR',
               'CHECK_SUBNETS', 'CREATE_SUBNETS', 'GET_DHCP_IP',
               'FIND_NODE_TEMPLATE', 'CREATE_NODE', 'LOCATE_DEVICE_CONFIG_TASK',
               'REPORT_ACTIVITY', 'AWAITING_DEVICE_CONFIG',
               'GET_DEVICE_REF_FROM_NODE', 'ADD_DEVICE_REF_TO_NETWORK',
               'CREATE_VCENTER_SESSION')

    def __init__(self, *args, **kwargs):
        super(NsxNodeTemplate, self).__init__(*args, **kwargs)

    def show_runtime_progress(self, ret):
            if ret and ret.taskState:
                return ret.taskState.createBigIpNextStep
            else:
                return "No progress seen on API"

    @staticmethod
    def wait(rest, connector, service_inst, runtime, timeout=1800, interval=30):
        conn_id = connector.connectorId if connector.connectorId else connector

        ret = wait(lambda: rest.get(Connector.SERVICE_RUNTIME_ITEM_URI %
                                    (conn_id, service_inst, runtime)),
                   condition=lambda ret: ret.taskState.createBigIpNextStep
                   not in NsxServiceRuntimes.PENDING,
                   progress_cb=lambda ret: 'BIGIP runtime state: {0}'
                   .format(ret.taskState.createBigIpNextStep
                           if ret and ret.taskState else "NONE"),
                   timeout=timeout, interval=interval)

        if ret.taskState.createBigIpNextStep != 'SUCCESS':
            Task.fail("BIGIP deploy failed", ret)

        return ret


class IappTemplate(BaseApiObject):
    URI = '/mgmt/cm/cloud/provider/templates/iapp'
    ITEM_URI = '/mgmt/cm/cloud/provider/templates/iapp/%s'
    HTTP_EXAMPLE = '/mgmt/cm/cloud/templates/iapp/f5.http/providers/example'
    HTTP_OFFLOAD_EXAMPLE = '/mgmt/cm/cloud/templates/iapp/f5.http/providers/f5.http:ssl-offload'
    EXAMPLE_URI = '/mgmt/cm/cloud/templates/iapp/%s/providers/example'

    class Variable(AttrDict):
        def __init__(self, *args, **kwargs):
            super(IappTemplate.Variable, self).__init__(*args, **kwargs)
            self.setdefault('name', 'foo')
            self.setdefault('provider', 'bar')
            self.setdefault('providerType', None)
            self.setdefault('isRequired', True)

    class Table(AttrDict):
        def __init__(self, *args, **kwargs):
            super(IappTemplate.Table, self).__init__(*args, **kwargs)
            self.setdefault('name', 'iapp_table')
            self.setdefault('columns', [])

    def __init__(self, *args, **kwargs):
        super(IappTemplate, self).__init__(*args, **kwargs)
        self.setdefault('templateName', 'template')
        self.setdefault('parentReference', Reference())
        self.setdefault('overrides', AttrDict(vars=[], tables=[]))
        self.setdefault('properties', [])


class ConnectorProperty(AttrDict):
    def __init__(self, *args, **kwargs):
        super(ConnectorProperty, self).__init__(*args, **kwargs)
        self.setdefault('id', '')
        self.setdefault('displayName', '')
        self.setdefault('isRequired', True)
        self.setdefault('value', '')


class CloudNode(BaseApiObject):
    URI = '/mgmt/cm/cloud/connectors/%s/%s/nodes'

    def __init__(self, *args, **kwargs):
            super(CloudNode, self).__init__(*args, **kwargs)
            self.setdefault('state', 'PENDING')
            self.setdefault('cloudConnectorReference', Reference())
            self.setdefault('properties', [])
            self.setdefault('networkInterfaces', [])
            self.setdefault('services', [])
            self.setdefault('dnsServers', [])
            self.setdefault('dnsSuffixes', [])
            self.setdefault('ntpServers', [])


class CloudNodeBIGIP(BaseApiObject):
    URI = '/mgmt/cm/cloud/connectors/%s/nodes/%s'

    def __init__(self, *args, **kwargs):
            super(CloudNodeBIGIP, self).__init__(*args, **kwargs)
            self.setdefault('cloudConnectorReference', Reference())
            self.setdefault('properties', [])


class CloudNodeProperty(AttrDict):
    def __init__(self, *args, **kwargs):
        super(CloudNodeProperty, self).__init__(*args, **kwargs)
        self.setdefault('id', '')
        self.setdefault('value', '')


class ConfigureDeviceNode(Task):
    URI = '/mgmt/cm/cloud/tasks/configure-device-node'
    ITEM_URI = '/mgmt/cm/cloud/tasks/configure-device-node/%s'  # node
    PENDING_STATUS = ('VALIDATE_NODE', 'GET_CONFIG_FROM_CONNECTOR', 'GET_NETWORK',
                      'GET_SUBNETS', 'CONSTRUCT_NETWORK_CONFIG',
                      'AWAITING_HEALTHY_NODE', 'AWAITING_DEVICE_CONTROL_PLANE',
                      'RESET_DEVICE_CONFIG', 'CONFIGURING_DEVICE',
                      'AWAITING_MANAGED_DEVICE', 'SECURE_ROOT_LOGIN',
                      'LICENSE_DEVICE', 'AWAITING_LICENSED_DEVICE',
                      'ASSOCIATE_DEVICE_WITH_CONNECTOR')

    def __init__(self, *args, **kwargs):
            super(ConfigureDeviceNode, self).__init__(*args, **kwargs)

    @staticmethod
    def wait(rest, pre_items, timeout=1200):

        wait(lambda: rest.get(ConfigureDeviceNode.URI),
             condition=lambda x: len(x['items']) > len(pre_items),
             progress_cb=lambda x: 'Waiting for new item to populate: {0} > {1}'.format(len(x['items']), len(pre_items)),
             timeout=300, interval=30, timeout_message='ConfigureDeviceNode did not start.')

        resp = rest.get(ConfigureDeviceNode.URI)['items']
        new_items = [x for x in resp if x.id not in [y.id for y in pre_items]]

        for item in new_items:
            ret = wait(lambda: rest.get(item.selfLink),
                       condition=lambda ret: ret.currentStep not in ConfigureDeviceNode.PENDING_STATUS,
                       progress_cb=lambda ret: 'Status: {0}'.format(ret.currentStep),
                       timeout=timeout, interval=60,
                       timeout_message='ConfigureDeviceNode timed out.')

            if sum(1 for x in ret) != (len(new_items) + len(pre_items)) \
               or ret.currentStep != 'SUCCESS':
                Task.fail("ConfigureDeviceNode failed", ret)

        return rest.get(ConfigureDeviceNode.URI)


class AutoDeployDevice(Task):
    URI = '/mgmt/cm/cloud/tasks/auto-deploy-device'
    PENDING_STATUS = ('LOCATE_DEVICE_CONFIG_TASK', 'FIND_DEVICE_TEMPLATE', 'POST_DEVICE_NODE', 'AWAITING_DEVICE_CONFIG',
                      'RESTARTING_PENDING_PLACEMENTS')

    @staticmethod
    def wait(rest, pre_items, timeout=1200):

        wait(lambda: rest.get(AutoDeployDevice.URI),
             condition=lambda x: len(x['items']) > len(pre_items),
             progress_cb=lambda x: 'Waiting for new item to populate: {0} > {1}'.format(len(x['items']), len(pre_items)),
             timeout=300, interval=30, timeout_message='Autodeployment did not start')

        resp = rest.get(AutoDeployDevice.URI)['items']
        new_items = [x for x in resp if x.id not in [y.id for y in pre_items]]

        for item in new_items:
            ret = wait(lambda: rest.get(item.selfLink),
                       condition=lambda ret: ret.currentStep not in AutoDeployDevice.PENDING_STATUS,
                       progress_cb=lambda ret: 'Status: {0}'.format(ret.currentStep),
                       timeout=timeout, interval=60,
                       timeout_message='Autodeployment timed out.')

            resp = rest.get(AutoDeployDevice.URI)['items']
            if sum(1 for x in resp) != (len(new_items) + len(pre_items)) \
               or ret.currentStep != 'SUCCESS':
                Task.fail("Autodeploy failed", ret)

        return resp


class ProviderActivities(AttrDict):
    URI = '/mgmt/cm/cloud/provider/activities'
    ITEM_URI = '/mgmt/cm/cloud/provider/activities/%s'

    def __init__(self, *args, **kwargs):
        super(ProviderActivities, self).__init__(*args, **kwargs)
        self.setdefault('activity', '')
        self.setdefault('resourceReferences', ReferenceList())
        self.setdefault('title', '')
        self.setdefault('message', '')


class VcmpGuest(AttrDict):
    """VCMPguest class to create a payload to create guests"
    """
    COLLECTION_URI = "/mgmt/cm/cloud/connectors/vcmp/%s/nodes"
    ITEM_URI = "/mgmt/cm/cloud/connectors/vcmp/%s/nodes/%s"

    def __init__(self, *args, **kwargs):
        super(VcmpGuest, self).__init__(*args, **kwargs)

        self.setdefault('ipAddress', '10.10.10.10/24')
        self.setdefault('providerOnly', True)
        self.setdefault('properties', [])
        self.setdefault('networkInterfaces', [])
        self.init_default_properties()
        self.init_default_interfaces()

    def init_default_properties(self):
        """ Setting up the the default config properties and interfaces"""
        # All the below properties required exceptt the slots optional
        self.add_property("NodeName", "DefaultGuest")
        self.add_property("DeviceHostname", "DefaultGuest.hostname.com")
        self.add_property("NodeTemplateName", "BIGIP-12.6.0.0.0.401.iso")
        self.add_property("HotFix", "")
        self.add_property("RequestedState", "deployed")
        self.add_property("DeviceMgmtUser", "admin")
        self.add_property("DeviceMgmtPassword", "admin")
        self.add_property("NumberOfCoresPerSlot", "2")
        self.add_property("Slots", "1")
        self.add_property("DeviceCreatedWithDefaultCredentials", "true")
        self.add_property("DeviceLeaveRootLoginEnabled", "true")

    def init_default_interfaces(self):
        # All the below interfaces are required
        self.add_localInterface("192.168.0.1", "192.168.0.254", "192.168.0.0/24")
        self.add_vlanInterface("internal", "10.10.200.1", "10.10.0.0/24")

    def add_property(self, name, value):
        """Method to create a property and assign it a value
        @param name: name of the property ->id
        @param value: value of that property -> value
        @return: None
         """
        new_property = AttrDict()
        new_property['id'] = name
        new_property['value'] = value
        self['properties'].append(new_property)

    def set_property(self, name, value):
        """Method to set a property value
        @param name: name of the property ->id
        @param value: value of that property -> value
        @return: True if modified, False if added
        """
        for n, each in enumerate(self['properties']):
            if each['id'] == name:
                self['properties'][n]['value'] = value
                return True
        self.add_property(name, value)
        return False

    def set_properties(self, adict):
        """Method to set many properties at once
        @param adict: a dictionary with all the properties needed to be set
        @return: None
        """
        assert isinstance(adict, dict)
        for key, value in adict.iteritems():
            self.set_property(key, value)
#        for n, each in enumerate(self['properties']):
#            value = adict.get(each['id'], None)
#            if value is not None:
#                self['properties'][n]['value'] = value

    def add_localInterface(self, laddr, gwaddr, subaddr):
        """Method to create local interface and assign it a value
        @param laddr: local address ipv4 format
        @param gwaddr: gateway address ipv4 format
        @param subaddr: subnet mask ipv4 format/netmask
        @return: None
         """
        # we may assert valid_ip(laddr) however no need
        new_item = AttrDict()
        new_item['localAddress'] = laddr
        new_item['gatewayAddress'] = gwaddr
        new_item['subnetAddress'] = subaddr
        self['networkInterfaces'].append(new_item)

    def add_vlanInterface(self, vname, vladdr, vsubaddr):
        new_item = AttrDict()
        new_item['name'] = vname
        new_item['localAddress'] = vladdr
        new_item['subnetAddress'] = vsubaddr
        self['networkInterfaces'].append(new_item)

    def set_localInterface(self, laddr, gwaddr, subaddr):
        for n, each in enumerate(self['networkInterfaces']):
            if each.get('gatewayAddress', False):
                self['networkInterfaces'].__delitem__(n)
                break
        self.add_localInterface(laddr, gwaddr, subaddr)

    def set_VlanInterface(self, vname, vladdr, vsubaddr):
        for n, each in enumerate(self['networkInterfaces']):
            if each.get('gatewayAddress', False):
                self['networkInterfaces'].__delitem__(n)
                break
        self.add_vlanInterface(vname, vladdr, vsubaddr)

    def set_networkInterface(self, interfaces_list):
        for new_int in interfaces_list:
            if 'mgmt' == new_int['name']:
                self['networkInterfaces'][0]['gatewayAddress'] = new_int['gateway']
                self['networkInterfaces'][0]['localAddress'] = new_int['local']
                self['networkInterfaces'][0]['subnetAddress'] = new_int['subnet']
            else:
                target = -1
                for n, interface in enumerate(self['networkInterfaces']):
                    if new_int['name'] == interface.get('name', False):
                        target = n
                if (target > -1):
                    self['networkInterfaces'][target]['name'] = new_int['name']
                    self['networkInterfaces'][target]['localAddress'] = new_int['local']
                    self['networkInterfaces'][target]['subnetAddress'] = new_int['subnet']
                else:
                    self.add_vlanInterface(new_int['name'],
                                           new_int['local'],
                                           new_int['subnet'])


class ConfigureHADevices(AttrDict):
    URI = '/mgmt/cm/cloud/tasks/configure-ha-devices'

    def __init__(self, *args, **kwargs):
        super(ConfigureHADevices, self).__init__(*args, **kwargs)


class IAppBaseTemplate(BaseApiObject):
    URI = '/mgmt/cm/cloud/templates/iapp'
    ITEM_URI = URI + "/%s"
    ITEM_STAT_URI = ITEM_URI + "/stats"
    ITEM_DEVICE_URI = ITEM_URI + "/devices"
    IAPP_TMPL_URI_LIST = ['/mgmt/cm/cloud/templates/iapp/f5.bea_weblogic',
                          '/mgmt/cm/cloud/templates/iapp/f5.citrix_presentation_server',
                          '/mgmt/cm/cloud/templates/iapp/f5.citrix_xen_app',
                          '/mgmt/cm/cloud/templates/iapp/f5.diameter',
                          '/mgmt/cm/cloud/templates/iapp/f5.dns',
                          '/mgmt/cm/cloud/templates/iapp/f5.http',
                          '/mgmt/cm/cloud/templates/iapp/f5.ip_forwarding',
                          '/mgmt/cm/cloud/templates/iapp/f5.ldap',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_exchange_2010',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_exchange_owa_2007',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_iis',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_ocs_2007_r2',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_sharepoint_2007',
                          '/mgmt/cm/cloud/templates/iapp/f5.microsoft_sharepoint_2010',
                          '/mgmt/cm/cloud/templates/iapp/f5.npath',
                          '/mgmt/cm/cloud/templates/iapp/f5.oracle_as_10g',
                          '/mgmt/cm/cloud/templates/iapp/f5.oracle_ebs',
                          '/mgmt/cm/cloud/templates/iapp/f5.peoplesoft_9',
                          '/mgmt/cm/cloud/templates/iapp/f5.radius',
                          '/mgmt/cm/cloud/templates/iapp/f5.sap_enterprise_portal',
                          '/mgmt/cm/cloud/templates/iapp/f5.sap_erp',
                          '/mgmt/cm/cloud/templates/iapp/f5.vmware_view']
    APP_TIER_INFO = [
                     {"name": "",
                     "virtualAddress": "",
                     "virtualPort": "",
                     "pool": "",
                     "serverAddress": "",
                     "serverPort": "",
                     "sslCert": "",
                     "sslKey": ""}
                     ]

    def __init__(self, *args, **kwargs):
        super(IAppBaseTemplate, self).__init__(*args, **kwargs)
        self.setdefault('deviceForJSONTransformation', {"link": "", "isSubCollection": "false"})
        self.setdefault('templateContent', '')
        self.setdefault('minSupportedBIGIPVersion', '')
        self.setdefault('maxSupportedBIGIPVersion', '')
        self.setdefault('unsupportedBIGIPVersions', [])
        self.setdefault('serverTierInformation',
                        IAppBaseTemplate.APP_TIER_INFO)

    @staticmethod
    def verify_template_devices(rest, tmpl_selfLink, expected_device_ref_list):
        tmpl_devices = rest.get(tmpl_selfLink + '/devices')['items']
        actual_tmpl_dev_list = []
        expected_device_machineId_list = [item.split('/')[-1] for item in expected_device_ref_list]
        for tmpl_device in tmpl_devices:
            actual_tmpl_dev_list.append(tmpl_device.selfLink)
        if len(actual_tmpl_dev_list) <> len(expected_device_machineId_list):
            return False
        for item in actual_tmpl_dev_list:
            if item.split('/')[-1] not in expected_device_machineId_list:
                return False
        return True

    @staticmethod
    def verify_tmpl_in_iapp_tmpl_collection(rest, tmplate_name, timeout=90):
        iapp_coll_search_uri = "/mgmt/cm/cloud/templates/iapp?$filter=name eq '{0}'".format(tmplate_name)
        wait(lambda: rest.get(iapp_coll_search_uri),
             condition=lambda x: (x.totalItems == 1),
             progress_cb=lambda x: 'Waiting until template is imported into\
                   /mgmt/cm/cloud/templates/iapp',
                   timeout=timeout, interval=2)
