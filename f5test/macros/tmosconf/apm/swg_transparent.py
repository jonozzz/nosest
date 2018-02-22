'''
Created on Mar 22, 2016

@author: jono
'''
from ..scaffolding import Stamp


class SWGTransparent(Stamp):
    TMSH = r"""
        #TMSH-VERSION: 12.1.0

        apm swg-scheme %(key)s-malware { }
        apm url-filter %(key)s-malware {
            #allowed-categories { /Common/Nutrition /Common/Adult_Material /Common/Business_and_Economy /Common/Education /Common/Government /Common/News_and_Media /Common/Religion /Common/Society_and_Lifestyles /Common/Special_Events /Common/Information_Technology /Common/Abortion /Common/Advocacy_Groups /Common/Entertainment /Common/Gambling /Common/Games /Common/Illegal_or_Questionable /Common/Job_Search /Common/Shopping /Common/Sports /Common/Tasteless /Common/Travel /Common/Vehicles /Common/Violence /Common/Weapons /Common/Drugs /Common/Militancy_and_Extremist /Common/Intolerance /Common/Health /Common/Website_Translation /Common/Advertisements /Common/User-Defined /Common/Nudity /Common/Adult_Content /Common/Sex /Common/Financial_Data_and_Services /Common/Cultural_Institutions /Common/Media_File_Download /Common/Military /Common/Political_Organizations /Common/General_Email /Common/Proxy_Avoidance /Common/Search_Engines_and_Portals /Common/Web_Hosting /Common/Web_Chat /Common/Hacking /Common/Alternative_Journals /Common/Non-Traditional_Religions /Common/Traditional_Religions /Common/Restaurants_and_Dining /Common/Gay_or_Lesbian_or_Bisexual_Interest /Common/Personals_and_Dating /Common/Alcohol_and_Tobacco /Common/Prescribed_Medications /Common/Abused_Drugs /Common/Internet_Communication /Common/Pro-Choice /Common/Pro-Life /Common/Sex_Education /Common/Lingerie_and_Swimsuit /Common/Online_Brokerage_and_Trading /Common/Educational_Institutions /Common/Instant_Messaging /Common/Application_and_Software_Download /Common/Pay-to-Surf /Common/Internet_Auctions /Common/Real_Estate /Common/Hobbies /Common/Sport_Hunting_and_Gun_Clubs /Common/Internet_Telephony /Common/Streaming_Media /Common/Productivity /Common/Marijuana /Common/Message_Boards_and_Forums /Common/Personal_Network_Storage_and_Backup /Common/Internet_Radio_and_TV /Common/Peer-to-Peer_File_Sharing /Common/Bandwidth /Common/Social_Networking /Common/Educational_Materials /Common/Reference_Materials /Common/Social_Organizations /Common/Service_and_Philanthropic_Organizations /Common/Social_and_Affiliation_Organizations /Common/Professional_and_Worker_Organizations /Common/Security /Common/Malicious_Web_Sites /Common/Computer_Security /Common/Miscellaneous /Common/Web_Infrastructure /Common/Web_Images /Common/Private_IP_Addresses /Common/Content_Delivery_Networks /Common/Dynamic_Content /Common/Network_Errors /Common/Uncategorized /Common/Spyware /Common/File_Download_Servers /Common/Phishing_and_Other_Frauds /Common/Keyloggers /Common/Potentially_Unwanted_Software /Common/Bot_Networks /Common/Extended_Protection /Common/Elevated_Exposure /Common/Emerging_Exploits /Common/Suspicious_Content /Common/Organizational_Email /Common/Text_and_Media_Messaging /Common/Web_and_Email_Spam /Common/Web_Collaboration /Common/Parked_Domain /Common/Hosted_Business_Applications /Common/Blogs_and_Personal_Sites /Common/Malicious_Embedded_Link /Common/Malicious_Embedded_iFrame /Common/Suspicious_Embedded_Link /Common/Surveillance /Common/Educational_Video /Common/Entertainment_Video /Common/Viral_Video /Common/Dynamic_DNS /Common/Potentially_Exploited_Documents /Common/Mobile_Malware /Common/Unauthorized_Mobile_Marketplaces /Common/Custom-Encrypted_Uploads /Common/Files_Containing_Passwords /Common/Advanced_Malware_Command_and_Control /Common/Advanced_Malware_Payloads /Common/Compromised_Websites /Common/Newly_Registered_Websites /Common/Collaboration_-_Office /Common/Office_-_Mail /Common/Office_-_Drive /Common/Office_-_Documents /Common/Office_-_Apps /Common/Web_Analytics /Common/Web_and_Email_Marketing /Common/Social_Web_-_Facebook /Common/LinkedIn_Updates /Common/LinkedIn_Mail /Common/LinkedIn_Connections /Common/LinkedIn_Jobs /Common/Facebook_Posting /Common/Facebook_Commenting /Common/Facebook_Friends /Common/Facebook_Photo_Upload /Common/Facebook_Mail /Common/Facebook_Events /Common/YouTube_Commenting /Common/YouTube_Video_Upload /Common/Facebook_Apps /Common/Facebook_Chat /Common/Facebook_Questions /Common/Facebook_Video_Upload /Common/Facebook_Groups /Common/Twitter_Posting /Common/Twitter_Mail /Common/Twitter_Follow /Common/YouTube_Sharing /Common/Facebook_Games /Common/Social_Web_-_YouTube /Common/Social_Web_-_Twitter /Common/Social_Web_-_LinkedIn /Common/Social_Web_-_Various /Common/Classifieds_Posting /Common/Blog_Posting /Common/Blog_Commenting }
            #blocked-categories { %(key)s-testing_malware }
        }
        apm policy access-policy %(key)s {
            default-ending %(key)s_end_deny
            items {
                %(key)s_act_swg_policy_assign { }
                %(key)s_end_allow { }
                %(key)s_end_deny { }
                %(key)s_ent { }
            }
            start-item %(key)s_ent
        }
        apm policy access-policy %(key)s-malware_filter {
            default-ending %(key)s-malware_filter_end_reject
            items {
                %(key)s-malware_filter_act_category_lookup { }
                %(key)s-malware_filter_act_url_filter_lookup { }
                %(key)s-malware_filter_end_allow { }
                %(key)s-malware_filter_end_reject { }
                %(key)s-malware_filter_ent { }
            }
            start-item %(key)s-malware_filter_ent
            type per-rq-policy
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
        apm policy policy-item %(key)s_act_swg_policy_assign {
            agents {
                %(key)s_act_swg_policy_assign_ag {
                    type resource-assign
                }
            }
            caption "SWG Scheme Assign"
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
                    next-item %(key)s_act_swg_policy_assign
                }
            }
        }
        apm policy policy-item %(key)s-malware_filter_act_category_lookup {
            agents {
                %(key)s-malware_filter_act_category_lookup_ag {
                    type category-lookup
                }
            }
            caption "Category Lookup"
            color 1
            item-type action
            rules {
                {
                    caption fallback
                    next-item %(key)s-malware_filter_act_url_filter_lookup
                }
            }
        }
        apm policy policy-item %(key)s-malware_filter_act_url_filter_lookup {
            agents {
                %(key)s-malware_filter_act_url_filter_lookup_ag {
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
                    next-item %(key)s-malware_filter_end_allow
                }
                {
                    caption fallback
                    next-item %(key)s-malware_filter_end_allow
                }
            }
        }
        apm policy policy-item %(key)s-malware_filter_end_allow {
            agents {
                %(key)s-malware_filter_end_allow_ag {
                    type ending-allow
                }
            }
            caption Allow
            color 1
            item-type ending
        }
        apm policy policy-item %(key)s-malware_filter_end_reject {
            agents {
                %(key)s-malware_filter_end_reject_ag {
                    type ending-reject
                }
            }
            caption Reject
            color 2
            item-type ending
        }
        apm policy policy-item %(key)s-malware_filter_ent {
            caption Start
            color 1
            rules {
                {
                    caption fallback
                    next-item %(key)s-malware_filter_act_category_lookup
                }
            }
        }
        apm policy agent category-lookup %(key)s-malware_filter_act_category_lookup_ag {
            input http-uri
        }
        apm policy agent ending-allow %(key)s_end_allow_ag { }
        apm policy agent ending-allow %(key)s-malware_filter_end_allow_ag { }
        apm policy agent ending-deny %(key)s_end_deny_ag {
            customization-group %(key)s_end_deny_ag
        }
        apm policy agent ending-reject %(key)s-malware_filter_end_reject_ag { }
        apm policy agent resource-assign %(key)s_act_swg_policy_assign_ag {
            rules {
                {
                    swg-scheme %(key)s-malware
                }
            }
            type swg
        }
        apm policy agent url-filter-lookup %(key)s-malware_filter_act_url_filter_lookup_ag {
            filter-name %(key)s-malware
        }
        apm profile access %(key)s {
            accept-languages { en }
            access-policy %(key)s
            app-service none
            customization-group %(key)s_logout
            default-language en
            domain-mode single-domain
            eps-group %(key)s_eps
            errormap-group %(key)s_errormap
            framework-installation-group %(key)s_frameworkinstallation
            general-ui-group %(key)s_general_ui
            generation 5
            generation-action noop
            log-settings {
                /Common/default-log-setting
            }
            logout-uri-include none
            modified-since-last-policy-sync true
            ntlm-auth-name none
            type swg-transparent
            user-identity-method ip-address
        }
        apm resource sandbox %(key)s-citrix-client-package {
            base-uri %(key)s-public/citrix
            description "Sandbox for Citrix client package files"
        }
        apm resource sandbox %(key)s-hosted-content {
            base-uri %(key)s-public/share
            description "Sandbox for static contents"
        }

        ltm virtual %(key)s-swg_all {
            destination 0.0.0.0%(rd_id)s:0
            mask any
            profiles {
                /Common/ipother { }
            }
            source 0.0.0.0%(rd_id)s/0
            source-address-translation {
                type automap
            }
            translate-address enabled
            translate-port disabled
        }
        ltm virtual %(key)s-swg_http {
            destination 0.0.0.0%(rd_id)s:80
            ip-protocol tcp
            mask any
            per-flow-request-access-policy %(key)s-malware_filter
            profiles {
                /Common/antifraud { }
                /Common/http { }
                /Common/rba { }
                /Common/tcp { }
#                /Common/websecurity { }
                /Common/websso { }
                %(key)s { }
                %(key)s-analytics01 { }
            }
            source 0.0.0.0%(rd_id)s/0
            translate-address disabled
            translate-port enabled
            vlans {
                %(key)s-vlan_3595
                %(key)s-vlan_3596
            }
            vlans-enabled
        }
        ltm virtual %(key)s-swg_ssl {
            destination 0.0.0.0%(rd_id)s:443
            ip-protocol tcp
            mask any
            profiles {
                /Common/http { }
                /Common/tcp { }
                %(key)s_client_ssl {
                    context clientside
                }
                %(key)s_server_ssl {
                    context serverside
                }
            }
            source 0.0.0.0%(rd_id)s/0
            source-address-translation {
                type automap
            }
            translate-address disabled
            translate-port enabled
        }
        ltm virtual-address 0.0.0.0%(rd_id)s {
            address any
            arp disabled
            icmp-echo disabled
            mask any
            #spanning enabled
            traffic-group /Common/traffic-group-1
        }
        ltm profile analytics %(key)s-analytics01 {
            app-service none
            collect-geo enabled
            collect-ip enabled
            collect-max-tps-and-throughput enabled
            collect-methods enabled
            collect-page-load-time enabled
            collect-response-codes enabled
            collect-subnets enabled
            collect-url enabled
            collect-user-agent enabled
            collect-user-sessions enabled
            defaults-from /Common/analytics
            description none
            notification-email-addresses none
            session-cookie-security ssl-only
            session-timeout 300
            session-timeout-minutes 5
            traffic-capture {
                %(key)s-capturing-for-analytics01 { }
            }
        }
        ltm profile client-ssl %(key)s_client_ssl {
            app-service none
            cert %(ssl_cert)s
            cert-key-chain {
                SSL_Test {
                    cert %(ssl_cert)s
                    key %(ssl_key)s
                }
            }
            chain none
            ciphers !SSLv2:ALL:!DH:!ADH:!EDH:@SPEED
            defaults-from /Common/clientssl
            inherit-certkeychain false
            key %(ssl_key)s
            passphrase none
            proxy-ca-cert /Common/default.crt
            proxy-ca-key /Common/default.key
            ssl-forward-proxy enabled
            ssl-forward-proxy-bypass enabled
        }
        ltm profile server-ssl %(key)s_server_ssl {
            app-service none
            ca-file %(ssl_cert)s
            ciphers !SSLv2:!EXPORT:!DH:RSA+RC4:RSA+AES:RSA+DES:RSA+3DES:ECDHE+AES:ECDHE+3DES:@SPEED
            defaults-from /Common/serverssl
            expire-cert-response-control ignore
            peer-cert-mode require
            ssl-forward-proxy enabled
            ssl-forward-proxy-bypass enabled
            untrusted-cert-response-control ignore
        }
        sys url-db url-category %(key)s-testing_internet {
            cat-number 1930
            default-action allow
            display-name testing_internet
            initial-disposition 4
            is-custom true
            urls {
                http://172.152.100.100%(rd_id)s/\* {
                    type glob-match
                }
                https://172.152.100.100%(rd_id)s/\* {
                    type glob-match
                }
            }
        }
        sys url-db url-category %(key)s-testing_malware {
            cat-number 1931
            display-name testing_malware
            is-custom true
            urls {
                http://172.152.99.100%(rd_id)s/\* {
                    type glob-match
                }
                https://172.152.99.100%(rd_id)s/\* {
                    type glob-match
                }
            }
        }
        """

    def __init__(self, name='SWG-transparent', rd=None, ssl_cert=None,
                 ssl_key=None, vlans=None):
        self.name = name
        self.rd = rd
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.vlans = vlans
        super(SWGTransparent, self).__init__()

    def tmsh(self, obj):
        if self.rd:
            rd_id = '%%%d' % self.rd.id()
        else:
            rd_id = ''

        obj['ltm virtual %(key)s-swg_http']['vlans'] = [x.get_full_path()
                                                        for x in self.vlans]
        key = self.get_full_path()
        value = obj.format(key=key, rd_id=rd_id,
                           ssl_cert=self.ssl_cert.get_full_path(),
                           ssl_key=self.ssl_key.get_full_path())
        return key, value
