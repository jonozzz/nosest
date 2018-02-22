'''
Created on Mar 23, 2016

@author: jono
'''
from .scaffolding import Stamp, PropertiesStamp
from .profile import BaseProfile
import logging
# from ...base import enum
# from ...utils.parsers import tmsh
# from ...utils.parsers.tmsh import RawEOL

LOG = logging.getLogger(__name__)


class SipPeer(PropertiesStamp):
    TMSH = r"""
    ltm message-routing sip peer %(key)s {
        #app-service none
        connection-mode per-peer
        #description none
        number-connections 1
        #partition Common
        pool none
        ratio 1
        transport-config none
    }
    """


class SipRoute(PropertiesStamp):
    TMSH = r"""
    ltm message-routing sip route %(key)s {
        peers {
            /partition01/mr_peer1
        }
        # virtual-server /Common/foo
    }
    """


class SipTransportConfig(PropertiesStamp):
    TMSH = r"""
    ltm message-routing sip transport-config %(key)s {
        #app-service none
        description none
        ip-protocol tcp
        #partition Common
        profiles {
            diametersession { }
            tcp { }
        }
        rules none
        source-address-translation {
            pool none
            type automap
        }
        source-port 0
    }
    """


class SipProfileRouter(PropertiesStamp, BaseProfile):
    built_in = False

    TMSH = r"""
        ltm message-routing sip profile router %(key)s {
            # app-service none
            # defaults-from none
            # description none
            max-pending-bytes 23768
            max-pending-messages 64
            operation-mode load-balancing
            # partition Common
            routes none
            session {
                transaction-timeout 10
            }
            use-local-connection enabled
        }
    """


class SipProfileSession(PropertiesStamp, BaseProfile):
    built_in = False

    TMSH = r"""
    ltm message-routing sip profile session %(key)s {
        # app-service none
        generate-response-on-failure enabled
        insert-record-route-header enabled
        loop-detection enabled
        max-forwards-check enabled
    }
    """
