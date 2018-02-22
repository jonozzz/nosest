'''
Created on May 24, 2016

@author: jono
'''

from f5test.macros.tmosconf.scaffolding import PropertiesStamp
from f5test.macros.tmosconf.profile import BaseProfile


class ProfileSpm(PropertiesStamp, BaseProfile):

    built_in = False

    TMSH = """
    pem profile spm %(key)s  {
        app-service none
    }
    """

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        if self.context:
            return {key: {'context': self.context}}
        else:
            return {key: {}}
