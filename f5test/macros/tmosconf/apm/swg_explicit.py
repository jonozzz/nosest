'''
Created on Mar 22, 2016

@author: jono
'''
from ..scaffolding import Stamp


class SWGExplicit(Stamp):
    TMSH = r"""
apm policy access-policy %(key)s {
    default-ending %(key)s_end_deny
    items {
        %(key)s_act_HTTP_407_Response { }
        %(key)s_act_localdb_auth { }
        %(key)s_act_swg_policy_assign_1 { }
        %(key)s_end_allow { }
        %(key)s_end_deny { }
        %(key)s_ent { }
    }
    start-item %(key)s_ent
}

apm policy customization-group %(key)s_act_HTTP_407_Response_ag {
    revision 2
}
apm policy customization-group %(key)s_end_deny_ag {
    revision 1
    type logout
}
apm policy customization-group %(key)s_eps {
    revision 1
    type eps
}
apm policy customization-group %(key)s_errormap {
    revision 1
    type errormap
}
apm policy customization-group %(key)s_frameworkinstallation {
    revision 1
    type framework-installation
}
apm policy customization-group %(key)s_general_ui {
    revision 1
    type general-ui
}
apm policy customization-group %(key)s_logout {
    revision 1
    type logout
}

apm policy policy-item %(key)s_act_HTTP_407_Response {
    agents {
        %(key)s_act_HTTP_407_Response_ag {
            type logon-page
        }
    }
    caption "HTTP 407 Response"
    color 1
    item-type action
    rules {
        {
            caption Basic
            expression "expr {[mcget {session.logon.last.authtype}] == \"Basic\"} "
            next-item %(key)s_act_localdb_auth
        }
        {
            caption fallback
            next-item %(key)s_end_deny
        }
    }

}

apm policy policy-item %(key)s_act_localdb_auth {
    agents {
        %(key)s_act_localdb_auth_ag {
            type aaa-localdb
        }
    }
    caption "LocalDB Auth"
    color 1
    item-type action
    rules {
        {
            caption Successful
            expression "expr {[mcget {session.localdb.last.result}] == 1}"
            next-item %(key)s_act_swg_policy_assign_1
        }
        {
            caption "Locked User Out"
            expression "expr {[mcget {session.localdb.last.result}] == 2}"
            next-item %(key)s_end_deny
        }
        {
            caption fallback
            next-item %(key)s_end_deny
        }
    }
}

apm policy policy-item %(key)s_act_swg_policy_assign_1 {
    agents {
        %(key)s_act_swg_policy_assign_1_ag {
            type resource-assign
        }
    }
    caption "SWG Scheme Assign(1)"
    color 1
    item-type action
    rules {
        {
            caption fallback
            next-item %(key)s_end_allow
        }
    }
}

apm policy policy-item %(key)s_end_allow {
    agents {
        %(key)s_end_allow_ag {
            type ending-allow
        }
    }
    caption Allow
    color 1
    item-type ending
}
apm policy policy-item %(key)s_end_deny {
    agents {
        %(key)s_end_deny_ag {
            type ending-deny
        }
    }
    caption Deny
    color 2
    item-type ending
}
apm policy policy-item %(key)s_ent {
    caption Start
    color 1
    rules {
        {
            caption fallback
            next-item %(key)s_act_HTTP_407_Response
        }
    }
}

apm aaa localdb %(key)s-userDB {}
apm policy agent aaa-localdb %(key)s_act_localdb_auth_ag {
    localdb-instance %(key)s-userDB
}
apm policy agent category-lookup %(key)s-per_request_act_category_lookup_ag {
    input http-uri
    lookup-type all
}
apm policy agent ending-allow %(key)s_end_allow_ag { }
apm policy agent ending-deny %(key)s_end_deny_ag {
    customization-group %(key)s_end_deny_ag
}
apm policy agent logon-page %(key)s_act_HTTP_407_Response_ag {
    customization-group %(key)s_act_HTTP_407_Response_ag
    http-401-auth-level basic
    type 407
}
apm policy agent resource-assign %(key)s_act_swg_policy_assign_1_ag {
    rules {
        {
            swg-scheme %(key)s-swg_schema
        }
    }
    type swg
}
apm profile access %(key)s {
    accept-languages { en }
    access-policy %(key)s
    app-service none
    customization-group %(key)s_logout
    default-language en
    eps-group %(key)s_eps
    errormap-group %(key)s_errormap
    framework-installation-group %(key)s_frameworkinstallation
    general-ui-group %(key)s_general_ui
    generation 10
    generation-action noop
    log-settings {
        /Common/default-log-setting
    }
    logout-uri-include none
    modified-since-last-policy-sync true
    ntlm-auth-name none
    type swg-explicit
    user-identity-method ip-address
}

ltm virtual %(key)s-proxy {
    destination %(destination)s
    ip-protocol tcp
    mask 255.255.255.255
    per-flow-request-access-policy %(key)s-per_request
    profiles {
        /Common/rba { }
        /Common/tcp { }
        /Common/websso { }
        %(key)s { }
        %(key)s-forward { }
    }
    source 0.0.0.0%%%(rd_id)s/0
    source-address-translation {
        type automap
    }
    translate-address enabled
    translate-port enabled
}

ltm virtual %(key)s-ssl {
    destination 0.0.0.0%%%(rd_id)s:443
    ip-protocol tcp
    mask any
    per-flow-request-access-policy %(key)s-per_request
    profiles {
        /Common/http { }
        /Common/rba { }
        /Common/tcp { }
        /Common/websso { }
        %(key)s { }
        %(key)s-swg_client_ssl_forward {
            context clientside
        }
        %(key)s-swg_server_ssl {
            context serverside
        }
    }
    source 0.0.0.0%%%(rd_id)s/0
    source-address-translation {
        type automap
    }
    translate-address disabled
    translate-port enabled
    vlans {
        %(key)s-swg_tunnel
    }
    vlans-enabled
}

apm swg-scheme %(key)s-swg_schema { }
apm url-filter %(key)s-swg_filter {
    #allowed-categories { /Common/Social_Web_-_Twitter /Common/Social_Web_-_Various /Common/Restaurants_and_Dining /Common/Facebook_Apps /Common/Facebook_Photo_Upload /Common/Facebook_Chat /Common/Blog_Commenting /Common/Facebook_Questions /Common/Web_Chat /Common/Facebook_Groups /Common/Facebook_Video_Upload /Common/YouTube_Video_Upload /Common/Facebook_Commenting /Common/Facebook_Events /Common/Twitter_Follow /Common/Social_Web_-_LinkedIn /Common/Twitter_Posting /Common/Facebook_Posting /Common/LinkedIn_Connections /Common/LinkedIn_Jobs /Common/YouTube_Commenting /Common/Unauthorized_Mobile_Marketplaces /Common/LinkedIn_Updates /Common/Advanced_Malware_Payloads /Common/Alcohol_and_Tobacco /Common/Social_Web_-_Facebook /Common/Advanced_Malware_Command_and_Control /Common/Educational_Video /Common/Files_Containing_Passwords /Common/Custom-Encrypted_Uploads /Common/Dynamic_DNS /Common/Potentially_Exploited_Documents /Common/Mobile_Malware /Common/Entertainment_Video /Common/Surveillance /Common/Emerging_Exploits /Common/Suspicious_Embedded_Link /Common/Malicious_Embedded_iFrame /Common/Malicious_Embedded_Link /Common/Blogs_and_Personal_Sites /Common/Religion /Common/Hosted_Business_Applications /Common/Parked_Domain /Common/Hobbies /Common/Nutrition /Common/Web_Collaboration /Common/Abused_Drugs /Common/Web_and_Email_Spam /Common/Text_and_Media_Messaging /Common/Suspicious_Content /Common/Pro-Choice /Common/Organizational_Email /Common/Internet_Communication /Common/Twitter_Mail /Common/Elevated_Exposure /Common/Extended_Protection /Common/Prescribed_Medications /Common/Bot_Networks /Common/Keyloggers /Common/Potentially_Unwanted_Software /Common/Phishing_and_Other_Frauds /Common/Spyware /Common/Dynamic_Content /Common/File_Download_Servers /Common/Adult_Content /Common/Uncategorized /Common/Network_Errors /Common/Web_Infrastructure /Common/Private_IP_Addresses /Common/Web_Images /Common/Content_Delivery_Networks /Common/Miscellaneous /Common/Malicious_Web_Sites /Common/Computer_Security /Common/Security /Common/Professional_and_Worker_Organizations /Common/Social_and_Affiliation_Organizations /Common/Service_and_Philanthropic_Organizations /Common/Social_Organizations /Common/Social_Networking /Common/Reference_Materials /Common/Educational_Materials /Common/Message_Boards_and_Forums /Common/Peer-to-Peer_File_Sharing /Common/Internet_Radio_and_TV /Common/Marijuana /Common/Productivity /Common/Streaming_Media /Common/Educational_Institutions /Common/Internet_Telephony /Common/Sport_Hunting_and_Gun_Clubs /Common/Application_and_Software_Download /Common/Instant_Messaging /Common/Pay-to-Surf /Common/Real_Estate /Common/Online_Brokerage_and_Trading /Common/Lingerie_and_Swimsuit /Common/Personals_and_Dating /Common/LinkedIn_Mail /Common/Sex_Education /Common/Advocacy_Groups /Common/Pro-Life /Common/Government /Common/Gay_or_Lesbian_or_Bisexual_Interest /Common/Traditional_Religions /Common/Classifieds_Posting /Common/Information_Technology /Common/Blog_Posting /Common/Viral_Video /Common/YouTube_Sharing /Common/Non-Traditional_Religions /Common/Facebook_Friends /Common/Social_Web_-_YouTube /Common/Alternative_Journals /Common/Facebook_Games /Common/Hacking /Common/Web_Hosting /Common/General_Email /Common/Facebook_Mail /Common/Search_Engines_and_Portals /Common/Proxy_Avoidance /Common/Political_Organizations /Common/Military /Common/Vehicles /Common/Financial_Data_and_Services /Common/Media_File_Download /Common/Sex /Common/Cultural_Institutions /Common/Nudity /Common/Advertisements /Common/Tasteless /Common/Website_Translation /Common/Weapons /Common/Health /Common/Militancy_and_Extremist /Common/Intolerance /Common/Drugs /Common/Violence /Common/Travel /Common/Job_Search /Common/Sports /Common/Shopping /Common/Illegal_or_Questionable /Common/Personal_Network_Storage_and_Backup /Common/Bandwidth /Common/Gambling /Common/Entertainment /Common/Education /Common/Adult_Material /Common/Special_Events /Common/Business_and_Economy /Common/Abortion /Common/News_and_Media /Common/Society_and_Lifestyles /Common/Internet_Auctions /Common/Compromised_Websites /Common/Newly_Registered_Websites %(key)s-myCustomCategory }
    #blocked-categories { /Common/User-Defined %(key)s-myGame /Common/Games }
}

sys url-db url-category %(key)s-myCustomCategory {
    cat-number 1928
    default-action allow
    display-name myCustomCategory
    initial-disposition 4
    is-custom true
    urls {
        http://10.75.2.100/\* {
            type glob-match
        }
        http://10.75.2.103/\* {
            type glob-match
        }
        http://ws1.swgtest.com/\* {
            type glob-match
        }
        http://ws109.swgtest.com/ { }
        https://10.75.2.100/\* {
            type glob-match
        }
        https://10.75.2.103/\* {
            type glob-match
        }
        https://ws1.swgtest.com/\* {
            type glob-match
        }
        https://ws109.swgtest.com/ { }
    }
}
sys url-db url-category %(key)s-myGame {
    cat-number 1929
    display-name myGame
    is-custom true
    urls {
        http://ws108.swgtest.com/ { }
        https://ws108.swgtest.com/ { }
    }
}

net fdb tunnel %(key)s-swg_tunnel { }

net tunnels tunnel %(key)s-swg_tunnel {
    profile /Common/tcp-forward
}


ltm profile http %(key)s-forward {
    accept-xff disabled
    app-service none
    defaults-from /Common/http-explicit
    encrypt-cookies none
    enforcement {
        max-header-count 64
        max-header-size 32768
        max-requests 0
        pipeline allow
        truncated-redirects disabled
        unknown-method allow
    }
    explicit-proxy {
        bad-request-message "lxu - bad request"
        bad-response-message "lxu - bad response"
        connect-error-message "lxu - connection failed"
        default-connect-handling allow
        dns-error-message "lxu - dns lookup failed"
        dns-resolver %(key)s-swg_resolvers
        route-domain %(rd_name)s
        tunnel-name %(key)s-swg_tunnel
    }
    fallback-host none
    fallback-status-codes none
    header-erase none
    header-insert none
    insert-xforwarded-for disabled
    lws-separator none
    lws-width 80
    oneconnect-transformations disabled
    proxy-type explicit
    redirect-rewrite none
    request-chunking preserve
    response-chunking selective
    response-headers-permitted none
    server-agent-name BigIP
    sflow {
        poll-interval 0
        poll-interval-global yes
        sampling-rate 0
        sampling-rate-global yes
    }
    via-request preserve
    via-response preserve
    xff-alternative-names none
}

net dns-resolver %(key)s-swg_resolvers {
    forward-zones {
        swgTest.com {
            nameservers {
                10.80.1.11%%%(rd_id)s:53 { }
            }
        }
    }
    route-domain %(rd_name)s
}

ltm profile client-ssl %(key)s-swg_client_ssl_forward {
    app-service none
    cert %(ssl_cert)s
    cert-extension-includes { basic-constraints subject-alternative-name }
    cert-key-chain {
        SSL_Test {
            cert %(ssl_cert)s
            key %(ssl_key)s
        }
    }
    cert-lifespan 30
    cert-lookup-by-ipaddr-port disabled
    chain none
    ciphers !SSLv2:ALL:!DH:!ADH:!EDH:@SPEED
    defaults-from /Common/clientssl
    destination-ip-blacklist none
    destination-ip-whitelist none
    forward-proxy-bypass-default-action intercept
    hostname-blacklist none
    hostname-whitelist none
    inherit-certkeychain false
    key %(ssl_key)s
    passphrase none
    proxy-ca-cert /Common/default.crt
    proxy-ca-key /Common/default.key
    source-ip-blacklist none
    source-ip-whitelist none
    ssl-forward-proxy enabled
    ssl-forward-proxy-bypass enabled
}

ltm profile server-ssl %(key)s-swg_server_ssl {
    alert-timeout 10
    app-service none
    cache-size 262144
    cache-timeout 3600
    cert none
    chain none
    ciphers !SSLv2:!EXPORT:!DH:RSA+RC4:RSA+AES:RSA+DES:RSA+3DES:ECDHE+AES:ECDHE+3DES:@SPEED
    defaults-from /Common/serverssl
    generic-alert enabled
    handshake-timeout 10
    key none
    mod-ssl-methods disabled
    mode enabled
    options { dont-insert-empty-fragments }
    proxy-ssl disabled
    renegotiate-period indefinite
    renegotiate-size indefinite
    renegotiation enabled
    secure-renegotiation request
    server-name none
    session-ticket disabled
    sni-default false
    sni-require false
    ssl-forward-proxy enabled
    ssl-forward-proxy-bypass enabled
    ssl-sign-hash any
    strict-resume disabled
    unclean-shutdown enabled
}


apm policy access-policy %(key)s-per_request {
    default-ending %(key)s-per_request_end_reject
    items {
        %(key)s-per_request_act_category_lookup { }
        %(key)s-per_request_act_url_filter_lookup { }
        %(key)s-per_request_end_allow { }
        %(key)s-per_request_end_reject { }
        %(key)s-per_request_ent { }
    }
    start-item %(key)s-per_request_ent
    type per-rq-policy
}
apm policy policy-item %(key)s-per_request_act_category_lookup {
    agents {
        %(key)s-per_request_act_category_lookup_ag {
            type category-lookup
        }
    }
    caption "Category Lookup"
    color 1
    item-type action
    rules {
        {
            caption fallback
            next-item %(key)s-per_request_act_url_filter_lookup
        }
    }
}
apm policy policy-item %(key)s-per_request_act_url_filter_lookup {
    agents {
        %(key)s-per_request_act_url_filter_lookup_ag {
            type url-filter-lookup
        }
    }
    caption "URL Filter Assign"
    color 1
    item-type action
    rules {
        {
            caption Allow
            expression "expr { [mcget {perflow.urlfilter_lookup.result.action}] == 1 }"
            next-item %(key)s-per_request_end_allow
        }
        {
            caption fallback
            next-item %(key)s-per_request_end_reject
        }
    }
}
apm policy policy-item %(key)s-per_request_end_allow {
    agents {
        %(key)s-per_request_end_allow_ag {
            type ending-allow
        }
    }
    caption Allow
    color 1
    item-type ending
}
apm policy policy-item %(key)s-per_request_end_reject {
    agents {
        %(key)s-per_request_end_reject_ag {
            type ending-reject
        }
    }
    caption Reject
    color 2
    item-type ending
}
apm policy policy-item %(key)s-per_request_ent {
    caption Start
    color 1
    rules {
        {
            caption fallback
            next-item %(key)s-per_request_act_category_lookup
        }
    }
}
apm policy agent category-lookup %(key)s-per_request_act_category_lookup_ag {
    input http-uri
    lookup-type all
}
apm policy agent ending-allow %(key)s-per_request_end_allow_ag { }
apm policy agent ending-reject %(key)s-per_request_end_reject_ag { }
apm policy agent url-filter-lookup %(key)s-per_request_act_url_filter_lookup_ag {
    filter-name %(key)s-swg_filter
}
        """

    def __init__(self, name='SWG-explicit', rd=0, destination=None,
                 ssl_cert=None, ssl_key=None):
        self.name = name
        self.rd = rd
        self.destination = destination
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        super(SWGExplicit, self).__init__()

    def tmsh(self, obj):
        rd_id = self.rd.id()
        rd_name = self.rd.name
        destination = str(self.destination)
        key = self.get_full_path()
        value = obj.format(key=key, rd_id=rd_id, rd_name=rd_name,
                           destination=destination,
                           ssl_cert=self.ssl_cert.get_full_path(),
                           ssl_key=self.ssl_key.get_full_path())
        return key, value
