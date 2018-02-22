'''
Created on May 4, 2016

@author: jono
'''
import logging
import netaddr
import itertools as IT

from ..ltm import (Node, Pool, VirtualServer)
from ..profile import (Profile)
from ..wam import Aam, WamResource
from . import BaseConfig


LOG = logging.getLogger(__name__)


class WAMConfig(BaseConfig):
    EXTERNAL = 'external'

    def __init__(self, node_ips, vs_ip, vs_port=None, *args, **kwargs):
        self.node_ips = node_ips or []
        self.vs_ip = vs_ip
        self.vs_port = vs_port
        super(WAMConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('WAM configuration')

        all_nodes = []
        if self.node_ips:
            rd = self.route_domain
            for ip in self.node_ips:
                node = Node(ip, rd=rd)
                self.folder.hook(node)
                all_nodes.append(node)

        http_ports = IT.repeat(80)
        p = Pool('WAM-Pool', all_nodes, http_ports)
        self.folder.hook(p)

        profile_http = Profile('http')
        profile_tcp = Profile('tcp')
        profile_httpcomp = Profile('httpcompression')
        self.common.hook(profile_httpcomp, profile_http, profile_tcp)

        resources = []
        for _ in range(100):
            resources.append(WamResource('js-%d' % _, type='js',
                                         url='http://s2.gbbtest.com/aam/js/js%d.js' % _))
        self.folder.hook(*resources)
        aam_profile = Aam(js_inlining_urls=resources)
        self.folder.hook(aam_profile)

        self.folder.add('Drafts')

        vs_ip = netaddr.IPNetwork(self.vs_ip)

        v = VirtualServer('WAM-VS', vs_ip, self.vs_port, p,
                          profiles=[profile_tcp, profile_http, profile_httpcomp,
                                    aam_profile])
        self.folder.hook(v)

        return self.tree
