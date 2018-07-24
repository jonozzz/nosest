'''
Created on Apr 15, 2013

@author: jono
'''
from .scaffolding import Stamp, PropertiesStamp
import crypt  # @UnresolvedImport
# import itertools
# import netaddr
from ...utils.parsers import tmsh


class User(Stamp):
    TMSH = """
        auth user %(name)s {
           description "created by confgen"
           shell none
           #role admin
           #partition-access all

           #partition-access {
           #  all-partitions {
           #    role admin
           # }
          }
        }
    """
    BIGPIPE = """
        user %(name)s {
           description "a"
           shell "/bin/false"
#           role administrator in all
        }
    """
    bp_role_map = {'admin': 'administrator',
                   'application-editor': 'app editor',
                   'no-access': 'none',
                   'web-application-security-editor': 'policy editor',
                   'resource-admin': 'resource admin',
                   'user-manager': 'user manager'}

    def __init__(self, name, password=None, role='admin'):
        self.name = name
        self.password = password or name
        self.role = role
        self.salt = '$1$fakesalt$'
        super(User, self).__init__()

    def tmsh(self, obj):
        ctx = self.folder.context
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        value = obj.rename_key('auth user %(name)s', name=self.name)
        value['encrypted-password'] = crypt.crypt(self.password, self.salt)
        # CAUTION: BIG-IQ OR (Orchestration) is shipped under the same product
        # string "BIG-IQ" although the version is different starting from 1.0
        # In the event that BIG-IQ OR decides to keep this product name and the
        # version will reach 4.0 we'll hit a version ambiguity.
        #
        # S. Fisher 10/12/2015 We're not changing product name.
        # So hardcoding the check to support 1.0 or anything higher is preferred.
        # We'll be at 1.1 or 2.0 in next release - around February or so
        if ctx.version >= 'bigip 11.6' or ctx.version >= 'bigiq 5.0' or \
                ctx.version < 'bigiq 4.0' or ctx.version >= 'iworkflow 2.0':
            value['partition-access'] = {'all-partitions': {'role': self.role}}
        else:
            value['role'] = self.role
            value['partition-access'] = 'all'

        value['description'] = "User %s %s" % (self.name, self.password)  # / is not longer a valid character (rest framework >= bp 12.1; bq>= 5.0)

        return key, obj

    def bigpipe(self, obj):
        # ctx = self.folder.context
        key = self.name
        value = obj.rename_key('user %(name)s', name=self.name)
        value['password crypt'] = crypt.crypt(self.password, self.salt)
        value['role'] = tmsh.RawString(' '.join([User.bp_role_map.get(self.role, self.role), 'in all']))
        value['description'] = "User %s %s" % (self.name, self.password)  # / is not longer a valid character (rest framework >= bp 12.1; bq>= 5.0)
        return key, obj


class PasswordPolicy(PropertiesStamp):
    TMSH = """
    auth password-policy {
        policy-enforcement disabled
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = list(obj.values())[0]
        if v.product.is_bigip:
            return self.get_full_path(), obj
