'''
Created on Jun 20, 2013

@author: aphan
'''
from .scaffolding import PropertiesStamp
import logging


LOG = logging.getLogger(__name__)


class BaseLogConfig(object):
    context = None

    def tmsh(self, obj):
        key = self.get_full_path()
        value = obj.format(key=key)
        return key, value

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        if self.context:
            return {key: {'context': self.context}}
        else:
            # return super(Profile, self).reference()
            return {key: {}}


class LogConfigDestinationRemoteHighspeed(BaseLogConfig, PropertiesStamp):
    TMSH = r"""
    sys log-config destination remote-high-speed-log %(key)s {
        app-service none
        description none
        distribution adaptive
        pool-name rhsl_pool
        protocol tcp
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 12.0':  # failed on 11.5.5, 11.6.3
                values.pop('distribution')
            return self.get_full_path(), obj


class LogConfigPublisher(BaseLogConfig, PropertiesStamp):
    TMSH = r"""
    sys log-config publisher %(key)s {
        app-service none
        description none
        destinations {
        }
    }
    """
