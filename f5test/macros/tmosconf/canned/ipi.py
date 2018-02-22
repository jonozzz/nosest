'''
Created on May 4, 2016

@author: jono
'''
import logging

from ..profile import (ClientSsl, references, combine)
from ..security import (IpIntelligenceFeed, IpIntelligenceFeedList,
                        IpIntelligencePolicy)
from ..sys import SSLCert, SSLKey
from . import BaseConfig


LOG = logging.getLogger(__name__)


class IPIConfig(BaseConfig):

    def __init__(self, node_ips, vs_ip, vs_port=443, ssl_key=None, ssl_cert=None,
                 *args, **kwargs):
        self.node_ips = node_ips
        self.vs_ip = vs_ip
        self.vs_port = vs_port
        self.ssl_key = ssl_key
        self.ssl_cert = ssl_cert
        super(IPIConfig, self).__init__(*args, **kwargs)

    def setup(self):
        LOG.info('SSL Mirror IPI configuration')
        v = self.context.version

        if not (v.product.is_bigip and v >= 'bigip 11.5.0'):
            LOG.info('Sorry, no IPI support.')
            return self.tree

        ssl_cert = SSLCert(name='ipi.crt', obj=self.ssl_cert)
        ssl_key = SSLKey(name='ipi.key', obj=self.ssl_key)
        self.folder.hook(ssl_cert, ssl_key)

        clientssl1 = ClientSsl('clientssl1')
        self.folder.hook(clientssl1)

        blacklist1 = IpIntelligenceFeedList('blacklist1')
        blacklist1.properties.feeds = combine(*[IpIntelligenceFeed('feed_%d' % x) for x in range(1000)])
        self.folder.hook(blacklist1)

        policy = IpIntelligencePolicy('policy')

        if not (v.product.is_bigip and v > 'bigip 11.6.2'):
            cat1 = {'/Common/proxy': {}}
        else:
            cat1 = {'/Common/additional':
                    {'match-direction-override': 'match-source'}
                    }

        policy.properties.blacklist_categories = cat1
        policy.properties.feed_lists = references(blacklist1)
        self.folder.hook(policy)

        return self.tree
