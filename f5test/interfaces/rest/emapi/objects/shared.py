'''
Created on Jan 9, 2014

/mgmt/[cm|tm]/shared and /mgmt/shared workers

@author: jono
'''
from .....base import enum, AttrDict
from .....defaults import ADMIN_USERNAME, ADMIN_PASSWORD
from .base import Reference, ReferenceList, Task, DEFAULT_TIMEOUT
from ...base import BaseApiObject
from .....utils.wait import wait


class SystemStarted(BaseApiObject):
    """ Is system Started
    """
    URI = '/mgmt/shared/system-started'

    def __init__(self, *args, **kwargs):
        super(SystemStarted, self).__init__(*args, **kwargs)
        self.setdefault('reason', 'System is started')  # sample to wait for

    @staticmethod
    def wait(rest, timeout=DEFAULT_TIMEOUT, interval=2):

        ret = wait(lambda: rest.get(SystemStarted.URI), timeout=timeout, interval=interval,
                   condition=lambda ret: ret.reason in ["System is started"],
                   progress_cb=lambda ret: 'Status: {0}'.format(ret.reason))
        return ret


class UserCredentialData(BaseApiObject):
    """ Stores all the data related to a new user to be passed in a REST
        API call.

        The following parameters are supported (case sensitive):
          name
          password
          displayName
    """
    URI = '/mgmt/shared/authz/users'
    ITEM_URI = '/mgmt/shared/authz/users/%s'

    def __init__(self, *args, **kwargs):
        super(UserCredentialData, self).__init__(*args, **kwargs)
        self.setdefault('name', 'NewTenant')
        self.setdefault('password', '')
        self.setdefault('displayName', 'NewTenant DisplayName')


class License(Task):
    ACTIVATION_URI = '/mgmt/tm/shared/licensing/activation'
    URI = '/mgmt/tm/shared/licensing/registration'
    WAITING_STATE = 'LICENSING_ACTIVATION_IN_PROGRESS'
    FAIL_STATE = 'LICENSING_FAILED'

    def __init__(self, *args, **kwargs):
        super(License, self).__init__(*args, **kwargs)
        self.setdefault('baseRegKey', '')
        self.setdefault('addOnKeys', [])
        self.setdefault('isAutomaticActivation', 'true')

    @staticmethod
    def wait(rest, timeout=DEFAULT_TIMEOUT):

        ret = wait(lambda: rest.get(License.ACTIVATION_URI), timeout=timeout, interval=1,
                   condition=lambda ret: ret.status not in License.WAITING_STATE,
                   progress_cb=lambda ret: 'Status: {0}'.format(ret.status))

        if ret.status in License.FAIL_STATE:
            Task.fail('Licensing failed', ret)

        return ret


class NetworkDiscover(BaseApiObject):
    URI = '/mgmt/shared/identified-devices/config/discovery'

    def __init__(self, *args, **kwargs):
        super(NetworkDiscover, self).__init__(*args, **kwargs)
        self.setdefault('discoveryAddress', '')
        self.setdefault('validateOnly', False)


class UserRoles(BaseApiObject):
    URI = '/mgmt/shared/authz/roles/%s'  # keep for backwards compatible
    ITEM_URI = '/mgmt/shared/authz/roles/%s'
    ONLYURI = '/mgmt/shared/authz/roles'
    TYPES = enum(ADMIN='Administrator',
                 SECURITY='Security_Manager',
                 CLOUD='CloudTenantAdministrator_%s',
                 FIREWALL='Firewall_Manager')

    def __init__(self, *args, **kwargs):
        super(UserRoles, self).__init__(*args, **kwargs)
        self.setdefault('name', UserRoles.TYPES.ADMIN)
        self.setdefault('userReferences', ReferenceList())
        self.setdefault('resources', [])

# A wait method to check if the given role is removed on the user
    @staticmethod
    def wait_removed(restapi, userselflink, timeout=DEFAULT_TIMEOUT):  # @UndefinedVariable

        ret = wait(lambda: restapi.get(UserRoles.ONLYURI)['items'], timeout=timeout, interval=1,
                   condition=lambda ret: userselflink not in [x.link for x in ret],
                   progress_cb=lambda __: "Waiting until user role is deleted")

        return userselflink not in [x.link for x in ret]


class GossipWorkerState(BaseApiObject):
    URI = '/mgmt/shared/gossip'

    def __init__(self, *args, **kwargs):
        super(GossipWorkerState, self).__init__(*args, **kwargs)
        self.setdefault('pollingIntervalMicrosCount')
        self.setdefault('updateThresholdPerMicrosCount')
        self.setdefault('workerUpdateProcessingIntervalMicrosCount')
        self.setdefault('workerUpdateDelayMicrosCount')
        self.setdefault('workerStateInfoMap', AttrDict())
        self.setdefault('gossipPeerGroup')
        self.setdefault('isLocalUpdate', False)


class DeviceResolver(Task):
    URI = '/mgmt/shared/resolver/device-groups'
    ITEM_URI = '%s/%%s' % URI
    DEVICES_URI = '%s/%%s/devices' % URI
    DEVICE_STATE = '%s/%s/devices/%s'
    DEVICE_URI = '%s/%%s' % DEVICES_URI
    STATS_URI = '%s/%%s/stats' % URI
    DEVICE_STATS_URI = '%s/stats' % DEVICE_URI
    PENDING_STATES = ('PENDING', 'PENDING_DELETE',
                      'FRAMEWORK_DEPLOYMENT_PENDING', 'TRUST_PENDING',
                      'CERTIFICATE_INSTALL')

    def __init__(self, *args, **kwargs):
        super(DeviceResolver, self).__init__(*args, **kwargs)
        self.setdefault('address', '')
        self.setdefault('userName', ADMIN_USERNAME)
        self.setdefault('password', ADMIN_PASSWORD)
        self.setdefault('properties', AttrDict())
        self.setdefault('deviceReference', Reference())
#         self.setdefault('parentGroupReference', Reference())  # BZ474699

    @staticmethod
    def wait(rest, group, timeout=120, count=None):

        def get_status():
            return rest.get(DeviceResolver.DEVICES_URI % group)

        def all_done(ret):
            return sum(x.state not in DeviceResolver.PENDING_STATES
                       for x in ret['items']) == (sum(1 for x in ret['items']) if count is None else count)

        ret = wait(get_status, timeout=timeout,
                   condition=all_done,
                   progress_cb=lambda ret: 'Status: {0}'.format(list(x.state for x in ret['items'])))

        if sum(1 for x in ret['items']) != \
           sum(x.state == 'ACTIVE' for x in ret['items']):
            Task.fail('At least one subtask is not completed', ret)
        return ret

    @staticmethod
    def wait_for_bigiq_count(rest, group, timeout=120, count=1):

        def get_status_with_filter():
            return rest.get(DeviceResolver.DEVICES_URI % group, params_dict={'$filter': "product eq 'BIG-IQ'"})

        ret = wait(get_status_with_filter, timeout=timeout,
                   condition=lambda ret: ret.totalItems >= count,
                   progress_cb=lambda ret: 'BQ Status: {0}'.format(ret))
        return ret


class DeviceResolverGroup(BaseApiObject):
    URI = DeviceResolver.URI + '/%s'


class DeviceResolverDevice(BaseApiObject):
    URI = DeviceResolver.DEVICES_URI + '/%s'

    def __init__(self, *args, **kwargs):
        super(DeviceResolverDevice, self).__init__(*args, **kwargs)
        self.setdefault('userName', ADMIN_USERNAME)
        self.setdefault('password', ADMIN_PASSWORD)
        self.setdefault('uuid')
        self.setdefault('state', 'ACTIVE')


class DeviceGroup(BaseApiObject):
    URI = '/mgmt/shared/resolver/device-groups'
    ITEM_URI = '{0}/%s'.format(URI)
    DEVICES_URI = '{0}/%s/devices'.format(URI)

    def __init__(self, *args, **kwargs):
        super(DeviceGroup, self).__init__(*args, **kwargs)
        self.setdefault('kind', 'shared:resolver:device-groups:devicegroupstate')
        self.setdefault('infrastructure', False)
        self.setdefault('description', 'Just a Test Group')
        self.setdefault('isViewGroup', False)
        self.setdefault('groupName', 'test-group')
        self.setdefault('autoManageLocalhost', True)


class DeviceInfo(BaseApiObject):
    URI = '/mgmt/shared/identified-devices/config/device-info'

    def __init__(self, *args, **kwargs):
        super(DeviceInfo, self).__init__(*args, **kwargs)


class HAPeerRemover(BaseApiObject):
    URI = '/mgmt/cm/shared/ha-peer-remover'

    def __init__(self, *args, **kwargs):
        super(HAPeerRemover, self).__init__(*args, **kwargs)
        self.setdefault('peerReference', Reference())


class Echo(BaseApiObject):
    URI = '/mgmt/shared/echo'
    AVAILABLE_URI = '/mgmt/shared/echo/available'


class FailoverState(BaseApiObject):
    URI = '/mgmt/shared/failover-state'
    PENDING_STATES = ('UNKNOWN', 'UNINITIALIZED', 'SYNCHRONIZING', 'UNPAIRED')
    KNOWN_STATES = ('ACTIVE', 'STANDBY', 'DOWN')

    def __init__(self, *args, **kwargs):
        super(FailoverState, self).__init__(*args, **kwargs)
        self.setdefault('isPrimary', True)

    @staticmethod
    def wait(rest, timeout=DEFAULT_TIMEOUT):

        def get_status():
            return rest.get(FailoverState.URI)

        def all_done(ret):
            return ret.failoverState not in FailoverState.PENDING_STATES \
                and ret.peerFailoverState not in FailoverState.PENDING_STATES

        ret = wait(get_status, timeout=timeout, interval=1,
                   condition=all_done,
                   progress_cb=lambda _: 'Waiting until faioverState complete...')
        return ret


class SnapshotClient(BaseApiObject):
    URI = '/mgmt/shared/storage/snapshot-client'
    SNAPSHOT_LOCATION = '/var/config/rest/active-storage.zip'

    def __init__(self, *args, **kwargs):
        super(SnapshotClient, self).__init__(*args, **kwargs)
        self.setdefault("snapshotFile", "")


class LicensePool(Task):
    POOLS_URI = '/mgmt/cm/shared/licensing/pools'
    POOL_URI = '/mgmt/cm/shared/licensing/pools/%s'
    POOL_MEMBERS_URI = '/mgmt/cm/shared/licensing/pools/%s/members'
    POOL_MEMBER_URI = '/mgmt/cm/shared/licensing/pools/%s/members/%s'
    WAITING_STATE = 'WAITING_FOR_EULA_ACCEPTANCE'
    WAITING_STATE_MANUAL = 'WAITING_FOR_LICENSE_TEXT'
    FAIL_STATE = 'FAILED'
    LICENSE_STATE = 'LICENSED'
    INSTALL_STATE = 'INSTALL'
    AUTO_METHOD = 'AUTOMATIC'
    MANUAL_METHOD = 'MANUAL'
    ACCEPTED_EULA = "ACCEPTED_EULA"

    def __init__(self, *args, **kwargs):
        super(LicensePool, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('baseRegKey', '')
        self.setdefault('addOnKeys', [])
        self.setdefault('eulaText', '')
        self.setdefault('state', '')
        self.setdefault('licenseText', '')
        self.setdefault('method', '')
        self.setdefault("deviceReference", Reference())
        self.setdefault("deviceGroupReference", Reference())

    def removeBlankFields(self):
        """ Go through the object and remove all fields that do not contain
            any data, so that the REST call will work properly.
            See BZ553222.
        """
        if ('addOnKeys' in self) is True and\
           len(self['addOnKeys']) <= 0:
            del self['addOnKeys']
        if ('baseRegKey' in self) is True and\
           self['baseRegKey'] == '':
            del self['baseRegKey']
        if ('deviceGroupReference' in self) is True and\
           len(self['deviceGroupReference']) <= 0:
            del self['deviceGroupReference']
        if ('deviceReference' in self) is True and\
           len(self['deviceReference']) <= 0:
            del self['deviceReference']
        if ('eulaText' in self) is True and\
           self['eulaText'] == '':
            del self['eulaText']
        if ('dossier' in self) is True and\
           self['dossier'] == '':
            del self['dossier']
        if ('licenseText' in self) is True and\
           self['licenseText'] == '':
            del self['licenseText']
        if ('method' in self) is True and\
           self['method'] == '':
            del self['method']
        if ('name' in self) is True and\
           self['name'] == '':
            del self['name']
        if ('selfLink' in self) is True and\
           self['selfLink'] == '':
            del self['selfLink']
        if ('state' in self) is True and\
           self['state'] == '':
            del self['state']
        if ('uuid' in self) is True and\
           self['uuid'] == '':
            del self['uuid']

    @staticmethod
    def wait(rest, pool, automatic, timeout=10):

        states = (LicensePool.WAITING_STATE, LicensePool.LICENSE_STATE) if automatic \
            else (LicensePool.WAITING_STATE_MANUAL, LicensePool.LICENSE_STATE)

        ret = wait(lambda: rest.get(pool.selfLink),
                   condition=lambda x: x.state in states,
                   progress_cb=lambda x: 'State: {0} '.format(x.state),
                   timeout=timeout, interval=1)

        if ret.state in LicensePool.FAIL_STATE:
            Task.fail('Licensing failed', ret)

        return ret


class DeviceInventory(BaseApiObject):
    URI = '/mgmt/cm/shared/device-inventory'
    FINISH_STATE = 'FINISHED'
    FAIL_STATE = 'FAILED'

    def __init__(self, *args, **kwargs):
        super(DeviceInventory, self).__init__(*args, **kwargs)
        self.setdefault('devicesQueryUri', '')

    @staticmethod
    def wait(rest, identifier, timeout=10):

        ret = wait(lambda: rest.get(DeviceInventory.URI + '/' + identifier),
                   condition=lambda x: x.status == DeviceInventory.FINISH_STATE,
                   progress_cb=lambda x: 'State: {0} '.format(x.status),
                   timeout=timeout, interval=1)
        if ret.status == DeviceInventory.FAIL_STATE:
            Task.fail('Post Failed to get Device ID', ret)

        return ret


class LicenseRegistrationKey(BaseApiObject):
    URI = '/mgmt/cm/shared/licensing/registrations'
    ITEM_URI = '/mgmt/cm/shared/licensing/registrations/%s'

    def __init__(self, *args, **kwargs):
        super(LicenseRegistrationKey, self).__init__(*args, **kwargs)
        self.setdefault('registrationKey', '')


class EventAggregationTasks(BaseApiObject):
    """To be used on each BQ to create a listening task"""
    URI = '/mgmt/shared/analytics/event-aggregation-tasks'
    ITEM_URI = '/mgmt/shared/analytics/event-aggregation-tasks/%s'
    STATS_ITEM_URI = '/mgmt/shared/analytics/event-aggregation-tasks/%s/worker/stats'
    PORT = 9010  # some default test port

    def __init__(self, *args, **kwargs):
        super(EventAggregationTasks, self).__init__(*args, **kwargs)
        self.setdefault('sysLogConfig',
                        AttrDict(tcpListenEndpoint='http://localhost:{0}'.format(self.PORT),
                                 isRfc5424=False,  # not to use rfc5424
                                 ))
        self.setdefault('eventSourcePollingIntervalMillis', 1000)
        self.setdefault('itemCountCommitThreshold', 100)  # mandatory see BZ521994
        self.setdefault('isIndexingRequired', True)
        self.setdefault('name', 'test-aggregation-task01')
        self.setdefault('kind', 'shared:analytics:event-aggregation-tasks:eventaggregationstate')
        self.setdefault('description', 'Test.EAT')
        # self.setdefault('generation', 0)
        # self.setdefault('lastUpdateMicros', 0)
        self.setdefault('eventExpirationMicros', 31536000000000)  # Since GF - 365 days - is backwards compatible


class EventAnalysisTasks(BaseApiObject):
    """To be used on default (main) BQ to create an analysis task"""
    URI = '/mgmt/shared/analytics/event-analysis-tasks'
    ITEM_URI = '/mgmt/shared/analytics/event-analysis-tasks/%s'

    def __init__(self, *args, **kwargs):
        super(EventAnalysisTasks, self).__init__(*args, **kwargs)

        self.setdefault('collectFilteredEvents', False)
        self.setdefault('histograms',
                        [
                        AttrDict(# sourceEventProperty='hostname',  # MANDATORY
                                 sourceEventProperty='unit_hostname',  # MANDATORY
                                 # durationTimeUnit='MINUTES',  # MANDATORY
                                 durationTimeUnit='SECONDS',  # MANDATORY
                                 # durationTimeUnit='HOURS',  # MANDATORY
                                 durationLength=240,  # MANDATORY
                                 nBins=1,  # MANDATORY
                                 # mode='SUM',
                                 selectionQueryType='ODATA',  # MANDATORY
                                 orderByEventProperty="management_ip_address",
                                 eventFilter="unit_hostname eq '*'",
                                 timestampEventProperty='eventConversionDateTime',
                                 timeUpperBoundMicrosUtc=1400181224388389,  # MANDATORY if isRelativeToNow is False
                                 isRelativeToNow=False,  # if False, strictly tight to timeUpperBoundMicrosUtc
                                 # sourceEventProperty="aCounter",
                                 # totalEventCount=0,
                                 )
                        ]
                        )


class UtilityLicense(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/utility-licenses'
    ITEM_URI = '/mgmt/cm/system/licensing/utility-licenses/%s'

    AUTOMATIC_ACTIVATION_STATES = enum('ACTIVATING_AUTOMATIC', 'ACTIVATING_AUTOMATIC_EULA_ACCEPTED')

    MANUAL_ACTIVATION_STATES = enum('ACTIVATING_MANUAL', 'ACTIVATING_MANUAL_LICENSE_TEXT_PROVIDED',
                                    'ACTIVATING_MANUAL_OFFERINGS_LICENSE_TEXT_PROVIDED')

    WAITING_STATES = ['ACTIVATING_AUTOMATIC_NEED_EULA_ACCEPT', 'ACTIVATING_AUTOMATIC_OFFERINGS',
                      'ACTIVATING_MANUAL_NEED_LICENSE_TEXT', 'ACTIVATING_MANUAL_OFFERINGS_NEED_LICENSE_TEXT']

    FAILED_STATES = ['ACTIVATION_FAILED_OFFERING', 'ACTIVATION_FAILED']

    SUCCESS_STATE = ['READY']

    def __init__(self, *args, **kwargs):
        super(UtilityLicense, self).__init__(*args, **kwargs)
        self.setdefault('regKey', '')
        self.setdefault('addOnKeys', [])
        self.setdefault('name', '')
        self.setdefault('status', '')
        self.setdefault('licenseText', '')
        self.setdefault('eulaText', '')
        self.setdefault('dossier', '')

    @staticmethod
    def wait(rest, uri, wait_for_status, timeout=30, interval=1):

        resp = wait(lambda: rest.get(uri), condition=lambda temp: temp.status in wait_for_status,
                    progress_cb=lambda temp: 'Status: {0}, Message: {1}' .format(temp.status, temp.message), timeout=timeout, interval=interval)

        return resp


class OfferingsCollection(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/utility-licenses/%s/offerings'
    OFFERING_URI = '/mgmt/cm/system/licensing/utility-licenses/%s/offerings/%s'

    def __init__(self, *args, **kwargs):
        super(OfferingsCollection, self).__init__(*args, **kwargs)
        self.setdefault('status', '')
        self.setdefault('licenseText', '')


class MembersCollection(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/utility-licenses/%s/offerings/%s/members'
    MEMBER_URI = '/mgmt/cm/system/licensing/utility-licenses/%s/offerings/%s/members/%s'

    UNIT_OF_MEASURE = enum('hourly', 'daily', 'monthly', 'yearly')

    WAITING_STATE = 'INSTALLING'
    FAILED_STATE = 'INSTALLATION_FAILED'
    SUCCESS_STATE = 'LICENSED'

    def __init__(self, *args, **kwargs):
        super(MembersCollection, self).__init__(*args, **kwargs)
        self.setdefault('unitOfMeasure', '')
        self.setdefault('deviceMachineId', '')

    @staticmethod
    def wait(rest, uri, wait_for_status, timeout=30, interval=1):

        resp = wait(lambda: rest.get(uri), condition=lambda temp: temp.status == wait_for_status,
                    progress_cb=lambda temp: 'Status: {0}, Message: {1}' .format(temp.status, temp.message), timeout=timeout, interval=interval)

        return resp


class ReportWorker(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/utility-license-reports'
    ITEM_URI = '/mgmt/cm/system/licensing/utility-license-reports/%s'

    REPORT_TYPE = enum('JSON', 'CSV')

    WAITING_STATE = 'STARTED'
    SUCCESS_STATE = 'FINISHED'

    def __init__(self, *args, **kwargs):
        super(ReportWorker, self).__init__(*args, **kwargs)
        self.setdefault('regKey', '')
        self.setdefault('offering', '')
        self.setdefault('reportStartDateTime', '')
        self.setdefault('reportEndDateTime', '')
        self.setdefault('reportType', ReportWorker.REPORT_TYPE.JSON)

    @staticmethod
    def wait(rest, uri, timeout=30):

        resp = wait(lambda: rest.get(uri), condition=lambda temp: temp.status == ReportWorker.SUCCESS_STATE,
                    progress_cb=lambda temp: 'Status: {0}' .format(temp.status), timeout=timeout)

        return resp


class AuditWorker(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/audit'
    ITEM_URI = '/mgmt/cm/system/licensing/audit/%s'

    STATUS = enum('GRANTED', 'REVOKED')


class ResourceGroup(BaseApiObject):
    URI = '/mgmt/shared/authz/resource-groups'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(ResourceGroup, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('resources', [])


class RemoteResource(BaseApiObject):
    URI = '/mgmt/shared/authz/remote-resources'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(RemoteResource, self).__init__(*args, **kwargs)
        self.setdefault('roleReference', Reference())
        self.setdefault('deviceGroupReferences', ReferenceList())
        self.setdefault('resourceGroupReferences', ReferenceList())


class RbacHelper(BaseApiObject):
    URI = '/mgmt/cm/system/rbac-helper'
    ROLE_TYPE = enum('READONLY', 'EDITOR')

    def __init__(self, *args, **kwargs):
        super(RbacHelper, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('description', '')
        self.setdefault('roleType', RbacHelper.ROLE_TYPE.READONLY)
        self.setdefault('deviceGroupReference', Reference())


class AuthnLocalGroups(BaseApiObject):
    URI = '/mgmt/shared/authn/providers/local/groups'

    def __init__(self, *args, **kwargs):
        super(AuthnLocalGroups, self).__init__(*args, **kwargs)
        self.setdefault('name', '')


class DiagnosticsRuntime(BaseApiObject):
    URI = '/mgmt/shared/diagnostics/runtime'


class ESIndices(BaseApiObject):
    # Rest collection worker showing Elastic Search indices
    URI = '/mgmt/cm/shared/esmgmt/cluster/%s/indices'
    ITEM_URI = '/mgmt/cm/shared/esmgmt/cluster/%s/indices/%s'

    def __init__(self, *args, **kwargs):
        super(ESIndices, self).__init__(*args, **kwargs)
        self.setdefault('isOriginator', True)
        self.setdefault('indexName', 'test_index')
        self.setdefault('indexType', 'TIME_BASED')
        self.setdefault('shardCount', 1)
        self.setdefault('replicaCount', 1)
        self.setdefault('maxIndexCount', 1)
        self.setdefault('source', 'asm')


class ESInstance(BaseApiObject):
    # Rest collection worker showing Elastic Search state
    URI = '/mgmt/cm/shared/esmgmt/cluster'
    ITEM_URI = '/mgmt/cm/shared/esmgmt/cluster/%s'

    def __init__(self, *args, **kwargs):
        super(ESInstance, self).__init__(*args, **kwargs)


class ESTasks(BaseApiObject):
    # worker showing Elastic Search task state
    URI = 'mgmt/cm/shared/esmgmt/cluster-task'

    def __init__(self, *args, **kwargs):
        super(ESTasks, self).__init__(*args, **kwargs)


class ESSnapshotTasks(BaseApiObject):
    # worker for elastic search snapshot tasks
    URI = '/mgmt/cm/shared/esmgmt/es-snapshot-task'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(ESSnapshotTasks, self).__init__(*args, **kwargs)


class ESSnapshots(BaseApiObject):
    # REST worker for taking snapshots of elastic search data
    URI = '/mgmt/cm/shared/esmgmt/es-snapshots'

    def __init__(self, *args, **kwargs):
        super(ESSnapshots, self).__init__(*args, **kwargs)


class ESRestore(BaseApiObject):
    # REST worker for restoring snapshots of elastic search data
    URI = '/mgmt/cm/shared/esmgmt/es-restore-task'

    def __init__(self, *args, **kwargs):
        super(ESRestore, self).__init__(*args, **kwargs)
        self.setdefault('snapshotReference', {})


class ESHealth(BaseApiObject):
    # Rest collection worker showing Elastic Search health
    URI = '/mgmt/cm/shared/esmgmt/health'

    def __init__(self, *args, **kwargs):
        super(ESHealth, self).__init__(*args, **kwargs)


class AddSyslogListener(BaseApiObject):
    # Rest collection worker responsible for activating the syslog listener
    URI = 'mgmt/cm/asm/tasks/add-syslog-listener'

    def __init__(self, *args, **kwargs):
        super(AddSyslogListener, self).__init__(*args, **kwargs)
        self.setdefault('module', 'asm')
        self.setdefault('deviceReference', {})


class SyslogListenerTasks(BaseApiObject):
    # Rest collection worker showing the status of the last task run
    URI = 'mgmt/cm/asm/tasks/sysloglistener'

    def __init__(self, *args, **kwargs):
        super(SyslogListenerTasks, self).__init__(*args, **kwargs)


class RemoveSyslogListener(BaseApiObject):
    # Rest collection worker responsible for deactivating the syslog listener
    URI = 'mgmt/cm/asm/tasks/remove-syslog-listener'

    def __init__(self, *args, **kwargs):
        super(RemoveSyslogListener, self).__init__(*args, **kwargs)
        self.setdefault('module', 'asm')
        self.setdefault('indexName', 'asmindex')
        self.setdefault('deviceReference', {})


class ESAddNode(BaseApiObject):
    # Add node  workflow task worker
    URI = 'mgmt/cm/shared/esmgmt/add-node/'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(ESAddNode, self).__init__(*args, **kwargs)
        self.setdefault('httpPort', '9200')
        self.setdefault('transportPort', '9300')


class ESRemoveNode(BaseApiObject):
    # Remove node  workflow task worker
    URI = 'mgmt/cm/shared/esmgmt/remove-node/'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(ESRemoveNode, self).__init__(*args, **kwargs)
        self.setdefault('deviceReference', {})


class Diagnostics(BaseApiObject):
    URI = '/mgmt/shared/diagnostics'
    TYPE = enum('FINE', 'FINER', 'FINEST', 'ALL', 'OFF')

    def __init__(self, *args, **kwargs):
        super(Diagnostics, self).__init__(*args, **kwargs)
        self.setdefault('operationTracingLevel', Diagnostics.TYPE.FINE)
        self.setdefault('traceLimitPerWorker', 100)
        self.setdefault('frameworkLogLevel', 'INFO')
        self.setdefault('workerLogLevel', 'INFO')
        self.setdefault('uriPathWhiteList', ["**"])


class DiagnosticsTraces(BaseApiObject):
    URI = '/mgmt/shared/diagnostics/traces'

    def __init__(self, *args, **kwargs):
        super(DiagnosticsTraces, self).__init__(*args, **kwargs)
        self.setdefault('operationTracingLevel', 'OFF')
        self.setdefault('traceLimitPerWorker', 100)
        self.setdefault('traces', {})


class DiagnosticsLogs(BaseApiObject):
    URI = '/mgmt/shared/diagnostics/logs'


class DiagnosticsTopAggrTraceStats(BaseApiObject):
    URI = '/mgmt/shared/diagnostics/top-aggregated-trace-stats'


class TaskScheduler(BaseApiObject):
    """defauults on the Task Schedule Payload"""
    URI = '/mgmt/shared/task-scheduler/scheduler'
    ITEM_URI = '/mgmt/shared/task-scheduler/scheduler/%s'

    TYPE = enum('BASIC_WITH_INTERVAL',
                'DAYS_OF_THE_WEEK',
                'DAY_AND_TIME_OF_THE_MONTH',
                'BASIC_WITH_REPEAT_COUNT')
    UNIT = enum('MILLISECOND', 'SECOND', 'MINUTE', 'HOUR',
                'DAY', 'WEEK', 'MONTH', 'YEAR')

    def __init__(self, *args, **kwargs):
        super(TaskScheduler, self).__init__(*args, **kwargs)
        # Good Optionals:
        self.setdefault('name', "test-schedule-01")
        self.setdefault('description', "description for this task - test")

        # Type BASIC
        self.setdefault('scheduleType', TaskScheduler.TYPE.BASIC_WITH_INTERVAL)
        self.setdefault('interval', 30)
        self.setdefault('intervalUnit', TaskScheduler.UNIT.SECOND)

        # Other Required
        self.setdefault('deviceGroupName', 'cm-shared-all-big-iqs')
        self.setdefault('taskReferenceToRun', '')  # URI to be run on this S
        self.setdefault('taskBodyToRun', AttrDict())  # State Object (Eg: EventAnalyticsTaskState)
        self.setdefault('taskRestMethodToRun', 'GET')

        # Optionals
        self.setdefault('endDate', None)  # date
        self.setdefault('timeoutInMillis', 60000)  # wait for completion of task; Default from api is 60s


class AvrTask(Task):

    def wait_analysis(self, rest, resource, loop=None, timeout=30, interval=1,
                      timeout_message=None):
        def get_status():
            return rest.get(resource.selfLink)
        if loop is None:
            loop = get_status
        ret = wait(loop, timeout=timeout, interval=interval,
                   timeout_message=timeout_message,
                   condition=lambda x: x.status not in ('STARTED',),
                   progress_cb=lambda x: 'Status: {0}'.format(x.status))
        assert ret.status == 'FINISHED', "{0.status}:{0.errorMessage}".format(ret)
        return ret


class AvrAggregationTasks(BaseApiObject):
    # avrAggregationTask is a singleton created by restjavad. It's created at startup and no need to delete it
    URI = "/mgmt/shared/analytics/avr-aggregation-tasks"
    ITEM_URI = "/mgmt/shared/analytics/avr-aggregation-tasks/%s"

    def __init__(self, *args, **kwargs):
        super(AvrAggregationTasks, self).__init__(*args, **kwargs)


class GroupTask(Task):
    URI = "/mgmt/shared/group-task"
    DSC_GROUP_URI = "/mgmt/shared/system/dsc-group/"
    DSC_GROUP_ITEM_URI = "/mgmt/shared/system/dsc-group/%s"
    DSC_GROUP_TASK_URI = "/mgmt/shared/system/dsc-group-task/"

    def __init__(self, *args, **kwargs):
        super(GroupTask, self).__init__(*args, **kwargs)
        self.setdefault('devicesReference', Reference())
        self.setdefault('taskReference', Reference())
        self.setdefault('taskBody', AttrDict())


class WorkingLtmNode(BaseApiObject):
    URI = '/mgmt/cm/shared/config/working/ltm/node'

    def __init__(self, *args, **kwargs):
        super(WorkingLtmNode, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('fullPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('monitor', '/Common/icmp')


class WorkingLtmPool(BaseApiObject):
    URI = '/mgmt/cm/shared/config/working/ltm/pool'

    def __init__(self, *args, **kwargs):
        super(WorkingLtmPool, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('fullPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('monitor', '/Common/http')


class WorkingLtmPoolMember(BaseApiObject):
    URI = '/mgmt/cm/shared/config/working/ltm/pool/%s/members'

    def __init__(self, *args, **kwargs):
        super(WorkingLtmPoolMember, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('fullPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('nodeReference', Reference())
        self.setdefault('monitor', 'default')


class WorkingLtmVirtualAddress(BaseApiObject):
    URI = '/mgmt/cm/shared/config/working/ltm/virtual-address'

    def __init__(self, *args, **kwargs):
        super(WorkingLtmVirtualAddress, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('mask', '')
        self.setdefault('subPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())


class SourceAddressTranslation(AttrDict):
    def __init__(self, *args, **kwargs):
        super(SourceAddressTranslation, self).__init__(*args, **kwargs)
        self.setdefault('type', 'automap')


class WorkingLtmVip(BaseApiObject):
    URI = '/mgmt/cm/shared/config/working/ltm/virtual'

    def __init__(self, *args, **kwargs):
        super(WorkingLtmVip, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('destination', '')
        self.setdefault('fullPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('poolReference', Reference())
        self.setdefault('pool', '')
        self.setdefault('disabled', False)
        self.setdefault('enabled', True)
        self.setdefault('translateAddress', 'enabled')
        self.setdefault('translatePort', 'enabled')
        self.setdefault('sourceAddressTranslation', SourceAddressTranslation()),
        # the following are added for virtual server modeling
        self.setdefault('ipProtocol', ''),
        self.setdefault('iRuleReferences', ReferenceList()),
        self.setdefault('isMirrorEnabled', False),
        self.setdefault('virtualAddressReference', Reference()),
        self.setdefault('destinationPort', ''),
        self.setdefault('subPath', ''),
        self.setdefault('mask', '')


class SnapshotTask(Task):
    URI = "/mgmt/shared/snapshot-task"

    def __init__(self, *args, **kwargs):
        super(SnapshotTask, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('collectionReferences', ReferenceList())


class ConfigDeploy(Task):
    """ This can be used to do ADC deployment """
    URI = '/mgmt/cm/shared/config/deploy'

    def __init__(self, *args, **kwargs):
        super(ConfigDeploy, self).__init__(*args, **kwargs)
        self.setdefault('name', 'Deployment')
        self.setdefault('description', 'Deployment')
        self.setdefault('configPaths', [])
        self.setdefault('kindTransformMappings', [])
        self.setdefault('deviceReference', Reference())


class RefreshCurrentConfig(Task):
    URI = '/mgmt/cm/shared/config/refresh-current-config'

    def __init__(self, *args, **kwargs):
        super(RefreshCurrentConfig, self).__init__(*args, **kwargs)
        self.setdefault('configPaths', [])
        self.setdefault('deviceReference', Reference())


class RefreshWorkingConfig(Task):
    URI = '/mgmt/cm/shared/config/refresh-working-config'

    def __init__(self, *args, **kwargs):
        super(RefreshWorkingConfig, self).__init__(*args, **kwargs)
        self.setdefault('configPaths', [])
        self.setdefault('deviceReference', Reference())


class DeviceAvailability(BaseApiObject):
    URI = '/mgmt/shared/device-availability'

    def __init__(self, *args, **kwargs):
        super(DeviceAvailability, self).__init__(*args, **kwargs)


class DiagnosticsMetricsTask(BaseApiObject):
    URI = '/mgmt/shared/diagnostics/metrics-task'
    ITEM_URI = '%s/%%s' % URI
    METRICS_URI = '/mgmt/shared/diagnostics/metrics/%s'
    METRICS_TYPE = enum(CPU='cpu',
                        MEMORY='memory',
                        NETWORK='network',
                        DISK='disk',
                        RESTJAVAD='restjavad')

    LATEST_METRICS_TYPE = enum(CPU='latest/cpu',
                               MEMORY='latest/memory',
                               NETWORK='latest/network',
                               DISK='latest/disk',
                               RESTJAVAD='latest/restjavad')

    AGGREGATIONLATEST_METRICS_TYPE = enum(CPU='aggregation/cpu',
                                          MEMORY='aggregation/memory',
                                          NETWORK='aggregation/network',
                                          DISK='aggregation/disk',
                                          RESTJAVAD='aggregation/restjavad')

    DEFAULT_DIRECTORIES = ['/var/config/rest/downloads',
                           '/var/config/rest/index',
                           '/var/config/rest/storage',
                           '/var/config/rest/utility-license-reports',
                           '/var/log',
                           '/shared/avr_reports',
                           '/shared/core',
                           '/shared/images',
                           '/shared/tmp',
                           '/shared/ucs_backups',
                           '/tmp']

    def __init__(self,
                 directories,
                 *args,
                 **kwargs):
        super(DiagnosticsMetricsTask, self).__init__(*args, **kwargs)
        self.setdefault('pollingIntervalMS', 10000)
        self.setdefault('groomingIntervalMS', 86400000)
        self.setdefault('cpuDivisor', 1)
        self.setdefault('memoryDivisor', 1)
        self.setdefault('networkDivisor', 3)
        self.setdefault('diskDivisor', 6)
        self.setdefault('restjavadDivisor', 6)
        if directories is not None:
            self.setdefault('diskDirectories', directories)

    @staticmethod
    def available_wait(rest, task_id, timeout=60):
        ret = wait(lambda: rest.get(DiagnosticsMetricsTask.ITEM_URI % task_id),
                   condition=lambda x: (x.status == "STARTED"),
                   progress_cb=lambda x: 'State: {0}'.format(x.status),
                   timeout=timeout, interval=1)
        return ret

    @staticmethod
    def cancel_wait(rest, resource, timeout=60):
        ret = wait(lambda: rest.get(resource.selfLink),
                   condition=lambda x: (x.status == "CANCELED"),
                   progress_cb=lambda x: 'State: {0}'.format(x.status),
                   timeout=timeout, interval=5)
        return ret

    @staticmethod
    def next_polling_data_wait(rest, uri, initialSampleCount, interval, timeout=300):
        ret = wait(lambda: rest.get(uri),
                   condition=lambda x: (x.totalItems == initialSampleCount + 1),
                   progress_cb=lambda x: 'SampleCount: {0}'.format(x.totalItems),
                   timeout=timeout, interval=interval)
        return ret


class DiagnosticsMetricsTaskVersionTwo(DiagnosticsMetricsTask):
    """ Use this class for BIG-IQ version 5.0 (Green Flash).
    This class is not backward compatible with previous versions of BIG-IQ.
    """
    DEFAULT_DIRECTORIES = ['/var/config/rest/access',
                           '/var/config/rest/downloads',
                           '/var/config/rest/index',
                           '/var/config/rest/license-reports',
                           '/var/config/rest/toku/data',
                           '/var/log',
                           '/shared/avr_reports',
                           '/shared/core',
                           '/shared/images',
                           '/shared/tmp',
                           '/shared/ucs_backups',
                           '/tmp']

    def __init__(self, directories, *args, **kwargs):
        self.setdefault('pollingIntervalMS', 10000)
        self.setdefault('groomingIntervalMS', 86400000)
        self.setdefault('cpuDivisor', 2)
        self.setdefault('memoryDivisor', 3)
        self.setdefault('networkDivisor', 5)
        self.setdefault('diskDivisor', 7)
        self.setdefault('restjavadDivisor', 11)
        super(DiagnosticsMetricsTaskVersionTwo, self).__init__(directories, *args, **kwargs)


class SystemSetup(BaseApiObject):
    URI = '/mgmt/shared/system/setup'

    def __init__(self, *args, **kwargs):
        super(SystemSetup, self).__init__(*args, **kwargs)
        self.setdefault('isAdminPasswordChanged', True)
        self.setdefault('isRootPasswordChanged', True)
        self.setdefault('isSystemSetup', True)


class MgmtTime(BaseApiObject):
    """returns in micros from epoch with 15 digits"""
    URI = '/mgmt/shared/time'

    def __init__(self, *args, **kwargs):
        super(MgmtTime, self).__init__(*args, **kwargs)
        self.setdefault('nowMicrosUtc', 1457656725438168)  # return example

class OnboardingEvent(BaseApiObject):
    URI = '/mgmt/cm/cloud/tasks/configure-device-node/event/types'
    ITEM_URI = '%s/%%s' % URI
    EVENT_TYPE = enum(CONFIG_CONSTRUCTED='onBigIpConfigConstructed',
                      AVAILABLE='onBigIpAvailable',
                      LICENSED='onBigIpLicensed')

    def __init__(self,
                 *args,
                 **kwargs):
        super(OnboardingEvent, self).__init__(*args, **kwargs)

class OnActiveEvent(BaseApiObject):
    URI = '/mgmt/shared/device-discovery-tasks/event/types/onActive'

    def __init__(self,
                 *args,
                 **kwargs):
        super(OnActiveEvent, self).__init__(*args, **kwargs)
