'''
Created on June 12, 2016

@author: aphan
'''
from .scaffolding import PropertiesStamp


class SnatTranslation(PropertiesStamp):
    TMSH = """
    ltm snat-translation %(key)s {
        address None
        inherited-traffic-group true
        traffic-group traffic-group-1
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        if v.product.is_bigip:
            return self.get_full_path(), obj
