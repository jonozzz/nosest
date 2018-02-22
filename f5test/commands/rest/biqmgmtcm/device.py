'''
Created on Apr 5, 2016
This module is the implementation of the DSC Cluster functions for bigiq-mgmt-cm Greenflash v5.0.0+
@author: elarson
'''

import logging
from f5test.commands.rest.base import IcontrolRestCommand
from f5test.interfaces.rest.emapi.objects.base import CmTask
from f5test.interfaces.rest.emapi.objects.biqmgmtcm.device import (DscGroupTask,
                                                                   DiscoverDscClustersException)
from f5test.interfaces.rest.emapi.objects.shared import DeviceResolver
from f5test.utils.wait import wait_args

LOG = logging.getLogger(__name__)

DSC_DISCOVER_TIMEOUT = 300

CM_DEVICE_GROUP = 'cm-bigip-allBigIpDevices'

discover_dsc_clusters = None
class DiscoverDscClusters(IcontrolRestCommand):  # @IgnorePep8
    """
    Perform discovery of DSC clusters on a list of BIG-IPs
    @return final response from task worker
    """
    def __init__(self, *args, **kwargs):
        super(DiscoverDscClusters, self).__init__(*args, **kwargs)

    def set_uri(self, item):
        self.uri = DscGroupTask.ITEM_URI % item.id

    def setup(self):
        LOG.info("Preparing to Discover DSC Clusters")
        payload = DscGroupTask()

        resp = self.api.post(DscGroupTask.URI, payload)
        self.set_uri(resp)
        resp = wait_args(self.api.get, func_args=[self.uri],
                         condition=lambda x: x.status in CmTask.FINAL_STATUSES,
                         interval=10,
                         timeout=DSC_DISCOVER_TIMEOUT,
                         timeout_message='DSC Cluster Discovery did not complete in {0} seconds')
        if resp.status == CmTask.FAIL_STATE:
            raise DiscoverDscClustersException("DSC Cluster Discovery failed with state {0}".format(resp.status))

        return resp
