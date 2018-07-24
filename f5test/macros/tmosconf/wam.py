'''
Created on Mar 22, 2016

@author: jono
'''
from .scaffolding import Stamp
from .profile import BaseProfile
import logging
from copy import deepcopy
# from ...base import enum
# from ...utils.parsers import tmsh
# from ...utils.parsers.tmsh import RawEOL

LOG = logging.getLogger(__name__)


class WamResource(Stamp):
    TMSH = r"""
        wam resource url %(key)s {
            type js
            url http://s2.gbbtest.com/aam/js/js97.js
        }
    """

    def __init__(self, name='aam', type='js',  # @ReservedAssignment
                 url='http://s2.gbbtest.com/aam/js/js1.js'):
        self.name = name
        self.type = type
        self.url = url
        super(WamResource, self).__init__()

    def tmsh(self, obj):
        key = self.get_full_path()
        obj['wam resource url %(key)s']['type'] = self.type
        obj['wam resource url %(key)s']['url'] = self.url
        value = obj.format(key=key, _maxdepth=1)

        return key, value


class Aam(Stamp, BaseProfile):
    built_in = False

    TMSH = r"""
        ltm profile web-acceleration %(wam_profile)s {
            app-service none
            applications { %(key)s-html_app1 }
            cache-aging-rate 9
            cache-client-cache-control-mode all
            cache-insert-age-header enabled
            cache-max-age 3600
            cache-max-entries 1000
            cache-object-max-size 50000
            cache-object-min-size 0
            cache-size 100mb
            cache-uri-exclude none
            cache-uri-include { .* }
            cache-uri-include-override none
            cache-uri-pinned none
            defaults-from /Common/webacceleration
        }

        wam application %(key)s-html_app1 {
            code 47893
            content-expiration-time 2014-06-19:14:28:04
            hosts {
                s2.gbbtest.com {
                    code 89400
                }
                10.1.2.3 {
                    code 86785
                }
            }
            policy %(key)s-TestPolicy
        }

        wam policy %(key)s-TestPolicy {
            code 64664
            nodes {
                JPG {
                    app-service none
#                    assembly-concatenation-sets none
                    assembly-css-inlining-urls none
                    assembly-css-reorder-urls none
#                    assembly-dns-prefetch-domain-lists none
                    assembly-image-inlining-urls none
                    assembly-js-inlining-urls none
                    assembly-js-reorder-urls none
                    cache-stand-in-period 0
                    code 76653
                    defaults-from none
                    description none
                    jpeg-quality 10
                    lifetime-cache-control-extensions none
                    lifetime-cache-max-age 14400
                    lifetime-honor-ows no
                    lifetime-honor-ows-values none
                    lifetime-honor-request yes
                    lifetime-honor-request-values { max-age max-stale min-fresh }
                    lifetime-http-heuristic 50
                    lifetime-insert-no-cache no
                    lifetime-preserve-response yes
                    lifetime-preserve-response-values { all-values }
                    lifetime-response-max-age undefined
                    lifetime-response-s-maxage undefined
                    lifetime-stand-in-codes { 404 500 504 }
                    lifetime-use-heuristic no
                    optimize-image to-jpeg
                    order 3
                    response-codes-cached { 300 301 }
                    video-optimization-ad-policy none
                    matching {
                        extension {
                            values {
                                "jpg JPG" { }
                            }
                        }
                        path-segment:image_path(L1,key) {
                            arg-alias image_path
                            arg-ordinal 1
                            value-case-sensitive yes
                            values {
                                img { }
                            }
                        }
                    }
                    variation {
                        host {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        method {
                            value-case-sensitive yes
                            values {
                                "GET POST HEAD" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        query-param:"All Query Parameters" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        path-segment:"All Path Segments" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        cookie:"All Cookies" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        user-agent {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        referrer {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        protocol {
                            value-case-sensitive yes
                            values {
                                "HTTP HTTPS" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        header:"All Headers" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        client-ip {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                    }
                }
                Rerouted {
                    app-service none
#                    assembly-concatenation-sets none
                    assembly-css-inlining-urls none
                    assembly-css-reorder-urls none
#                    assembly-dns-prefetch-domain-lists none
                    assembly-image-inlining-urls none
                    assembly-js-inlining-urls none
                    assembly-js-reorder-urls none
                    code 82874
                    defaults-from none
                    description "Represents rerouted requests"
                    order 1
                    response-codes-cached none
                    video-optimization-ad-policy none
                }
                Unmatched {
                    app-service none
#                    assembly-concatenation-sets none
                    assembly-css-inlining-urls none
                    assembly-css-reorder-urls none
#                    assembly-dns-prefetch-domain-lists none
                    assembly-image-inlining-urls none
                    assembly-js-inlining-urls none
                    assembly-js-reorder-urls none
                    code 47305
                    defaults-from none
                    description "Represents unmatched requests"
                    order 0
                    response-codes-cached none
                    video-optimization-ad-policy none
                }
                inlining {
                    app-service none
#                    assembly-concatenation-sets none
                    assembly-css-inlining enabled
                    assembly-css-inlining-urls { %(key)s-aamCss1 }
                    assembly-css-reorder enabled
                    assembly-css-reorder-urls { %(key)s-aamCss2 }
#                    assembly-dns-prefetch-domain-lists none
                    assembly-image-inlining enabled
                    assembly-image-inlining-max-size 8kb
                    assembly-image-inlining-urls { %(key)s-aamImg2 %(key)s-aamImg1 }
#                    assembly-intelligent-client-cache enabled
                    assembly-js-inlining enabled
                    assembly-js-inlining-urls { %(key)s-aamJs1 %(key)s-js1 %(key)s-js10 %(key)s-js100 %(key)s-js11 %(key)s-js12 %(key)s-js13 %(key)s-js14 %(key)s-js15 %(key)s-js16 %(key)s-js17 %(key)s-js18 %(key)s-js19 %(key)s-js2 %(key)s-js20 %(key)s-js21 %(key)s-js22 %(key)s-js23 %(key)s-js24 %(key)s-js25 %(key)s-js26 %(key)s-js27 %(key)s-js28 %(key)s-js29 }
                    assembly-js-reorder disabled
                    assembly-js-reorder-urls none
                    assembly-minification enabled
                    cache-stand-in-period 0
                    code 40727
                    defaults-from none
                    description none
                    lifetime-cache-control-extensions none
                    lifetime-cache-max-age 14400
                    lifetime-honor-ows no
                    lifetime-honor-ows-values none
                    lifetime-honor-request yes
                    lifetime-honor-request-values { max-age max-stale min-fresh }
                    lifetime-http-heuristic 50
                    lifetime-insert-no-cache no
                    lifetime-preserve-response yes
                    lifetime-preserve-response-values { all-values }
                    lifetime-response-max-age undefined
                    lifetime-response-s-maxage undefined
                    lifetime-stand-in-codes { 404 500 504 }
                    lifetime-use-heuristic no
                    order 2
                    response-codes-cached { 300 301 }
                    video-optimization-ad-policy none
                    matching {
                        path {
                            values {
                                "/aam/home.html /aam/css/mystyle1.css /aam/js/" { }
                            }
                        }
                    }
                    variation {
                        host {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        method {
                            value-case-sensitive yes
                            values {
                                "GET POST HEAD" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        query-param:"All Query Parameters" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        path-segment:"All Path Segments" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        cookie:"All Cookies" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        user-agent {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        referrer {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        protocol {
                            value-case-sensitive yes
                            values {
                                "HTTP HTTPS" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        header:"All Headers" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        client-ip {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                    }
                }
                reordering {
                    app-service none
#                    assembly-concatenation-sets none
                    assembly-css-inlining disabled
                    assembly-css-inlining-urls { %(key)s-aamCss2 }
                    assembly-css-reorder enabled
                    assembly-css-reorder-urls { %(key)s-aamCss2 }
#                    assembly-dns-prefetch-domain-lists none
                    assembly-image-inlining-urls none
                    assembly-js-inlining-urls none
                    assembly-js-reorder enabled
                    assembly-js-reorder-urls { %(key)s-aamJs1 }
                    cache-first-hit yes
                    cache-stand-in-period 0
                    code 4581
                    defaults-from none
                    description none
                    lifetime-cache-control-extensions none
                    lifetime-cache-max-age 5
                    lifetime-honor-ows no
                    lifetime-honor-ows-values none
                    lifetime-honor-request yes
                    lifetime-honor-request-values { max-age max-stale min-fresh }
                    lifetime-http-heuristic 50
                    lifetime-insert-no-cache no
                    lifetime-preserve-response yes
                    lifetime-preserve-response-values { all-values }
                    lifetime-response-max-age undefined
                    lifetime-response-s-maxage undefined
                    lifetime-stand-in-codes { 404 500 504 }
                    lifetime-use-heuristic no
                    order 4
                    request-queueing disabled
                    response-codes-cached { 300 301 }
                    video-optimization-ad-policy none
                    matching {
                        path {
                            values {
                                "/aam/reordering_test.html /aam/testFile1.html" { }
                            }
                        }
                    }
                    variation {
                        host {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        method {
                            value-case-sensitive yes
                            values {
                                "GET POST HEAD" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        query-param:"All Query Parameters" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        path-segment:"All Path Segments" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        cookie:"All Cookies" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        user-agent {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        referrer {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        protocol {
                            value-case-sensitive yes
                            values {
                                "HTTP HTTPS" {
                                    cache-as different
                                    match-all yes
                                }
                            }
                        }
                        header:"All Headers" {
                            arg-all yes
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                        client-ip {
                            value-case-sensitive yes
                            values {
                                "All Values" {
                                    cache-as same
                                    match-all yes
                                }
                            }
                        }
                    }
                }
            }
            publish-build 66
            state published
        }
        wam resource url %(key)s-aamCss1 {
            type css
            url http://s2.gbbtest.com/aam/css/mystyle1.css
        }
        wam resource url %(key)s-aamCss2 {
            type css
            url http://s2.gbbtest.com/aam/css/mystyle2.css
        }
        wam resource url %(key)s-aamImg1 {
            type image
            url http://s2.gbbtest.com/aam/p00.gif
        }
        wam resource url %(key)s-aamImg2 {
            type image
            url http://s2.gbbtest.com/aam/img/p00.gif
        }
        wam resource url %(key)s-aamJs1 {
            type js
            url http://s2.gbbtest.com/aam/js/myjs.js
        }
    """

    def __init__(self, name='aam', js_inlining_urls=None, state='published'):
        self.name = name
        self.js_inlining_urls = js_inlining_urls
        self.wam_profile = '%s-webacceleration' % name
        self.state = state
        super(Aam, self).__init__()

    def get_vs_profile(self):
        return super(Aam, self).get_vs_profile(self.wam_profile)

    def tmsh(self, obj):
        key = self.get_full_path()
        a = obj['wam policy %(key)s-TestPolicy']
        a['nodes']['inlining']['assembly-js-inlining-urls'] = [x.get_full_path() for x in self.js_inlining_urls]
        a['state'] = self.state
        
        # Place a copy in Drafts
        draft = self.folder.SEPARATOR.join((self.folder.key(), 'Drafts', str(self.name)))
        obj['wam policy %s-TestPolicy' % draft] = deepcopy(a)
        obj['wam policy %s-TestPolicy' % draft]['state'] = 'development'
        value = obj.format(key=key, wam_profile=self.wam_profile)

        return key, value
