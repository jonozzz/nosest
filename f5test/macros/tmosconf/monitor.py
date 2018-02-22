'''
Created on June 12, 2016

@author: aphan
'''
from .scaffolding import PropertiesStamp


class Monitor(PropertiesStamp):
    built_in = True
    context = None

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        if v.product.is_bigip:
            return self.get_full_path(), obj


