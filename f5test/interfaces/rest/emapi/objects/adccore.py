'''
Created on Dec 4, 2015

/mgmt/cm/adc-core workers

@author: langer
'''
from .base import Reference, ReferenceList, CmTask
from ...base import BaseApiObject
from .....base import AttrDict, enum


class AdcDeclareMgmtAuthorityTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'declare-mgmt-authority')
    URI_ITEM = URI + '/{0}'

    def __init__(self, *args, **kwargs):
        super(AdcDeclareMgmtAuthorityTask, self).__init__(*args, **kwargs)
        self.setdefault('isNewDevice', True)
        self.setdefault('deviceUsername', 'admin')


class AdcRemoveMgmtAuthorityTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'remove-mgmt-authority')

    def __init__(self, *args, **kwargs):
        super(AdcRemoveMgmtAuthorityTask, self).__init__(*args, **kwargs)
        self.setdefault('deviceReference', Reference())


class AdcDeployConfigTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'deploy-configuration')

    REQUEST_ATTRIBUTE = enum('name',
                             'description',
                             'skipDistribution',
                             'reevaluate',
                             'deviceReferences',
                             'deviceGroupReference',
                             'snapshotReference',
                             'childSnapshotReference')
    REQUIRED_REQUEST_ATTRIBUTES = {'name'}
    ATTRIBUTE_DEFAULTS = {'name': 'test deployment',
                          'description': 'deployment description',
                          'skipDistribution': False,
                          'reevaluate': False,
                          'deviceReferences': ReferenceList()  # Deploys to all devices if this isn't provided
                          # The following are here for tester reference, and shouldn't be
                          # 'deviceGroupReference': Reference(),  # Mutually exclusive with deviceReferences
                          # 'snapshotReference': Reference()  #
                          # 'childSnapshotReference': Reference
                          }
    RESPONSE_ATTRIBUTE = enum('deviceReferences',
                              'currentStep',
                              'deviceDetails',
                              'username',
                              'id',
                              'status',
                              'startTime',
                              'name',
                              'userReference',
                              'identityReferences',
                              'ownerMachineId',
                              'generation',
                              'lastUpdateMicros',
                              'kind',
                              # 'noDifferenceFound',
                              # 'skipVerifyConfig',
                              'selfLink'
                              )
    STEP = enum('CHECK_LICENSE',
                'CHECK_OTHER_RUNNING_TASKS',
                'GET_DEVICES',
                'CHECK_DEVICE_AVAILABILITY',
                'LOOKUP_CLUSTERS',
                'REFRESH_CURRENT_CONFIG_REST',
                'CREATE_SNAPSHOT',
                'CREATE_DIFFERENCE',
                'VERIFY_CONFIG',
                'GET_CHILD_DEPLOY_DEVICES',
                'START_CHILD_DEPLOY',
                'WAIT_FOR_CHILD_DEPLOY',
                'DISTRIBUTE_CONFIG',
                'CLEANUP_PREVIOUS_EVALUATE',
                'DISTRIBUTE_CONFIG_REST',
                'DISTRIBUTE_DSC_CLUSTERS',
                'FOLDBACK_DEPLOYED_ADDITIONS',
                'POST_DEPLOYMENT',
                'REFRESH_WORKING_CONFIG',
                'GET_DEPLOYMENT_TRACKERS',
                'DONE')

    def __init__(self, *args, **kwargs):
        super(AdcDeployConfigTask, self).__init__(*args, **kwargs)

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self


class AdcSnapshotConfigTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'snapshot-config')

    def __init__(self, *args, **kwargs):
        super(AdcSnapshotConfigTask, self).__init__(*args, **kwargs)
        self.setdefault('name', 'my_snapshot')


class AdcDifferenceConfigTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'difference-config')

    def __init__(self, *args, **kwargs):
        super(AdcDifferenceConfigTask, self).__init__(*args, **kwargs)
        self.setdefault('name', 'my_difference_config_task')
        self.setdefault('description', 'Difference between snapshot and Working Config')
        self.setdefault('fromStateReference', Reference())
        self.setdefault('toStateReference', Reference())


class AdcRestoreConfigTask(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'restore-config')

    def __init__(self, *args, **kwargs):
        super(AdcRestoreConfigTask, self).__init__(*args, **kwargs)
        self.setdefault('name', 'my_restore_config_task')
        self.setdefault('description', 'restore the snapshot')
        self.setdefault('snapshotReference', Reference())


class WorkingLtmNode(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/node'
    ITEM_URI = URI + '/%s'

    # Also 'stateStatus' and 'sessionStatus'?
    REQUEST_ATTRIBUTE = enum('name', 'partition', 'description', 'address', 'deviceReference', 'connectionLimit',
                             'dynamicRatio', 'isEphemeral', 'isLoggingEnabled', 'rateLimit', 'ratio', 'fqdn', 'monitor',
                             'subPath')

    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'deviceReference', 'address'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Node',
                          'partition': 'Common',
                          'deviceReference': Reference(),
                          'address': '10.10.10.10'
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self

    def set_legacy_defaults(self):
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('monitor', '/Common/icmp')
        return self


class WorkingLtmPool(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/pool'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'description', 'deviceReference', 'allowNat', 'allowSnat',
                             'ignorePersistedWeight', 'linkQosToClient', 'linkQosToServer', 'loadBalancingMode',
                             'monitorReferences', 'minActiveMembers', 'minUpMembers', 'queueDepthLimit',
                             'enableQueueOnConnectionLimit', 'queueTimeLimit', 'serviceDownAction', 'slowRampTime',
                             'reselectTries', 'membersReference', 'profiles', 'requestQueueTimeLimit',
                             'ipTosToClientControl', 'ipTosToServerControl')

    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'deviceReference', 'loadBalancingMode'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Pool',
                          'partition': 'Common',
                          'deviceReference': Reference(),
                          'loadBalancingMode': 'round-robin'
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self

    def set_legacy_defaults(self):
        self.setdefault('name', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('loadBalancingMode', 'round-robin')
        return self


class WorkingLtmPoolMember(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/pool/%s/members'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'nodeReference', 'ratio', 'priorityGroup', 'connectionLimit',
                             'rateLimit', 'isLoggingEnabled', 'dynamicRatio', 'description', 'port')

    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'nodeReference'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Node:80',
                          'partition': 'Common',
                          'nodeReference': Reference(),
                          'port': 80
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self

    def set_legacy_defaults(self):
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('partition', '')
        self.setdefault('nodeReference', Reference())
        return self


class SourceAddressTranslation(AttrDict):
    def __init__(self, *args, **kwargs):
        super(SourceAddressTranslation, self).__init__(*args, **kwargs)
        self.setdefault('type', 'automap')


class WorkingLtmVip(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/virtual'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'deviceReference', 'sourceAddress', 'destination', 'mask')
    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'deviceReference', 'sourceAddress', 'destination', 'mask'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Virtual-Server',
                          'partition': 'Common',
                          'deviceReference': Reference(),
                          'sourceAddress': '0.0.0.0/0',
                          'destination': '10.10.10.10:80',
                          'mask': '255.255.255.255'
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self

    def set_legacy_defaults(self):
        self.setdefault('name', '')
        self.setdefault('destination', '')
        self.setdefault('fullPath', '')
        self.setdefault('partition', '')
        self.setdefault('deviceReference', Reference())
        self.setdefault('poolReference', Reference())
        self.setdefault('sourceAddressTranslation', SourceAddressTranslation())
        self.setdefault('sourceAddress', '0.0.0.0/0')
        self.setdefault('ipProtocol', 'tcp')
        self.setdefault('iRuleReferences', ReferenceList())
        self.setdefault('mask', '255.255.255.255')
        return self


class WorkingLtmVipProfile(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/virtual/%s/profiles'
    ITEM_URI = URI + '/%s'

    # The * in profile*Reference corresponds to the type of profile it is and should not be used literally.
    # e.g. 'Udp' for:
    # {"link":"https://localhost/mgmt/cm/adc-core/working-config/ltm/profiles/udp/223f2554-d7d9-31e7-8c71-ca059cdcdb0c"}
    # TODO: Add all possible profile*Reference types to enum list.
    REQUEST_ATTRIBUTE = enum('name', 'partition', 'profile*Reference', 'context')
    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'profile*Reference', 'context'}
    ATTRIBUTE_DEFAULTS = {'name': 'fastL4',
                          'partition': 'Common',
                          'profileFastl4Reference': Reference(),
                          'context': 'all'  # '3ll', 'clientside', or 'serverside
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self


class WorkingLtmIrule(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/ltm/irule'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'body', 'apiRawValues')
    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Rule',
                          'partition': 'Common',
                          'body': '',
                          'apiRawValues': {'verificationStatus': 'signature-verified'},
                          'supportedBigIpVersions': '11.5.0-HF7+'
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self


class CurrentLtmIrule(BaseApiObject):
    URI = '/mgmt/cm/adc-core/current-config/ltm/irule'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'body', 'apiRawValues')
    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition'}
    ATTRIBUTE_DEFAULTS = {'name': 'Test-Rule',
                          'partition': 'Common',
                          'body': '',
                          'apiRawValues': {'verificationStatus': 'signature-verified'},
                          'supportedBigIpVersions': '11.5.0-HF7+'
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self


class WorkingNetSelfIp(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/net/self'
    ITEM_URI = URI + '/%s'

    REQUEST_ATTRIBUTE = enum('name', 'partition', 'address', 'allowServices', 'floating', 'inheritedTrafficGroup',
                             'trafficGroupReference', 'tunnelReference', 'vlanGroupReference', 'vlanReference',
                             'deviceReference')
    REQUIRED_REQUEST_ATTRIBUTES = {'name', 'partition', 'address', 'deviceReference', 'vlanReference'}  # vlan or tunnel
    ATTRIBUTE_DEFAULTS = {'name': 'selfip',
                          'partition': 'Common',
                          }

    def set_min_defaults(self):
        self.update({x: y for (x, y) in list(self.ATTRIBUTE_DEFAULTS.items())
                     if x in self.REQUIRED_REQUEST_ATTRIBUTES})
        return self

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self

class WorkingNetTrafficGroup(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/net/traffic-group'
    ITEM_URI = URI + '/%s'

class WorkingNetVlan(BaseApiObject):
    URI = '/mgmt/cm/adc-core/working-config/net/vlan'
    ITEM_URI = URI + '/%s'


class RefreshCertificate(CmTask):
    URI = CmTask.BASE_URI % ('adc-core', 'discover-cert')
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(RefreshCertificate, self).__init__(*args, **kwargs)
        self.setdefault("deviceReference", "")


# supercedes f5test.interfaces.rest.emapi.objects.system for bigiq-mgmt-cm
class CertificateInfo(BaseApiObject):
    URI = '/mgmt/cm/adc-core/current-config/sys/file/ssl-cert'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(CertificateInfo, self).__init__(*args, **kwargs)
