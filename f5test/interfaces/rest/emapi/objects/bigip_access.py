'''
Created on May 21, 2015

@author: ivanitskiy
'''

from f5test.interfaces.rest.base import BaseApiObject
from f5test.base import AttrDict
from datetime import datetime
import md5


def generate_hash():
    """Generates md55 hash of current time and return first 7 symbols
    """
    return md5.new(str(datetime.now())).hexdigest()[:7]


class ApmAaaLdap(BaseApiObject):
    URI = "/mgmt/tm/apm/aaa/ldap"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmAaaLdap, self).__init__(*args, **kwargs)
        self.setdefault('name', "ldap_%s" % generate_hash())
        self.setdefault('address', "1.1.1.1")
        self.setdefault('cleanupCache', "none")
        self.setdefault('adminDn', "admin")
        self.setdefault('adminEncryptedPassword', "admin")
        self.setdefault('groupCacheTtl', 30)
        self.setdefault('isLdaps', False)
        self.setdefault('locationSpecific', True)
        self.setdefault('port', 389)
        self.setdefault('timeout', 15)
        self.setdefault('usePool', "disabled")
        self.setdefault("schemaAttr", AttrDict())
        self.schemaAttr.groupMember = "member"
        self.schemaAttr.groupMemberValue = "dn"
        self.schemaAttr.groupMemberof = "memberOf"
        self.schemaAttr.groupObjectClass = "group"
        self.schemaAttr.userMemberof = "memberOf"
        self.schemaAttr.userObjectClass = "user"


class ApmAaaRadius(BaseApiObject):
    URI = "/mgmt/tm/apm/aaa/radius"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmAaaRadius, self).__init__(*args, **kwargs)
        self.setdefault('name', "radius_%s" % generate_hash())
        self.setdefault('generation', 687)
        self.setdefault('acctPort', 1813)
        self.setdefault('address', '1.1.1.1')
        self.setdefault('authPort', 1812)
        self.setdefault('locationSpecific', 'true')
        self.setdefault('mode', 'auth')
        self.setdefault('nasIpAddress', 'any6')
        self.setdefault('nasIpv6Address', 'any6')
        self.setdefault('radiusCharset', 'cp1252')
        self.setdefault('retries', 3)
        self.setdefault('secret', 'secret')
        self.setdefault('serviceType', 'default')
        self.setdefault('timeout', 5)
        self.setdefault('usePool', 'disabled')


class KeytabFileReference(BaseApiObject):
    URI = "/mgmt/tm/apm/aaa/kerberos-keytab-file"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(KeytabFileReference, self).__init__(*args, **kwargs)
        name = "%s_key_file" % generate_hash()
        self.setdefault('name', name)
        self.setdefault('partition', 'Common')
        self.setdefault('source-path', None)


class ApmAaaKerberos(BaseApiObject):
    URI = "/mgmt/tm/apm/aaa/kerberos"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmAaaKerberos, self).__init__(*args, **kwargs)
        name = "kerberos_%s" % generate_hash()
        self.setdefault('name', name)
        self.setdefault('generation', 693)
        self.setdefault('authRealm', "user@TEST.LAB")
        self.setdefault('keytabFileObj', None)
        self.setdefault('keytabFileObjReference', AttrDict())
        self.setdefault('locationSpecific', 'true')
        self.setdefault('serviceName', 'HTTP/test.lab')


class ApmAaaActiveDirectory(BaseApiObject):
    URI = "/mgmt/tm/apm/aaa/active-directory"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmAaaActiveDirectory, self).__init__(*args, **kwargs)
        self.setdefault('name', "ad_%s" % generate_hash())
        self.setdefault('adminEncryptedPassword', "password")
        self.setdefault('adminName', "admin")
        self.setdefault('cleanupCache', None)
        self.setdefault('domain', "domain.local")
        self.setdefault('domainController', "dc.domain.local")
        self.setdefault('groupCacheTtl', 30)
        self.setdefault('kdcLockoutDuration', 0)
        self.setdefault('locationSpecific', True)
        self.setdefault('psoCacheTtl', 30)
        self.setdefault('timeout', 15)
        self.setdefault('usePool', "disabled")


class ApmACL(BaseApiObject):
    URI = "/mgmt/tm/apm/acl"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmACL, self).__init__(*args, **kwargs)
        self.setdefault('name', "acl_%s" % generate_hash())
        self.setdefault('aclOrder', 0)
        self.setdefault('locationSpecific', True)
        self.setdefault('pathMatchCase', True)
        self.setdefault('type', 'static')


class ApmResourceNetworkAccess(BaseApiObject):
    URI = "/mgmt/tm/apm/resource/network-access"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmResourceNetworkAccess, self).__init__(*args, **kwargs)
        self.setdefault('name', "na_%s" % generate_hash())


class ApmResourcePortalAccess(BaseApiObject):
    URI = "/mgmt/tm/apm/resource/portal-access"
    URI_ITEM = URI + "/%s"
    URI_ITEMS = URI + "/%s/items"

    def __init__(self, *args, **kwargs):
        super(ApmResourcePortalAccess, self).__init__(*args, **kwargs)
        self.setdefault('name', "pa_%s" % generate_hash())


class ApmResourceRDP(BaseApiObject):
    URI = "/mgmt/tm/apm/resource/remote-desktop/rdp"
    URI_ITEM = URI + "/%s"

    def __init__(self, *args, **kwargs):
        super(ApmResourceRDP, self).__init__(*args, **kwargs)
        self.setdefault('name', "rdp_%s" % generate_hash())
        self.setdefault('ip', '10.10.10.10')


class ApmResourceLeasepool(BaseApiObject):
    URI = "/mgmt/tm/apm/resource/leasepool"

    def __init__(self, *args, **kwargs):
        super(ApmResourceLeasepool, self).__init__(*args, **kwargs)
        self.setdefault('name', "ipv4-leasepool_%s" % generate_hash())
        self.setdefault('members', [])
        self.members.append({"name": "1.1.1.1-1.1.1.10"})


class ApmResourceIpv6Leasepool(BaseApiObject):
    URI = "/mgmt/tm/apm/resource/ipv6-leasepool"

    def __init__(self, *args, **kwargs):
        super(ApmResourceIpv6Leasepool, self).__init__(*args, **kwargs)
        self.setdefault('name', "ipv6-leasepool_%s" % generate_hash())
        self.setdefault('members', [])
        self.members.append({"name": "2001:db8:85a3::8a2e:370:7334-2001:db8:85a3::8a2e:370:7336"})
