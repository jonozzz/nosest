'''
Created on May 31, 2016

@author: aphan
'''
from .scaffolding import PropertiesStamp


class TrafficGroup(PropertiesStamp):
    TMSH = """
        cm traffic-group %(key)s {
            app-service none
            auto-failback-enabled false
            auto-failback-time 60
            default-device none
            description none
            ha-group none
            ha-load-factor 1
            ha-order none
            is-floating true
            mac %(address)
            partition Common
            unit-id 1
        }
    """
