'''
Created on Apr 12, 2013

@author: jono
'''
from .scaffolding import Stamp, PropertiesStamp
from ...utils.dicts import flatten


def references(*dict_args):
    def modifier(k, d):
        d[k] = {}
        d[k].update(flatten(*[x.reference() for x in dict_args]))
    return modifier


def combine(*dict_args):
    def modifier(k, d):
        d[k] = {}
        d[k].update(flatten(*[x.compile()[1] for x in dict_args]))
    return modifier


class BaseProfile(object):
    built_in = True
    context = None

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        name = self.__class__.__name__
        return "<{0}: {1.name}>".format(name, self)

    def get_vs_profile(self, name=None):
        name = name or self.name
        v = self.folder.context.version
        if v.product.is_bigip and v >= 'bigip 11.0.0':
            key = self.folder.SEPARATOR.join((self.folder.key(), name))
            if self.context:
                return {key: {'context': self.context}}
            else:
                return {key: ''}
        else:
            return self.name


class Profile(BaseProfile, Stamp):

    def reference(self):
        key = self.folder.SEPARATOR.join((self.folder.key(), self.name))
        if self.context:
            return {key: {'context': self.context}}
        else:
            #return super(Profile, self).reference()
            return {key: {}}


class ServerSsl(PropertiesStamp, BaseProfile):
    context = 'serverside'
    TMSH = r"""
    ltm profile server-ssl %(key)s {
        alert-timeout indefinite
        allow-expired-crl disabled
        app-service none
        authenticate once
        authenticate-depth 9
        authenticate-name none
        ca-file none
        cache-size 262144
        cache-timeout 3600
        cert none
        chain none
        ciphers DEFAULT
        crl-file none
        defaults-from none
        description none
        expire-cert-response-control drop
        generic-alert enabled
        handshake-timeout 10
        key none
        mod-ssl-methods disabled
        mode enabled
        options { dont-insert-empty-fragments }
        partition Common
        passphrase none
        peer-cert-mode ignore
        proxy-ssl disabled
        proxy-ssl-passthrough disabled
        renegotiate-period indefinite
        renegotiate-size indefinite
        renegotiation enabled
        retain-certificate true
        secure-renegotiation require-strict
        server-name none
        session-mirroring disabled
        session-ticket disabled
        sni-default false
        sni-require false
        ssl-forward-proxy disabled
        ssl-forward-proxy-bypass disabled
        ssl-sign-hash any
        strict-resume disabled
        unclean-shutdown enabled
        untrusted-cert-response-control drop
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 12.0':
                values.pop('allow-expired-crl')
                values.pop('proxy-ssl-passthrough')
                values.pop('session-mirroring')
            if v < 'bigip 11.5':  # failed on 11.4.1
                values.pop('generic-alert')
                values.pop('ssl-forward-proxy-bypass')
                values.pop('ssl-sign-hash')
            return self.get_full_path(), obj


class ClientSsl(PropertiesStamp, BaseProfile):
    context = 'clientside'
    TMSH = r"""
    ltm profile client-ssl %(key)s {
        alert-timeout indefinite
        allow-expired-crl disabled
        allow-non-ssl disabled
        app-service none
        authenticate once
        authenticate-depth 9
        ca-file none
        cache-size 262144
        cache-timeout 3600
        cert default.crt
        cert-extension-includes { basic-constraints subject-alternative-name }
        cert-key-chain {
            default {
                app-service none
                cert default.crt
                chain none
                key default.key
                ocsp-stapling-params none
                passphrase none
            }
        }
        cert-lifespan 30
        cert-lookup-by-ipaddr-port disabled
        chain none
        ciphers DEFAULT
        client-cert-ca none
        crl-file none
        defaults-from none
        description none
        destination-ip-blacklist none
        destination-ip-whitelist none
        forward-proxy-bypass-default-action intercept
        generic-alert enabled
        handshake-timeout 10
        hostname-blacklist none
        hostname-whitelist none
        inherit-certkeychain false
        key default.key
        max-aggregate-renegotiation-per-minute indefinite
        max-renegotiations-per-minute 5
        mod-ssl-methods disabled
        mode enabled
        options { dont-insert-empty-fragments }
        partition Common
        passphrase none
        peer-cert-mode ignore
        peer-no-renegotiate-timeout 10
        proxy-ca-cert none
        proxy-ca-key none
        proxy-ca-passphrase none
        proxy-ssl disabled
        proxy-ssl-passthrough disabled
        renegotiate-max-record-delay indefinite
        renegotiate-period indefinite
        renegotiate-size indefinite
        renegotiation enabled
        retain-certificate true
        secure-renegotiation require
        server-name none
        session-mirroring disabled
        session-ticket disabled
        session-ticket-timeout 0
        sni-default false
        sni-require false
        source-ip-blacklist none
        source-ip-whitelist none
        ssl-forward-proxy disabled
        ssl-forward-proxy-bypass disabled
        ssl-sign-hash any
        strict-resume disabled
        unclean-shutdown enabled
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 12.0':
                values.pop('allow-expired-crl')
                values.pop('proxy-ssl-passthrough')
                values.pop('session-mirroring')
                values['cert-key-chain']['default'].pop('ocsp-stapling-params')
                values.pop('max-aggregate-renegotiation-per-minute')
                values.pop('max-renegotiations-per-minute')
                values.pop('peer-no-renegotiate-timeout')
                values.pop('session-ticket-timeout')
            if v < 'bigip 11.5':  # failed on 11.4.1
                values.pop('generic-alert')
                values.pop('ssl-forward-proxy-bypass')
                values.pop('ssl-sign-hash')
                values.pop('cert-key-chain')
                values.pop('destination-ip-blacklist')
                values.pop('destination-ip-whitelist')
                values.pop('forward-proxy-bypass-default-action')
                values.pop('hostname-blacklist')
                values.pop('hostname-whitelist')
                values.pop('inherit-certkeychain')
                values.pop('source-ip-blacklist')
                values.pop('source-ip-whitelist')
            return self.get_full_path(), obj


class Sip(PropertiesStamp, BaseProfile):
    built_in = False

    TMSH = r"""
    ltm profile sip %(key)s {
        alg-enable disabled
        app-service none
        community none
        defaults-from /Common/sip
        description none
        dialog-aware disabled
        dialog-establishment-timeout 10
        enable-sip-firewall no
        insert-record-route-header disabled
        insert-via-header disabled
        log-profile none
        log-publisher none
        max-media-sessions 6
        max-registrations 100
        max-sessions-per-registration 50
        max-size 65535
        #partition Common
        registration-timeout 3600
        rtp-proxy-style symmetric
        secure-via-header disabled
        security disabled
        sip-session-timeout 300
        terminate-on-bye enabled
        user-via-header none
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.6':  # failed on 11.4.1, 11.5
                values.pop('log-profile')
                values.pop('log-publisher')
            return self.get_full_path(), obj


class FastL4(PropertiesStamp, BaseProfile):
    built_in = False

    TMSH = r"""
    ltm profile fastl4 %(key)s {
        app-service none
        client-timeout 30
        defaults-from none
        description none
        explicit-flow-migration disabled
        hardware-syn-cookie enabled
        idle-timeout 300
        ip-tos-to-client pass-through
        ip-tos-to-server pass-through
        keep-alive-interval disabled
        late-binding disabled
        link-qos-to-client pass-through
        link-qos-to-server pass-through
        loose-close disabled
        loose-initialization disabled
        mss-override 0
        partition Common
        priority-to-client pass-through
        priority-to-server pass-through
        pva-acceleration full
        pva-dynamic-client-packets 1
        pva-dynamic-server-packets 0
        pva-flow-aging enabled
        pva-flow-evict enabled
        pva-offload-dynamic enabled
        pva-offload-state embryonic
        reassemble-fragments disabled
        receive-window-size 0
        reset-on-timeout enabled
        rtt-from-client disabled
        rtt-from-server disabled
        server-sack disabled
        server-timestamp disabled
        software-syn-cookie disabled
        syn-cookie-whitelist disabled
        tcp-close-timeout 5
        tcp-generate-isn disabled
        tcp-handshake-timeout 5
        tcp-strip-sack disabled
        tcp-timestamp-mode preserve
        tcp-wscale-mode preserve
        timeout-recovery disconnect
    }
    """

    def tmsh(self, obj):
        ctx = self.folder.context
        v = ctx.version
        values = obj.values()[0]
        if v.product.is_bigip:
            if v < 'bigip 11.5':  # failed on 11.4.1
                values.pop('priority-to-client')
                values.pop('priority-to-server')
                values.pop('pva-dynamic-client-packets')
                values.pop('pva-dynamic-server-packets')
                values.pop('pva-offload-dynamic')
                values.pop('pva-offload-state')
                #values.pop('client-timeout')
                #values.pop('explicit-flow-migration')
                #values.pop('late-binding')
                #values.pop('syn-cookie-whitelist')
                #values.pop('timeout-recovery')
            if v < 'bigip 11.6':  # failed on 11.5
                values.pop('client-timeout')
                values.pop('explicit-flow-migration')
                values.pop('late-binding')
                values.pop('syn-cookie-whitelist')
                values.pop('timeout-recovery')
            return self.get_full_path(), obj
