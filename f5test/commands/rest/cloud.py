'''
Created on Feb 11, 2014

@author: dobre
'''
from .base import IcontrolRestCommand
from ..base import CommandError
from ...base import Options, enum
from ...utils.wait import wait
from ...interfaces.rest.emapi.objects.cloud import Tenant, Connector, IappTemplate, \
    IappTemplateProperties, ConnectorProperty, TenantService, IAppBaseTemplate
from ...interfaces.testcase import ContextHelper
from ...interfaces.rest.emapi.objects.base import Link, Reference, ReferenceList
from ...interfaces.rest.emapi.objects.shared import DeviceResolver, LicensePool, RefreshCurrentConfig
from .device import DEFAULT_ALLBIGIQS_GROUP, DEFAULT_CLOUD_GROUP, \
    ASM_ALL_GROUP, FIREWALL_ALL_GROUP, DEFAULT_AUTODEPLOY_GROUP, \
    SECURITY_SHARED_GROUP, Discover
from .system import WaitRestjavad
from netaddr import IPAddress, ipv6_full
import logging
from f5test.interfaces.rest.emapi.objects.bigip import FailoverState

LOG = logging.getLogger(__name__)
PROPERTY_AA = {'highAvailabilityMode': 'active-active'}

# list of accepted connector types
CTYPES = enum(local='local',
              vsm='vmware',
              ec2='ec2',
              openstack='openstack',
              nsx='vmware-nsx',
              vcmp='vcmp',
              cisco='cisco-apic'
              )

add_tenant = None
class AddTenant(IcontrolRestCommand):  # @IgnorePep8
    """Adds a tenant (tenant post)

    @param name: name #mandatory
    @type name: string

    @return: the tenant's api resp
    @rtype: attr dict json
    """
    def __init__(self, name,
                 # role=None,
                 description=None,
                 connectors=None,  # =[Reference(connector_payload)]
                 address=None,
                 phone=None,
                 email=None,
                 *args, **kwargs):
        super(AddTenant, self).__init__(*args, **kwargs)
        self.name = name
        # self.role = role  # Reference
        self.description = description
        self.connectors = connectors  # Reference List: EG: =[Reference(connector_payload)]
        self.address = address
        self.phone = phone
        self.email = email

    def setup(self):

        LOG.debug('Verify cloud tenants rest api...')
        x = self.api.get(Tenant.URI)
        LOG.debug("Tenants State Now: {0}".format(x))

        # Adding a Tenant
        LOG.info("Creating Tenant '{0}' ...".format(self.name))

        payload = Tenant(name=self.name)
        if self.description:
            payload['description'] = self.description
        if self.address:
            payload['addressContact'] = self.address
        if self.phone:
            payload['phone'] = self.phone
        if self.email:
            payload['email'] = self.email
        if self.connectors:
            payload['cloudConnectorReferences'] = self.connectors

        # This will also create the cloud user role "CloudTenantAdministrator_"
        resp = self.api.post(Tenant.URI, payload=payload)
        LOG.info("Created Tenant '{0}'. Further results in debug.".format(self.name))
        return resp


assign_connector_to_tenant_by_name = None
class AssignConnectorToTenantByName(IcontrolRestCommand):  # @IgnorePep8
    """Assigns a connector(by name) to tenant(by name) (tenant put)

    @param ctype: connector type #mandatory;
            Example: local/vmware/ec2/openstack/vmware-nsx/etc.
    @type ctype: string
    @param cname: connector name #mandatory
    @type cname: string
    @param tname: tenantname #mandatory
    @type tname: string

    @return: the tenant's api resp
    @rtype: attr dict json
    """
    def __init__(self, ctype, cname, tname,
                 *args, **kwargs):
        super(AssignConnectorToTenantByName, self).__init__(*args, **kwargs)
        self.ctype = ctype
        self.cname = cname
        self.tname = tname

    def setup(self):

        LOG.info("Assigning Connector '{0}' to Tenant '{1}.'"
                 .format(self.ctype, self.tname))
        connectorid = next(x.connectorId for x in
                           self.api.get(Connector.URI % (self.ctype))['items']
                           if x.name == self.cname)
        payload = self.api.get(Tenant.ITEM_URI % (self.tname))
        payload['generation'] = payload.generation
        connector_payload = self.api.get(Connector.ITEM_URI % (self.ctype, connectorid))
        payload['cloudConnectorReferences'] = ReferenceList()
        payload.cloudConnectorReferences.append(Reference(connector_payload))

        resp = self.api.put(payload.selfLink, payload=payload)
        LOG.info("Assigned Connector '{0}' to Tenant '{1}'. Further results in debug."
                 .format(self.ctype, self.tname))

        return resp


add_iapp_template = None
class AddIappTemplate(IcontrolRestCommand):  # @IgnorePep8
    """Adds an iapp template to the Bigiq
        - will check for availability before posting
        Usage example 1 (use default HTTP iapp from cloud example):
        add_iapp_template(name='BVT_cat_HTTP0_')
        Usage example 2 (from file):
        add_iapp_template(name='BVT_cat_HTTP0_',
                          template_path=self.ih.get_data('PROJECTJSONDATAFOLDER'),
                          file_name='template115.json')


    @param name: name #mandatory
    @type name: string
    @param itype: Defaults to "http" #optional
    @type itype: string
    @param provider: Defaults to None # optional
    @type provider: string
    @param template_path: the relative path in depo #optional
    @type template_path: string
    @param file_name: file name of the template file #optional
    @type file_name: string

    @param specs: other optional specs. Calling this spec for now in case it grows in the future.
                  Right now there are 'connector' and 'template_uri'
                  'connector':<the post response> or selfLink of connector
                  'template_uri':'/mgmt/cm/cloud/templates/iapp/f5.http'
    @type specs: dict or AttrDict

    @return: iapp template rest resp
    @rtype: attr dict json
    """
    def __init__(self, name,
                 template_path=None,
                 file_name=None,
                 specs=None,
                 itype="f5.http",
                 provider=None,
                 *args, **kwargs):
        super(AddIappTemplate, self).__init__(*args, **kwargs)
        specs = Options(specs)
        self.name = name
        self.connector = specs.get('connector', '')

        content = None
        if template_path and file_name:
            content = IappTemplate().from_file(template_path, file_name)
        elif itype == "f5.http" and provider and provider == "f5.http:ssl-offload":
            content = IappTemplate()
            """
                REST Workers on systems take longer time to become available
                Check for availability and then perform additional queries
            """
            wait(lambda: self.ifc.api.get(IappTemplate.HTTP_OFFLOAD_EXAMPLE),
                 condition=lambda ret: ret is not None,
                 progress_cb=lambda ret: 'Waiting until template, {0} is available'
                 .format(IappTemplate.HTTP_OFFLOAD_EXAMPLE),
                 interval=3, timeout=30,
                 timeout_message="template, {0} is unavailable"
                 .format(IappTemplate.HTTP_OFFLOAD_EXAMPLE))
            content.update(self.ifc.api.get(IappTemplate.HTTP_OFFLOAD_EXAMPLE))
        else:
            content = IappTemplate()
            """
                REST Workers on systems take longer time to become available
                Check for availability and then perform additional queries
            """
            wait(lambda: self.ifc.api.get(IappTemplate.EXAMPLE_URI % itype),
                 condition=lambda ret: ret is not None,
                 progress_cb=lambda ret: 'Waiting until template, {0} is available'
                 .format(IappTemplate.EXAMPLE_URI % itype),
                 interval=3, timeout=30,
                 timeout_message="template, {0} is unavailable"
                 .format(IappTemplate.EXAMPLE_URI % itype))
            content.update(self.ifc.api.get(IappTemplate.EXAMPLE_URI % itype))
        self.itype = itype
        self.fn = template_path + "/" + file_name if template_path else None
        self.template_uri = specs.template_uri if specs.template_uri else content.parentReference.link
        self.payload = content
        self.overrides = specs.overrides if specs.overrides else None

    def setup(self):
        LOG.info("Creating catalog '{0}' from [{1}]...".format(self.name,
                                                               self.fn or self.itype))

        self.payload.update(templateName=self.name)

        if self.connector:
            provider = self.connector.selfLink if isinstance(self.connector, dict) and \
                self.connector.get('selfLink') else self.connector
            self.payload.properties.append(IappTemplateProperties(provider=provider))
        else:
            self.payload.properties.append(IappTemplateProperties())

        LOG.debug("Waiting for template to be available...")

        def is_iapp_template_available():
            return self.ifc.api.get(self.template_uri)

        wait(is_iapp_template_available,
             progress_cb=lambda x: '...retry template uri - not available yet ...',
             timeout=50, interval=1,
             timeout_message="Template uri is not available after {0}s")

        LOG.debug("Verified that template is available...")
        LOG.debug("Waiting for iapp template to be assosicated with device...")

        def is_templated_associated_with_bigip():
            template_resp = self.ifc.api.get(self.template_uri)
            device_references = template_resp['deviceReferences']
            if len(device_references) > 0:
                return True

        wait(is_templated_associated_with_bigip,
             progress_cb=lambda x: '...retry - iapp template not associated with device yet ...',
             timeout=120, interval=1,
             timeout_message="Template is not associated with device after {0}s")
        LOG.debug("Verified iapp is assosicated with a bigip device...")

        if self.overrides:
            # Case when a test needs properties other than default on the iapp template
            # specs passed to this class would be a list of dictionaries
            # [{"var_name":"provider_value"}]

            for var in self.overrides:
                for default_var in self.payload.overrides.vars:
                    if default_var.name == var.name:
                        default_var.provider = var.provider

        LOG.debug("Creating Catalog...Posting...")
        resp = self.ifc.api.post(IappTemplate.URI, payload=self.payload)
        LOG.info("Created iappTemplate (Catalog) '{0}'. Further results in debug."
                 .format(self.name))
        return resp


add_pool_license = None
class AddPoolLicense(IcontrolRestCommand):  # @IgnorePep8
    """ Adds a pool license to Big-IQ

    @param name: pool license name #mandatory
    @type name: string

    @param regkey: regkey #mandatory
    @type regkey: string

    @param method: pool license activation method #mandatory
    @type method: string

    """

    def __init__(self, name, regkey,
                 method,
                 *args, **kwargs):
        super(AddPoolLicense, self).__init__(*args, **kwargs)
        self.name = name
        self.regkey = regkey
        self.method = method

    def setup(self):
        if self.method == LicensePool.AUTO_METHOD:
            payload = LicensePool(name=self.name,
                                  baseRegKey=self.regkey, method=self.method)
            lic_pool = self.api.post(LicensePool.POOLS_URI, payload=payload)
            LOG.debug('Getting EULA...')
            LicensePool.wait(self.api, lic_pool, automatic=True, timeout=60)
            resp = LicensePool.wait(self.api, lic_pool, True, timeout=30)
            if resp.state in ['WAITING_FOR_EULA_ACCEPTANCE']:
                LOG.debug('Need to accept EULA...')
                LOG.debug('Adding EULA Text to Payload...')
                payload = LicensePool(eulaText=resp.eulaText, state='ACCEPTED_EULA')
                self.api.patch(resp.selfLink, payload=payload)
                wait(lambda: self.api.get(LicensePool.POOL_URI % resp.uuid),
                     condition=lambda temp: temp.state == 'LICENSED',
                     progress_cb=lambda temp: 'State: {0} '.format(temp.state),
                     timeout=10, interval=1)
                LOG.info('EULA Accepted...')
            return resp

add_connector = None
class AddConnector(IcontrolRestCommand):  # @IgnorePep8
    """Adds a cloud connector to bigiq

    @param name: name #mandatory
    @type name: string
    @param ctype: type of connector #mandatory
                Accepted: local/vmware/ec2/openstack/vmware-nsx
    @type ctype: string

    @param description: connector description #not mandatory
    @type description: string
    @param device_references: device references #not mandatory
                        example: # [Link(link=x) for x in self.get_data('device_uris)]
    @type device_references: ReferenceList()
    @param remote_address # all mandatory params for non 'local' connectors
           remote_user
           remote_password
    @type string

    @param specs: connector specific parameters in dict format #not mandatory
                  - each dict key is the exact "id" parameter value of the payload
                  - notice that for ec2, no need to add the networks "name" subdict item.
                  Examples:
                  nsx: nsxresp = add_connector(name=nsxalias,
                                            ctype=CTYPES.nsx,
                                            description="NSX Automated Test Connector",
                                            remote_address=nsxi.get("ip"),
                                            remote_user=nsxi.get("user"),
                                            remote_password=nsxi.get("pw"),
                                            specs={'bigIQCallbackUser': self.bigiq.get("user"),
                                           'bigIQCallbackPassword': self.bigiq.get("pw")})
                  ec2: resp = add_connector(name=ec2alias,
                                           ctype=CTYPES.ec2,
                                           description="EC2 Automated test",
                                           remote_address=ec2x.get('ip'),
                                           remote_user=ec2x.get('user'),
                                           remote_password=ec2x.get('pw'),
                         specs={'availabilityZone': ec2x.get('zone'),
                                'ntpServers': ec2x.get('ntps'),
                                'timezone': ec2x.get('tzs'),
                                'vpcId': ec2x.get('vpc'),
                        'tenantInternalNetworks': [{'subnetAddress': ec2x.get('sint'),
                                                    'gatewayAddress': ec2x.get('int_gw')}],
                        'managementNetworks': [{'subnetAddress': ec2x.get('smgmt'),
                                                'gatewayAddress': ec2x.get('mgmt_gw')}],
                        'tenantExternalNetworks': [{'subnetAddress': ec2x.get('sext'),
                                                    'gatewayAddress': ec2x.get('ext_gw')}],
                                        })
    @type specs: Dict

    @return: connector rest resp
    @rtype: attr dict json
    """
    def __init__(self, name, ctype,
                 description=None,
                 device_references=None,  # [Link(link=x) for x in self.get_data('device_uris)]
                 remote_address=None,
                 remote_user=None,
                 remote_password=None,
                 specs=None,
                 *args, **kwargs):
        super(AddConnector, self).__init__(*args, **kwargs)

        self.name = name
        self.description = description
        self.device_references = device_references
        # common required parameters:
        if ctype != CTYPES.local and ctype != CTYPES.cisco:
            if not remote_address or not remote_user or not remote_password:
                raise CommandError("Invalid required parameters for connector: {0}"
                                   .format(self.name))
        if ctype == CTYPES.nsx:
            if not 'bigIQCallbackUser' in specs or \
                not 'bigIQCallbackPassword' in specs:
                if not specs['bigIQCallbackUser'] or \
                    not  specs['bigIQCallbackPassword']:
                    raise CommandError("Invalid specific parameters for connector: {0}"
                                       .format(self.name))
        elif ctype == CTYPES.ec2:
            if not 'availabilityZone' in specs:
                if not specs['availabilityZone']:
                    raise CommandError("Invalid specific parameters for connector: {0}"
                                       .format(self.name))
        elif ctype == CTYPES.local:
            pass
        elif ctype == CTYPES.vsm:
            pass
        elif ctype == CTYPES.openstack:
            pass
        elif ctype == CTYPES.vcmp:
            pass
        elif ctype == CTYPES.cisco:
            pass
        else:
            raise CommandError("Wrong Connector Type was passed...")
        self.ctype = ctype

        self.remote_address = remote_address
        self.remote_user = remote_user
        self.remote_password = remote_password

        self.specs = specs

    def setup(self):

        LOG.debug("Adding {1} Connector '{0}'..."
                  .format(self.name, self.ctype))
        # Creating from scratch
        # Required Parameters for all:
        payload = Connector()
        # Required
        payload['cloudConnectorReference'] = Link(link=Connector.URI % self.ctype)
        # Required
        payload['name'] = self.name

        # Not Required parameters for all:
        if self.description:
            payload['description'] = self.description
        if self.device_references:
            # payload['deviceReferences'] = ReferenceList()
            # example: [(Link(link=x) for x in urideviceList)]
            payload['deviceReferences'] = self.device_references

        # Specific Objects abd Parameters to each connector:
        if self.ctype == CTYPES.ec2:
            # OBJECTS
            # Not Required Objects
            if 'ntpServers' in self.specs:
                if self.specs['ntpServers']:
                    payload['ntpServers'] = self.specs['ntpServers']
            if 'timezone' in self.specs:
                if self.specs['timezone']:
                    payload['timezone'] = self.specs['timezone']
            if 'tenantInternalNetworks' in self.specs:
                if self.specs['tenantInternalNetworks']:
                    payload['tenantInternalNetworks'] = []
                    for network in self.specs['tenantInternalNetworks']:
                        payload.tenantInternalNetworks.append(
                            {'subnetAddress': network['subnetAddress'],
                             'name': 'internal',
                             'gatewayAddress': network['gatewayAddress']})
            if 'managementNetworks' in self.specs:
                if self.specs['managementNetworks']:
                    payload['managementNetworks'] = []
                    for network in self.specs['managementNetworks']:
                        payload.managementNetworks.append(
                            {'subnetAddress': network['subnetAddress'],
                             'name': 'mgmt',
                             'gatewayAddress': network['gatewayAddress']})
            if 'tenantExternalNetworks' in self.specs:
                if self.specs['tenantExternalNetworks']:
                    payload['tenantExternalNetworks'] = []
                    for network in self.specs['tenantExternalNetworks']:
                        payload.tenantExternalNetworks.append(
                            {'subnetAddress': network['subnetAddress'],
                             'name': 'external',
                             'gatewayAddress': network['gatewayAddress']})
            if 'dnsServerAddresses' in self.specs:
                if self.specs['dnsServerAddresses']:
                    payload['dnsServerAddresses'] = []
                    for dns in self.specs['dnsServerAddresses']:
                        payload.dnsServerAddresses.append(dns)
            if 'dnsSuffixes' in self.specs:
                if self.specs['dnsSuffixes']:
                    payload['dnsSuffixes'] = []
                    for dns in self.specs['dnsSuffixes']:
                        payload.dnsSuffixes.append(dns)

            # Not Scoped Yet, left default as they come back from POST:

            # supportsServerProvisioning
            # supportsDeviceProvisioning
            # licensepools

            # PARAMETERS
            # Required Parameters
            regionEndpoint = ConnectorProperty(id='regionEndpoint',
                                               displayName='Region Endpoint',
                                               value=self.remote_address)
            keyId = ConnectorProperty(id='awsAccessKeyID',
                                      displayName='Key ID',
                                      value=self.remote_user)
            secretKey = ConnectorProperty(id='secretAccessKey',
                                          displayName='SecretKey',
                                          value=self.remote_password)
            availZone = ConnectorProperty(id='availabilityZone',
                                          displayName='Availability Zone',
                                          value=self.specs['availabilityZone'])
            payload.parameters.extend([regionEndpoint,
                                       keyId,
                                       secretKey,
                                       availZone])
            # Not Required Parameters:
            if 'vpcId' in self.specs:
                if self.specs['vpcId']:
                    vpc = ConnectorProperty(id='vpcId',
                                            isRequired=False,
                                            displayName='Virtual Private Cloud ID',
                                            value=self.specs['vpcId'])
                    payload.parameters.extend([vpc])
            if 'autoDeployDevices' in self.specs:
                if self.specs['autoDeployDevices']:
                    deploy = ConnectorProperty(id='autoDeployDevices',
                                               isRequired=False,
                                               displayName='Auto-deploy Devices',
                                               provider=self.specs['autoDeployDevices'])
                    deploy.pop('value')
                    payload.parameters.extend([deploy])

            if 'licenseReference' in self.specs:
                payload.licenseReference = self.specs.licenseReference

            # Not Scoped Yet, left default as they come back from POST:
            # autoDeployServers

        if self.ctype == CTYPES.nsx:
            LOG.debug('Creating Specific NSX parameters (from yaml)...')
            # PARAMETERS:
            # Required Parameters:
            nsx_address_obj = ConnectorProperty(id='nsxAddress',
                                                # displayName='nsxAddress',
                                                value=self.remote_address)
            # Required
            nsx_user_obj = ConnectorProperty(id='nsxUsername',
                                             # displayName='nsxUser',
                                             value=self.remote_user)
            # Required
            nsx_password_obj = ConnectorProperty(id='nsxPassword',
                                                 # displayName='SecretKey',
                                                 value=self.remote_password)
            # Required
            vcen_address_obj = ConnectorProperty(id='vCenterServerAddress',
                                                 # displayName='nsxAddress',
                                                 value=self.specs['vCenterServerAddress'])
            # Required
            vcen_user_obj = ConnectorProperty(id='vCenterServerUsername',
                                              # displayName='nsxUser',
                                              value=self.specs['vCenterServerUsername'])
            # Required
            vcen_password_obj = ConnectorProperty(id='vCenterServerPassword',
                                                  # displayName='SecretKey',
                                                  value=self.specs['vCenterServerPassword'])
            # Required
            user_obj = ConnectorProperty(id='bigIQCallbackUser',
                                         # displayName='bigiq user',
                                         value=self.specs['bigIQCallbackUser'])
            # Required
            password_obj = ConnectorProperty(id='bigIQCallbackPassword',
                                             # displayName='bigiq password',
                                             value=self.specs['bigIQCallbackPassword'])
            payload.parameters.extend([nsx_address_obj,
                                       nsx_user_obj,
                                       nsx_password_obj,
                                       user_obj,
                                       password_obj,
                                       vcen_address_obj,
                                       vcen_user_obj,
                                       vcen_password_obj
                                       ])
            # Not Required Parameters:
            if 'machineId' in self.specs and 'ipAddress' in self.specs:
                # machineId and ipAddress are required to form the call back cluster map
                payload.callbackClusterAddresses = [{'machineId': self.specs['machineId'], 'ipAddress': self.specs['ipAddress']}]

            if 'licenseReference' in self.specs:
                payload.licenseReference = self.specs.licenseReference
            if 'ntpServers' in self.specs:
                payload.ntpServers = self.specs.ntpServers
            if 'dnsServerAddresses' in self.specs:
                payload.dnsServerAddresses = self.specs.dnsServerAddresses
            if 'timezone' in self.specs:
                payload.timezone = self.specs.timezone
            if 'deviceReference' in self.specs:
                payload.deviceReferences = [Link(link=self.specs.deviceReference)]

            # adding VCMP connector
        if self.ctype == CTYPES.vcmp:
            LOG.debug('Creating Specific VCMP parameters (from yaml)...')
            vcmp_host_obj = ConnectorProperty(id='VcmpHost',
                                              isRequired=True,
                                              value=self.specs['VcmpHost'])
            vcmp_hostusername_obj = ConnectorProperty(id='VcmpHostUserName',
                                                      isRequired=True,
                                                      value=self.specs['VcmpHostUserName'])
            vcmp_hostpassword_obj = ConnectorProperty(id='VcmpHostPassword',
                                                      isRequired=True,
                                                      value=self.specs['VcmpHostPassword'])
            payload.parameters.extend([vcmp_host_obj, vcmp_hostusername_obj,
                                       vcmp_hostpassword_obj])
            # to be updated

        LOG.debug("Creating Connector: Using payload:\n{0}".format(payload))
        wait(lambda: self.api.get(Connector.ITEM_URI % (self.ctype, "available")),
             condition=lambda ret: ret is not None,
             progress_cb=lambda ret: 'Waiting until worker, {0} is available'.format(Connector.URI % (self.ctype)),
             interval=3, timeout=60,
             timeout_message="worker, {0} is unavailable".format(Connector.URI % (self.ctype)))
        resp = self.api.post(Connector.URI % self.ctype, payload=payload)
        LOG.info("Created Connector |{0}| '{1}'. Further results in debug."
                 .format(self.ctype, self.name))

        return resp


setup_ha = None
class SetupHa(IcontrolRestCommand):  # @IgnorePep8
    DEVICE_GROUPS = [SECURITY_SHARED_GROUP, DEFAULT_AUTODEPLOY_GROUP,
                     ASM_ALL_GROUP, FIREWALL_ALL_GROUP, SECURITY_SHARED_GROUP,
                     DEFAULT_CLOUD_GROUP, 'cm-asm-logging-nodes-trust-group',
                     'cm-websafe-logging-nodes-trust-group']

    def __init__(self, peers, *args, **kwargs):
        super(SetupHa, self).__init__(*args, **kwargs)
        self.peers = peers

    def prep(self):
        WaitRestjavad(self.peers, ifc=self.ifc).run()

    def setup(self):
        LOG.info("Setting up Clustered HA with %s...", self.peers)
        peer_ips = set(IPAddress(x.get_discover_address()).format(ipv6_full) for x in self.peers)
        options = Options()
        options.properties = PROPERTY_AA
        options.automaticallyUpdateFramework = False

        Discover(self.peers, group=DEFAULT_ALLBIGIQS_GROUP,
                 options=options, ifc=self.ifc).run()

        # Wait until until peer BIG-IQs are added to the device groups.
        for device_group in SetupHa.DEVICE_GROUPS:
            if self.ifc.version < 'bigiq 4.5.0' and device_group == 'cm-websafe-logging-nodes-trust-group':
                continue
            elif self.ifc.version >= 'bigiq 1.0.0' and self.ifc.version < 'bigiq 4.0.0':  # FOR OR BRANCHING
                continue
            elif self.ifc.version >= 'iworkflow 2.0':  # iWorkflow branch
                continue
            wait(lambda: self.ifc.api.get(DeviceResolver.DEVICES_URI % device_group),
                 condition=lambda ret: len(peer_ips) == len(peer_ips.intersection(set(x.address for x in ret['items']))),
                 progress_cb=lambda ret: 'Waiting until {0} appears in {1}'.format(peer_ips, device_group),
                 interval=10, timeout=600)

i_apps = None
class iApps(IcontrolRestCommand):  # @IgnorePep8
    """
    class to return the applications running on the big ip's
    @param devices: bigip device list from harness #mandatory
    @type connector: big-iq UI element connector #optional
    """
    TM_APP_URI = '/mgmt/tm/cloud/services/iapp'

    def __init__(self, devices, connector=None, *args, **kwargs):
        super(iApps, self).__init__(*args, **kwargs)
        self.devices = devices
        self.connector = connector
        self.app_list = {}

    def prep(self):
        self.context = ContextHelper(__file__)

    def cleanup(self):
        self.context.teardown()

    def setup(self):
        devices_to_verify_on = []
        check_all_bigips = False
        if self.connector:
            for device_uri in self.connector.deviceReferences:
                resp = self.api.get(device_uri['link'])
                if 'address' in resp:
                    devices_to_verify_on.append(resp['address'])
        else:
            check_all_bigips = True

        for device in self.devices:
            if not check_all_bigips:
                device_address = device.get_discover_address()
                LOG.debug("Getting iapps on Bigip {0}".format(device_address))
                if device_address in devices_to_verify_on:
                    LOG.debug("Bigip {0} is associated with Connector".format(device_address))
                    self.return_app_list(device)
            else:
                self.return_app_list(device)
        return self.app_list

    def return_app_list(self, device):
        bigip_device_api = self.context.get_icontrol_rest(device=device).api
        self.app_list[device] = bigip_device_api.get(self.TM_APP_URI)['items']
        LOG.debug("iapp {0} found on Bigip {1}".format(self.app_list[device], device))

fail_over_peer = None
class FailOverPeer(IcontrolRestCommand):  # @IgnorePep8
    """
        # Class to failover a connector provisioned device in an active/standby HA cluster
        # NOTE: Class must always receive the device that is active in the HA cluster

        @param bigip_ifc: REST Interface on BIGIP
        @type bigip_ifc: REST Interface object

        @param traffic_group_name: traffic group on the bigip device that will be forced to fail over #mandatory
        @type traffic_group_name: String
    """

    def __init__(self,
                 bigip_ifc,
                 traffic_group_name,
                 *args, **kwargs
                 ):
        super(FailOverPeer, self).__init__(*args, **kwargs)
        self.bigip_ifc = bigip_ifc
        self.traffic_group_name = traffic_group_name

    def prep(self):
        self.context = ContextHelper(__file__)

    def cleanup(self):
        self.context.teardown()

    def setup(self):
        bigip_api = self.bigip_ifc.api
        payload = Options()
        payload.command = "run"
        payload.standby = True
        payload.trafficGroup = self.traffic_group_name
        bigip_api.post(FailoverState.BIG_IP_SYNC_FAILOVER, payload=payload)
        return

wait_for_active_on_connector = None
class WaitForActiveOnConnector(IcontrolRestCommand):    # @IgnorePep8
    """
        # Class to wait until active BIGIP device in given HA pair is seen on the connector
        # Standby BIGIP device must not be seen on the connector

        @param connector: Cloud Connector #mandatory
        @type address: Cloud Connector Object

        @param active_machineId: active BIGIP machine ID #mandatory
        @type device: String

        @param standby_machineId: standby BIGIP machine ID #mandatory
        @type device: String
    """

    def __init__(self, connector,
                 active_machineId,
                 standby_machineId,
                 timeout=120,
                 interval=10,
                 *args, **kwargs):
        super(WaitForActiveOnConnector, self).__init__(*args, **kwargs)
        self.connector = connector
        self.active = active_machineId
        self.standby = standby_machineId
        self.timeout = timeout
        self.interval = interval

    def cleanup(self):
        self.context.teardown()

    def setup(self):
        wait(lambda: self.api.get(Connector.ITEM_URI % (CTYPES.nsx, "available")),
             condition=lambda ret: ret is not None,
             progress_cb=lambda ret: 'Waiting until worker, {0} is available'
             .format(Connector.URI % (CTYPES.nsx)),
             interval=5, timeout=60,
             timeout_message="worker, {0} is unavailable"
             .format(Connector.URI % (CTYPES.nsx)))

        wait(self.verify_device,
             condition=lambda x: x,
             progress_cb=lambda _: "waiting for the active device on the connector",
             timeout=self.timeout, interval=self.interval,
             timeout_message="connector doesn't have the active device of the HA cluster after {0} secs")

    def verify_device(self):
        connector = self.api.get(self.connector.selfLink)
        if connector.deviceGroupReference and connector.deviceGroupReference.link:
            connector_devices = self.api.get(connector.deviceGroupReference.link + '/devices')['items']
            machines_on_connector = [device.machineId for device in connector_devices if device.machineId]
            LOG.debug("Machines on connector device group={0}".format(machines_on_connector))
            if (self.active in machines_on_connector and self.standby not in machines_on_connector):
                return True
        return False


refresh_device = None
class RefreshDevice(IcontrolRestCommand):  # @IgnorePep8
    """Syn working config and current config from bigip ...

    @device_id: the device specs
    @type: string
    """
    def __init__(self, device, *args, **kwargs):
        super(RefreshDevice, self).__init__(*args, **kwargs)
        self.device = device

    def setup(self):
        LOG.info("Syn working config and current config from bigip ...")
        LOG.debug('device_id is %s' % self.device.uuid)
        payload = RefreshCurrentConfig()
        payload.configPaths.append({'icrObjectPath': '/cloud/net/vlan'})
        payload.configPaths.append({'icrObjectPath': '/cloud/net/interface'})
        payload.configPaths.append({'icrObjectPath': '/cloud/net/route'})
        payload.configPaths.append({'icrObjectPath': '/cloud/net/self'})
        payload.configPaths.append({'icrObjectPath': '/cloud/sys/all-certificate-file-object'})
        payload.deviceReference.set(self.device.selfLink)
        task = self.api.post(RefreshCurrentConfig.URI, payload)
        RefreshCurrentConfig.wait(self.api, task)


get_templates = None
class GetTemplates(IcontrolRestCommand):  # @IgnorePep8
    """Get an iApp template or a list of iApp templates.   Only for iWorkflow Krypton (2.1) or later.
    @param template_name: Name of the requested iApp template.
    @type template_name: string.  None by default. If None or empty string, then all iApp templates will be returned as a list.

    @param base_templates: whether the desired templates are base templates (vs. provider templates).
    @type base_templates: boolean.  False by default.  Set to True if the queried templates are base templates, otherwise, provider templates or tenant templates will be returned.

    @param tenant: Name of the login tenant user.
    @type tenant: a string.  None by default. If None or empty string, then the user is "admin", and provider or base templates will be returned.

    @return a template object (dict type) if template_name is set.   A list of template objects (list of dict) if template_name is None or empty.
    """

    def __init__(self, template_name=None, base_templates=False, tenant=None, *args, **kwargs):
        super(GetTemplates, self).__init__(*args, **kwargs)

        self.template_name = template_name
        self.tenant = tenant
        self.name_field = "name" if tenant or base_templates else "templateName"
        if tenant:
            self.url = TenantService.URI  # '/mgmt/cm/cloud/tenant/templates/iapp'
        elif base_templates:
            self.url = IAppBaseTemplate.URI  # '/mgmt/cm/cloud/templates/iapp'
        else:
            self.url = IappTemplate.URI  # '/mgmt/cm/cloud/provider/templates/iapp/'

    def prep(self):
        self.context = ContextHelper(__file__)

    def cleanup(self):
        self.context.teardown()

    def setup(self):
        template_list = self.api.get(self.url)["items"]
        if self.template_name:
            results = filter(lambda template: template.get(self.name_field) == self.template_name, template_list)
            result = results[0] if results else None
        else:
            result = template_list

        return result


import_template = None
class ImportTemplate(IcontrolRestCommand):  # @IgnorePep8
    """
        # Class to import a base template to iWorkflow.
        # This feature is added in Krypton.

        @param template_name: Name of the base template to be imported.
        @type template_name: string

        @param device_link: Selflink to the BIG-IP device which is used to generate json data
        @type device_link: String, something like "https://localhost//mgmt/shared/resolver/device-groups/cm-cloud-managed-devices/devices/10e90bb0-b62b-40b5-8aa4-042b3ec46970"

        @param absolute_file_path: full path to text file which contains base template content.
        @type absolute_file_path: string (file path).

        @param content: content which contains the base template information.  Usually it is the text format of .tmpl file generated from existing build-in base template
        @type content: String

        @return a template object (dict type) if the base template already exists or the base template is imported successfully.   Otherwise, REST exception will be thrown out.
    """
    def __init__(self,
                 template_name,
                 cloud_managed_devices,
                 absolute_file_path,
                 content=None,
                 minSupportedBIGIPVersion='',
                 maxSupportedBIGIPVersion='',
                 unsupportedBIGIPVersions='',
                 app_tier_info=None,
                 *args,
                 **kwargs):
        super(ImportTemplate, self).__init__(*args, **kwargs)
        self.cloud_managed_devices = cloud_managed_devices
        self.tmpl_file_path = absolute_file_path
        self.template_name = template_name
        self.content = content
        if absolute_file_path:
            with open(absolute_file_path) as tmpl_file:
                self.content = tmpl_file.read()
        self.minSupportedBIGIPVersion = minSupportedBIGIPVersion.strip()
        self.maxSupportedBIGIPVersion = maxSupportedBIGIPVersion.strip()
        self.unsupportedBIGIPVersions = unsupportedBIGIPVersions
        self.app_tier_info = app_tier_info

    def setup(self):
        template = get_templates(template_name=self.template_name,
                                 base_templates=True)
        if template:
            LOG.debug('template {0} is already imported into iWorkflow \
            device'.format(self.template_name))
            return template

        if not self.cloud_managed_devices or len(self.cloud_managed_devices) == 0:
            LOG.debug("no discovered Big-IP devices found, skipping import template")
            return
        else:
            payload = IAppBaseTemplate(templateContent=self.content)
            self.device_link = self.cloud_managed_devices[0]['selfLink']
            devicelink = {"link": self.device_link, "isSubCollection": "false"}
            payload.deviceForJSONTransformation = devicelink

        # set optional parameters in payload in case they are provided
        if self.minSupportedBIGIPVersion:
            payload.minSupportedBIGIPVersion = self.minSupportedBIGIPVersion
        else:
            del payload['minSupportedBIGIPVersion']

        if self.maxSupportedBIGIPVersion:
            payload.maxSupportedBIGIPVersion = self.maxSupportedBIGIPVersion
        else:
            del payload['maxSupportedBIGIPVersion']

        if self.unsupportedBIGIPVersions:
            payload.unsupportedBIGIPVersions = self.unsupportedBIGIPVersions
        else:
            del payload['unsupportedBIGIPVersions']
        if self.app_tier_info is not None:
                payload.serverTierInformation = self.app_tier_info
        else:
            del payload['serverTierInformation']

        LOG.debug("PAYLOAD: %s" % payload)
        template = self.api.post(path=IAppBaseTemplate.URI, payload=payload)
        self.template_loader_task_wait(self.template_name)
        wait(lambda: self.api.get(IAppBaseTemplate.ITEM_STAT_URI % self.template_name),
             timeout=60, interval=2,
             condition=lambda x: x['entries']['health.summary.template']['value'] != 0.5,
             progress_cb=lambda x: 'health: %s' % x['entries'],
             timeout_message='Timeout for importing template after {0}: {1}')
        return self.api.get(template.selfLink)

    def template_loader_task_wait(self, template_name, timeout=60):
        template_loader_task = self.get_template_loader_task(template_name)
        ret = wait(lambda: self.api.get(template_loader_task),
                   condition=lambda x: (x.status == "FINISHED"),
                   progress_cb=lambda x: 'Waiting until template loader task completes\
                   , Operation: {0}; Step: {1}'.format(x.operation, x.step),
                   timeout=timeout, interval=2)
        return ret

    def get_template_loader_task(self, template_name):
        """Note: template loader task uri will change and it will be made relative to
        IAppBaseTemplate URI. Updates will be made then"""

        template_loader_task_uri = '/mgmt/cm/cloud/templates/iapp/tasks/template-loader-task'
        params_dict = {'$orderby': 'lastUpdateMicros desc'}
        template_loader_task = self.api.get(template_loader_task_uri,
                                            params_dict=params_dict)['items'][0]
        if template_name == template_loader_task["iAppTemplateName"]:
            return template_loader_task.selfLink
