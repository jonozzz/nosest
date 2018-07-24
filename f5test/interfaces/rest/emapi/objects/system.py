'''
Created on Jan 9, 2014

/mgmt/[cm|tm|shared]/system

@author: jono
'''
from .....base import enum, AttrDict
from .base import Reference, Task
from ...base import BaseApiObject
from .....utils.wait import wait


class EasySetup(BaseApiObject):
    URI = '/mgmt/shared/system/easy-setup'

    def __init__(self, *args, **kwargs):
        super(EasySetup, self).__init__(*args, **kwargs)
        self.setdefault('hostname', '')
        self.setdefault('internalSelfIpAddresses', [])
        self.setdefault('selfIpAddresses', [])
        self.setdefault('ntpServerAddresses', [])
        self.setdefault('dnsServerAddresses', [])
        self.setdefault('dnsSearchDomains', [])


class NetworkInterface(BaseApiObject):
    URI = '/mgmt/tm/cloud/net/interface'
    ITEM_URI = '/mgmt/tm/cloud/net/interface/%s'

    def __init__(self, *args, **kwargs):
        super(NetworkInterface, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('description', '')


class NetworkVlan(BaseApiObject):
    URI = '/mgmt/tm/cloud/net/vlan'
    ITEM_URI = '/mgmt/tm/cloud/net/vlan/%s'

    def __init__(self, *args, **kwargs):
        super(NetworkVlan, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('interfacesReference')


class NetworkSelfip(BaseApiObject):
    URI = '/mgmt/tm/cloud/net/self'
    ITEM_URI = '/mgmt/tm/cloud/net/self/%s'

    def __init__(self, *args, **kwargs):
        super(NetworkSelfip, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('address', '')
        self.setdefault('vlanReference', Reference())


class BackupRestoreTask(Task):
    URI = '/mgmt/cm/system/backup-restore'
    ITEM_URI = '%s/%%s' % URI
    STATUS = enum('BACKUP_GET_DEVICE', 'BACKUP_MAKE_BACKUP',
                  'BACKUP_DOWNLOAD_BACKUP', 'BACKUP_FINISHED', 'BACKUP_FAILED',

                  'RESTORE_REQUESTED', 'RESTORE_GET_DEVICE',
                  'RESTORE_UPLOAD_BACKUP', 'RESTORE_RESTORE_BACKUP',
                  'RESTORE_FINISHED', 'RESTORE_FAILED')
    PENDING_STATUSES = ('BACKUP_GET_DEVICE', 'BACKUP_MAKE_BACKUP',
                        'BACKUP_DOWNLOAD_BACKUP',
                        'RESTORE_REQUESTED', 'RESTORE_GET_DEVICE',
                        'RESTORE_UPLOAD_BACKUP', 'RESTORE_RESTORE_BACKUP')
    FINAL_STATUSES = ('BACKUP_FINISHED', 'BACKUP_FAILED',
                      'RESTORE_FINISHED', 'RESTORE_FAILED')

    def __init__(self, *args, **kwargs):
        super(BackupRestoreTask, self).__init__(*args, **kwargs)
        self.setdefault('deviceReference', Reference())
        self.setdefault('name', '')
        self.setdefault('description', '')

    @staticmethod
    def wait(rest, resource, timeout=300):

        ret = wait(lambda: rest.get(resource.selfLink),
                   condition=lambda x: (x.status in Task.FINAL_STATUSES and  # See BZ440336
                                        x.backupRestoreStatus in BackupRestoreTask.FINAL_STATUSES),
                   progress_cb=lambda x: 'State: {0}:{1}'.format(x.status,
                                                                 x.backupRestoreStatus),
                   timeout=timeout, interval=5)
        if ret.status == Task.STATUS.FAILED:  # @UndefinedVariable
            Task.fail('Task failed', ret)

        return ret

    @staticmethod
    def wait_available(rest, timeout=120):
        def backup_restore_task_available():
            resp = rest.get(BackupRestoreTask.URI + '/available')
            if not resp:
                return True

        wait(backup_restore_task_available,
             progress_cb=lambda ret: True,
             timeout=timeout,
             interval=5,
             timeout_message="Waited for 2 min.Backup "
                             "restore task is still not "
                             "available, timeout!")


class SnmpInbound(BaseApiObject):
    URI = '/mgmt/shared/system/snmp-inbound-access'

    def __init__(self, *args, **kwargs):
        super(SnmpInbound, self).__init__(*args, **kwargs)
        self.setdefault('contactInformation', '')
        self.setdefault('machineLocation', '')
        self.setdefault('clientAllowList', [])


class SnmpV1V2cAccessRecords(BaseApiObject):
    URI = '/mgmt/shared/system/snmp-v1v2c-access-records'

    def __init__(self, *args, **kwargs):
        super(SnmpV1V2cAccessRecords, self).__init__(*args, **kwargs)
        self.setdefault('community', '')
        self.setdefault('oid', '')
        self.setdefault('readOnlyAccess', True)
        self.setdefault('addressType', '')
        self.setdefault('sourceAddress', '')
        self.setdefault('id', '')


class SnmpV3AccessRecords(BaseApiObject):
    URI = '/mgmt/shared/system/snmp-v3-access-records'
    AUTHNP = enum(MD5='MD5',
                  SHA='SHA')
    PRIPRO = enum(AES='AES',
                  DES='DES')

    def __init__(self, *args, **kwargs):
        super(SnmpV3AccessRecords, self).__init__(*args, **kwargs)
        self.setdefault('username', '')
        self.setdefault('oid', '')
        self.setdefault('readOnlyAccess', True)
        self.setdefault('useAuthPasswordForPrivacy', False)
        self.setdefault('authProtocol', SnmpV3AccessRecords.AUTHNP.MD5)
        self.setdefault('authnPassword', '')
        self.setdefault('privacyProtocol', SnmpV3AccessRecords.PRIPRO.AES)
        self.setdefault('privacyPassword', '')
        self.setdefault('id', '')


class SnmpTrap(BaseApiObject):
    URI = '/mgmt/shared/system/snmp-trap-destinations'
    AUTHNP = enum(MD5='MD5',
                  SHA='SHA',
                  NONE='NONE')
    PRIPRO = enum(AES='AES',
                  DES='DES',
                  NONE='NONE')
    SLEVEL = enum(ANP='authNoPriv',
                  AP='authPriv')
    VERSION = enum(V1='V1',
                   V2C='V2C',
                   V3='V3')

    def __init__(self, *args, **kwargs):
        super(SnmpTrap, self).__init__(*args, **kwargs)
        self.setdefault('version', SnmpTrap.VERSION.V2C)
        self.setdefault('host', '')
        self.setdefault('port', '162')
        self.setdefault('securityLevel', SnmpTrap.SLEVEL.ANP)
        self.setdefault('name', '')
        self.setdefault('authProtocol', SnmpTrap.AUTHNP.MD5)
        self.setdefault('securityName', '')
        self.setdefault('engineId', '')
        self.setdefault('community', '')
        self.setdefault('authPassword', '')
        self.setdefault('privacyProtocol', SnmpTrap.PRIPRO.NONE)
        self.setdefault('privacyPassword', '')
        self.setdefault('id', '')


class Certificates(AttrDict):
    URI = '/mgmt/cm/system/certificates'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(Certificates, self).__init__(*args, **kwargs)


class CertificateInfo(AttrDict):
    URI = '/mgmt/cm/shared/config/current/cloud/sys/all-certificate-file-object'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(CertificateInfo, self).__init__(*args, **kwargs)


class SnmpDestination(AttrDict):
    URI = '/mgmt/shared/system/smtp-destinations'
    ENCRYPTION_TYPE = enum('NO_ENCRYPTION', 'SSL', 'TLS')

    def __init__(self, *args, **kwargs):
        super(SnmpDestination, self).__init__(*args, **kwargs)

        self.setdefault('name', '')
        self.setdefault('host', '')
#         self.setdefault('port', 25)
        self.setdefault('fromAddress', '')
        self.setdefault('encryptedConnection',
                        SnmpDestination.ENCRYPTION_TYPE.NO_ENCRYPTION)


class SmtpServer(AttrDict):
    URI = '/mgmt/tm/sys/smtp-server'
    ENCRYPTION_TYPE = enum(NONE='none', SSL='ssl', TLS='tls')

    def __init__(self, *args, **kwargs):
        super(SmtpServer, self).__init__(*args, **kwargs)
        self.setdefault('name', 'TestEmails')


class Contact(AttrDict):
    URI = '/mgmt/cm/system/contacts'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(Contact, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('emailAddress', '')


# Doc: ?
class EventConfiguration(AttrDict):
    URI = '/mgmt/shared/system/event-configuration'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(Contact, self).__init__(*args, **kwargs)
        self.setdefault('enabled', True)
        self.setdefault('name', '')


class SmtpEmail(AttrDict):
    URI = '/mgmt/shared/smtp-email'

    def __init__(self, *args, **kwargs):
        super(SmtpEmail, self).__init__(*args, **kwargs)
        self.setdefault('body', 'Hello world!')
        self.setdefault('subject', 'Test')
        self.setdefault('toAddresses', [])
        self.setdefault('destination', AttrDict(authentication='no',
                                                fromAddress='nobody@foo.com',
                                                host='',
                                                name='test',
                                                # password='',
                                                # userName='',
                                                port=25))


class BulkDiscovery(Task):
    URI = '/mgmt/shared/device-discovery'
    ITEM_URI = '/mgmt/shared/device-discovery/%s'
    FINISH_STATE = 'FINISHED'
    CANCEL_STATE = 'CANCELED'
    START_STATE = 'STARTED'
    # Need to look at each device's state
    PENDING_STATE = 'PENDING'
    SUCCESSFUL_STATE = ('SKIPPED', 'COMPLETED')

    def __init__(self, *args, **kwargs):
        super(BulkDiscovery, self).__init__(*args, **kwargs)
        self.setdefault('filePath', '')
        self.setdefault('groupReference', Reference())
        self.setdefault('status', '')

    @staticmethod
    def wait(rest, post_resp, *args, **kwargs):
        def all_done(ret):
            values = list(ret.deviceStatesMap.values())
            return sum(1 for x in values if x.status not in
                       BulkDiscovery.PENDING_STATE) == len(values)

        wait(lambda: rest.get(post_resp.selfLink), condition=all_done,
             progress_cb=lambda ret: 'Status: {0}'.format(list(x.status
                                                               for x in list(ret.deviceStatesMap.values()))),
             *args, **kwargs)

        ret = wait(lambda: rest.get(post_resp.selfLink),
                   condition=lambda ret: ret.status != BulkDiscovery.START_STATE,
                   progress_cb=lambda ret: 'Status: {0}'.format(ret.status),
                   *args, **kwargs)

        for value in list(ret.deviceStatesMap.values()):
            if value.status not in BulkDiscovery.SUCCESSFUL_STATE:  # @UndefinedVariable
                Task.fail('Task failed', ret)

        return ret

    @staticmethod
    def cancel_wait(rest, *args, **kwargs):

        def all_done(ret):
            return sum(1 for x in ret['items'] if (x.status == BulkDiscovery.START_STATE or x.status == BulkDiscovery.FINISH_STATE or
                                                   x.status == BulkDiscovery.CANCEL_STATE)) == sum(1 for x in ret['items'])

        ret = wait(lambda: rest.get(BulkDiscovery.URI),
                   condition=all_done,
                   progress_cb=lambda ret: 'Status: {0}'.format(list(x.status for x in ret['items'])),
                   *args, **kwargs)

        return ret

    @staticmethod
    def start_wait(rest, link, *args, **kwargs):

        def all_done(ret):
            return len(ret['items']) == 2

        ret = wait(lambda: rest.get(link),
                   condition=all_done,
                   progress_cb=lambda ret: len(ret['items']),
                   *args, **kwargs)
        return ret


class RadiusProvider(AttrDict):
    URI = '/mgmt/cm/system/authn/providers/radius'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(RadiusProvider, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('host', '')
        self.setdefault('port', 1812)
        self.setdefault('secret', '')


class RadiusProviderLogin(AttrDict):
    URI = '%s/login' % RadiusProvider.ITEM_URI

    def __init__(self, *args, **kwargs):
        super(RadiusProviderLogin, self).__init__(*args, **kwargs)
        self.setdefault('username', '')
        self.setdefault('password', '')


class RadiusProviderUserGroups(AttrDict):
    URI = '%s/user-groups' % RadiusProvider.ITEM_URI

    def __init__(self, *args, **kwargs):
        super(RadiusProviderUserGroups, self).__init__(*args, **kwargs)
        self.setdefault('propertyMap', AttrDict())
        self.setdefault('name', '')


class LdapProvider(AttrDict):
    URI = '/mgmt/cm/system/authn/providers/ldap'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(LdapProvider, self).__init__(*args, **kwargs)
        self.setdefault('name', '')
        self.setdefault('host', '')
        self.setdefault('port', 389)
        self.setdefault('rootDn', '')
        self.setdefault('authMethod', 'none')


class LdapProviderUserGroups(AttrDict):
    URI = '%s/user-groups' % LdapProvider.ITEM_URI

    def __init__(self, *args, **kwargs):
        super(LdapProviderUserGroups, self).__init__(*args, **kwargs)
        self.setdefault('groupDn', '')
        self.setdefault('name', '')


class LdapProviderLogin(AttrDict):
    URI = '%s/login' % LdapProvider.ITEM_URI

    def __init__(self, *args, **kwargs):
        super(LdapProviderLogin, self).__init__(*args, **kwargs)
        self.setdefault('username', '')
        self.setdefault('password', '')


class LocalProvider(AttrDict):
    URI = '/mgmt/cm/system/authn/providers/local'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(LocalProvider, self).__init__(*args, **kwargs)
        self.setdefault('name', '')


class LocalProviderGroups(AttrDict):
    URI = '/mgmt/cm/system/authn/providers/local/groups'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(LocalProviderGroups, self).__init__(*args, **kwargs)
        self.setdefault('name', '')


class AuthnLogin(AttrDict):
    URI = '/mgmt/shared/authn/login'

    def __init__(self, *args, **kwargs):
        super(AuthnLogin, self).__init__(*args, **kwargs)
        self.setdefault('username', '')
        self.setdefault('password', '')
        self.setdefault('loginReference', Reference())


class AuthnExchange(AttrDict):
    """
    Exchange Authentication token by using the refresh feature
    """
    URI = '/mgmt/shared/authn/exchange'

    def __init__(self, *args, **kwargs):
        super(AuthnExchange, self).__init__(*args, **kwargs)
        self.setdefault('generation', 0)
        self.setdefault('lastUpdateMicros', 0)
        self.setdefault('refreshToken', AttrDict(timeout=0,
                                                 exp=0,
                                                 iat=0,
                                                 generation=0,
                                                 lastUpdateMicros=0,
                                                 token=''))  # add token here


class ServiceCluster(BaseApiObject):
    URI = '/mgmt/cm/system/dma'
    RMA_URI = '/mgmt/cm/system/rma'
    NET_VLAN = '/mgmt/cm/current/cloud/net/vlan'
    DEVGRP_URI = '/mgmt/cm/current/cloud/cm/device-group'
    FINISH_STATE = 'FINISHED'
    FAILED_STATE = 'FAILED'

    def __init__(self, *args, **kwargs):
        super(ServiceCluster, self).__init__(*args, **kwargs)
        self.setdefault('devicesReference', Reference())

    @staticmethod
    def dma_wait(rest, link, timeout=90):

        def all_done(ret):
            return ret.status in ServiceCluster.FINISH_STATE

        ret = wait(lambda: rest.get(link), timeout=timeout, interval=1,
                   condition=all_done, progress_cb=lambda x: 'Status: {0} '.format(x.status))
        return ret

    @staticmethod
    def wait(rest, group_name, timeout=120):

        def all_done(ret):
            return group_name in list(x.name for x in ret['items'])

        ret = wait(lambda: rest.get(ServiceCluster.DEVGRP_URI), timeout=timeout, interval=1,
                   condition=all_done, progress_cb=lambda ret: 'Status: {0}'.format(list(x.name for x in ret['items'])))
        return ret

    @staticmethod
    def wait_twice(rest, group_name, timeout=120):

        def all_done(ret):
            num = sum(1 for x in ret['items'] if x.name == group_name)
            return num == 2 or num == 3

        ret = wait(lambda: rest.get(ServiceCluster.DEVGRP_URI), timeout=timeout, interval=1,
                   condition=all_done, progress_cb=lambda ret: 'Status: {0}'.format(list(x.name for x in ret['items'])))
        return ret

    @staticmethod
    def wait_thrice(rest, group_name, timeout=120):

        def all_done(ret):
            num = sum(1 for x in ret['items'] if x.name == group_name)
            return num == 3

        ret = wait(lambda: rest.get(ServiceCluster.DEVGRP_URI), timeout=timeout, interval=1,
                   condition=all_done, progress_cb=lambda ret: 'Status: {0}'.format(list(x.name for x in ret['items'])))
        return ret


class PruneBackupTask(Task):
    URI = '/mgmt/cm/system/prune-backups'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(PruneBackupTask, self).__init__(*args, **kwargs)
        self.setdefault('scheduleReference', Reference())


class ArchiveBackupTask(Task):
    URI = '/mgmt/cm/system/archive-backups'
    ITEM_URI = '%s/%%s' % URI
    TYPE = enum('SCP', 'LOCAL')

    def __init__(self, *args, **kwargs):
        super(ArchiveBackupTask, self).__init__(*args, **kwargs)
        self.setdefault('scheduleReference', Reference())
        self.setdefault('archivingLocation', '')
        self.setdefault('archiveType', ArchiveBackupTask.TYPE.SCP)


class SimpleEncrypter(AttrDict):
    URI = '/mgmt/cm/system/simple-encrypter'

    def __init__(self, *args, **kwargs):
        super(SimpleEncrypter, self).__init__(*args, **kwargs)
        self.setdefault('inputText', '')


class MachineIdResolver(AttrDict):
    URI = '/mgmt/cm/system/machineid-resolver'
    ITEM_URI = '%s/%%s' % URI
    ITEM_URI_F = "/mgmt/cm/system/machineid-resolver?$filter=uuid%20eq%20'{0}'"  # generating full with items[]
    STATS_ITEM_URI = '%s/%%s/stats' % URI
    # with filters
    BIGIQS_ITEMS_URI_F = "/mgmt/cm/system/machineid-resolver?$filter=product%20eq%20'BIG-IQ'"
    BIGIPS_ITEMS_URI_F = "/mgmt/cm/system/machineid-resolver?$filter=product%20eq%20'BIG-IP'"

    def __init__(self, *args, **kwargs):
        super(MachineIdResolver, self).__init__(*args, **kwargs)


class VolumeLicense(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/pool/volume/licenses'
    ITEM_URI = '/mgmt/cm/system/licensing/pool/volume/licenses/%s'

    AUTOMATIC_ACTIVATION_STATES = enum('ACTIVATING_AUTOMATIC', 'ACTIVATING_AUTOMATIC_EULA_ACCEPTED')

    MANUAL_ACTIVATION_STATES = enum('ACTIVATING_MANUAL', 'ACTIVATING_MANUAL_LICENSE_TEXT_PROVIDED',
                                    'ACTIVATING_MANUAL_OFFERINGS_LICENSE_TEXT_PROVIDED')

    WAITING_STATES = ['ACTIVATING_AUTOMATIC_NEED_EULA_ACCEPT', 'ACTIVATING_AUTOMATIC_OFFERINGS',
                      'ACTIVATING_MANUAL_NEED_LICENSE_TEXT', 'ACTIVATING_MANUAL_OFFERINGS_NEED_LICENSE_TEXT']

    FAILED_STATES = ['ACTIVATION_FAILED_OFFERING', 'ACTIVATION_FAILED']

    SUCCESS_STATE = ['READY']

    def __init__(self, *args, **kwargs):
        super(VolumeLicense, self).__init__(*args, **kwargs)
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


class VolumeLicenseOfferingsCollection(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/pool/volume/licenses/%s/offerings'
    ITEM_URI = '/mgmt/cm/system/licensing/pool/volume/licenses/%s/offerings/%s'

    def __init__(self, *args, **kwargs):
        super(VolumeLicenseOfferingsCollection, self).__init__(*args, **kwargs)
        self.setdefault('status', '')
        self.setdefault('licenseText', '')


class VolumeLicenseMembersCollection(BaseApiObject):
    URI = '/mgmt/cm/system/licensing/pool/volume/licenses/%s/offerings/%s/members'
    ITEM_URI = '/mgmt/cm/system/licensing/pool/volume/licenses/%s/offerings/%s/members/%s'

    WAITING_STATE = 'INSTALLING'
    FAILED_STATE = 'INSTALLATION_FAILED'
    SUCCESS_STATE = 'LICENSED'

    def __init__(self, *args, **kwargs):
        super(VolumeLicenseMembersCollection, self).__init__(*args, **kwargs)
        self.setdefault('deviceMachineId', '')

    @staticmethod
    def wait(rest, uri, wait_for_status, timeout=30, interval=1):

        resp = wait(lambda: rest.get(uri), condition=lambda temp: temp.status == wait_for_status,
                    progress_cb=lambda temp: 'Status: {0}, Message: {1}' .format(temp.status, temp.message), timeout=timeout, interval=interval)

        return resp


class RootCredentialChange(BaseApiObject):
    URI = '/mgmt/shared/authn/root'

    def __init__(self, *args, **kwargs):
        super(RootCredentialChange, self).__init__(*args, **kwargs)
        self.setdefault('oldPassword', '')
        self.setdefault('newPassword', '')


class FileTransfer(BaseApiObject):
    URI = '/mgmt/shared/file-transfer/uploads/%s'
    DEFAULT_DEVICES_CSV = 'file'

    def __init__(self, *args, **kwargs):
        super(FileTransfer, self).__init__(*args, **kwargs)

    @staticmethod
    def upload(rest, content, file_name=DEFAULT_DEVICES_CSV):
        CHUNKS = 256 * 1024  # 256KB chunks

        def chunks(l, m):
            for i in range(0, len(l), m):
                yield l[i:i + m]

        offset = 0
        content_length = len(content)
        headers = dict()
        headers['Content-Type'] = "application/octet-stream"
        for chunk in chunks(content, CHUNKS):
            chunk_length = len(chunk)
            headers['Content-range'] = "%s-%s/%s" % (offset,
                                                     chunk_length + offset - 1,
                                                     content_length)
            headers['Content-Length'] = chunk_length
            offset += chunk_length
            resp = rest.post(FileTransfer.URI % file_name, payload=chunk,
                             headers=headers)

        return resp


class FileObjectTask(BaseApiObject):
    URI = '/mgmt/cm/system/file-object-tasks'
    ITEM_URI = '%s/%%s' % URI
    TYPE = enum('REMOTE_SOURCE_FILE', 'LOCAL_SOURCE_FILE')

    def __init__(self, *args, **kwargs):
        super(FileObjectTask, self).__init__(*args, **kwargs)
        self.setdefault('requestType', FileObjectTask.TYPE.LOCAL_SOURCE_FILE)
        self.setdefault('fileType', '')


class FileObject(BaseApiObject):
    URI = '/mgmt/cm/system/file-objects'
    ITEM_URI = '%s/%%s' % URI

    def __init__(self, *args, **kwargs):
        super(FileObject, self).__init__(*args, **kwargs)


class SSHTrust(BaseApiObject):
    URI = '/mgmt/shared/ssh-trust-setup'

    def __init__(self, *args, **kwargs):
        super(SSHTrust, self).__init__(*args, **kwargs)

        self.setdefault('fingerprint', '')
        self.setdefault('rootPassword', '')
        self.setdefault('ipAddress', '')


class ManagedDeviceAvailability(BaseApiObject):
    URI = '/mgmt/shared/system/managed-device-availability'

    def __init__(self, *args, **kwargs):
        super(ManagedDeviceAvailability, self).__init__(*args, **kwargs)
