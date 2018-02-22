'''
Created on May 22, 2014
@author: mathur

'''
from .base import DEFAULT_TIMEOUT, Reference, ReferenceList
from ...base import BaseApiObject
from .....utils.wait import wait
from f5test.interfaces.rest.emapi.resources import EmapiResourceError

DEFAULT_PARTITION = 'Common'


class SyncStatus(BaseApiObject):
    URI = '/mgmt/tm/cm/sync-status'
    SYNC_STATE = 'In Sync'
    STANDALONE_STATE = 'Standalone'

    def __init__(self, *args, **kwargs):
        super(SyncStatus, self).__init__(*args, **kwargs)

    @staticmethod
    def wait(rest, timeout=DEFAULT_TIMEOUT):

        def all_done(ret):
            return ret['entries']['https://localhost/mgmt/tm/cm/sync-status/0']['nestedStats']['entries']['status']['description'] == SyncStatus.STANDALONE_STATE

        ret = wait(lambda: rest.get(SyncStatus.URI), timeout=timeout, interval=1, condition=all_done,
                   progress_cb=lambda ret: 'Status: {0}'.format((ret['entries']['https://localhost/mgmt/tm/cm/sync-status/0']['nestedStats']['entries']['status']['description'])))

        return ret

    @staticmethod
    def wait_sync(rest, timeout=DEFAULT_TIMEOUT):

        def all_done(ret):
            return ret['entries']['https://localhost/mgmt/tm/cm/sync-status/0']['nestedStats']['entries']['status']['description'] == SyncStatus.SYNC_STATE

        ret = wait(lambda: rest.get(SyncStatus.URI), timeout=timeout, interval=1, condition=all_done,
                   progress_cb=lambda ret: 'Status: {0}'.format((ret['entries']['https://localhost/mgmt/tm/cm/sync-status/0']['nestedStats']['entries']['status']['description'])))

        return ret


class Device(BaseApiObject):
    URI = '/mgmt/tm/cm/device'
    ITEM_URI = '/mgmt/tm/cm/device/%s'
    VALID_STATES = ['active', 'standby']

    def __init__(self, *args, **kwargs):
        super(Device, self).__init__(*args, **kwargs)

    @staticmethod
    def wait(rest, timeout=DEFAULT_TIMEOUT):

        def all_done(ret):
            states = [x.failoverState for x in ret['items']
                      if x.failoverState in Device.VALID_STATES]
            return len(states) == len(ret['items'])

        ret = wait(lambda: rest.get(Device.URI), timeout=timeout, interval=1,
                   condition=all_done,
                   progress_cb=lambda ret: 'States: {0}'.format([x.failoverState
                                                                 for x in ret['items']]))

        return ret


class Sys(BaseApiObject):
    URI = '/mgmt/tm/sys'
    AVAILABLE_URI = URI + '/available'
    DNS_URI = URI + '/dns'
    NTP_URI = URI + '/ntp'

    def __init__(self, *args, **kwargs):
        super(Sys, self).__init__(*args, **kwargs)


class SysProvision(BaseApiObject):
    URI = '/mgmt/tm/sys/provision'

    def __init__(self, *args, **kwargs):
        super(SysProvision, self).__init__(*args, **kwargs)


class iAppTemplate(BaseApiObject):
    URI = '/mgmt/shared/iapp/blocks'

    def __init__(self, *args, **kwargs):
        super(iAppTemplate, self).__init__(*args, **kwargs)
        self.setdefault('state', 'TEMPLATE')
        self.setdefault('name', 'Default Template Name')
        self.setdefault('audit', dict(intervalSeconds=0, policy='NOTIFY_ONLY'))
        self.setdefault('configurationProcessorReference', Reference())
        self.setdefault('statsProcessorReferences', ReferenceList())
        self.setdefault('inputProperties', list())


class FailoverState(BaseApiObject):
    URI = '/mgmt/tm/shared/bigip-failover-state'
    BIG_IP_SYNC_FAILOVER = "/mgmt/tm/sys/failover/"
    BIGP_FAILOVER_STATUS_URI = "/mgmt/tm/cm/failover-status"

    def __init__(self, *args, **kwargs):
        super(FailoverState, self).__init__(*args, **kwargs)

    def get_failover_state(self, ifc):
        bigip_api = ifc.api
        fos = bigip_api.get(FailoverState.BIGP_FAILOVER_STATUS_URI)
        for key in fos.entries.keys():
            entries = fos.entries[key]
            return entries.nestedStats.entries.status.description
        return None


class DeviceGroup(BaseApiObject):
    URI = '/mgmt/tm/cm/device-group'

    def __init__(self, *args, **kwargs):
        super(DeviceGroup, self).__init__(*args, **kwargs)


class VirtualServer(BaseApiObject):
    URI = '/mgmt/tm/ltm/virtual'
    ITEM_URI = URI + '/~' + DEFAULT_PARTITION + '~%s'

    # Incomplete set of defaults, but good enough for our tests at the moment.
    ATTRIBUTE_DEFAULTS = {'description': 'default description',
                          'ipProtocol': 'tcp',
                          'profiles': [{'name': 'tcp'}],
                          'persist': [{'name': 'source_addr'}],
                          'sourceAddressTranslation': {'type': 'automap'}
                          }

    def set_all_defaults(self):
        self.update(self.ATTRIBUTE_DEFAULTS)
        return self


class Pool(BaseApiObject):
    URI = '/mgmt/tm/ltm/pool'
    ITEM_URI = URI + '/~' + DEFAULT_PARTITION + '~%s'


class Node(BaseApiObject):
    URI = '/mgmt/tm/ltm/node'
    ITEM_URI = URI + '/~' + DEFAULT_PARTITION + '~%s'


class Rule(BaseApiObject):
    URI = '/mgmt/tm/ltm/rule'
    ITEM_URI = URI + '/~' + DEFAULT_PARTITION + '~%s'


class Route(BaseApiObject):
    URI = '/mgmt/tm/net/route'

    def __init__(self, *args, **kwargs):
        super(Route, self).__init__(*args, **kwargs)


class Version(BaseApiObject):
    SYS_VERSION_URI = "/mgmt/tm/sys/version"

    def __init__(self, *args, **kwargs):
        super(Version, self).__init__(*args, **kwargs)


class IApp(BaseApiObject):
    URI = '/mgmt/tm/cloud/services/iapp'
    ITEM_URI = URI + "/%s"
    ITEM_STATS_URI = ITEM_URI + "/stats"

    def __init__(self, *args, **kwargs):
        super(IApp, self).__init__(*args, **kwargs)


class Auth(BaseApiObject):
    BIGIP_ADMIN_URI = "/mgmt/tm/auth/user/admin"

    def __init__(self, *args, **kwargs):
        super(Auth, self).__init__(*args, **kwargs)


class AuthAdmin(BaseApiObject):
    URI = "/mgmt/tm/auth/user/admin"
    AVAILABLE_URI = "/mgmt/tm/auth/user/admin/available"

    def __init__(self, *args, **kwargs):
        super(Auth, self).__init__(*args, **kwargs)


class AuthzRoles(BaseApiObject):
    URI = "/mgmt/shared/authz/roles"
    AVAILABLE_URI = "/mgmt/shared/authz/roles/available"

    def __init__(self, *args, **kwargs):
        super(AuthzRoles, self).__init__(*args, **kwargs)


class AuthnLogin(BaseApiObject):
    URI = "/mgmt/shared/authn/login"

    def __init__(self, *args, **kwargs):
        super(AuthnLogin, self).__init__(*args, **kwargs)


class Certificates2(BaseApiObject):
    URI = '/mgmt/tm/cloud/sys/certificate-file-object'

    def __init__(self, *args, **kwargs):
        super(Certificates2, self).__init__(*args, **kwargs)


class Tmui(BaseApiObject):
    LOGIN_URI = '/tmui/login.jsp'

    def __init__(self, *args, **kwargs):
        super(Tmui, self).__init__(*args, **kwargs)


class Vlan(BaseApiObject):
    URI = '/mgmt/tm/net/vlan'

    def __init__(self, *args, **kwargs):
        super(Vlan, self).__init__(*args, **kwargs)


class MgmtIp(BaseApiObject):
    URI = '/mgmt/tm/sys/management-ip'

    def __init__(self, *args, **kwargs):
        super(MgmtIp, self).__init__(*args, **kwargs)


class SelfIp(BaseApiObject):
    URI = '/mgmt/tm/net/self'
    ITEM_URI = URI + '/~' + DEFAULT_PARTITION + '~%s'

    def __init__(self, *args, **kwargs):
        super(SelfIp, self).__init__(*args, **kwargs)


class Folders(BaseApiObject):
    URI = '/mgmt/tm/sys/folder'

    def __init__(self, *args, **kwargs):
        super(Folders, self).__init__(*args, **kwargs)
