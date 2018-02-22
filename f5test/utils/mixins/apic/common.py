from f5test.interfaces.ssh import SSHInterface
from f5test.interfaces.rest.apic.objects.tenant import Tenant
from f5test.interfaces.rest.apic.objects.system import ManagedObject
from f5test.interfaces.rest.emapi.objects.bigip import Folders
from f5test.utils.wait import wait, wait_args
from f5test.interfaces.rest.emapi.objects.bigip import DeviceGroup
import f5test.commands.apic as ACMD
import f5test.defaults as F5D
import f5test.commands.shell as SCMD
import logging

LOG = logging.getLogger(__name__)
PING = "ping %s -c 10"
PING_ERROR = "100% packet loss"
TRAFFIC = "ab -n 10 http://%s/"
# TRAFFIC = "curl http://%s"
TRAFFIC_ATTEMPTS = 10


class ApicTestcase(object):
    """
    Common used functions that apply to any APIC test.
    """

    @staticmethod
    def set_web_pg(config, vcenter, pg_name, dvs_name=None, options=None):
        LOG.info("Setting Web PGs to Client VMs...")
        clients = config.get_devices(kind=F5D.KIND_CLOUD_VCENTER_CLIENT)
        for client in clients:
            vcenter.assign_nic(client.address, client.specs.nic2.name,
                               pg_name, dvs_name=dvs_name)

    @staticmethod
    def set_app_pg(config, vcenter, pg_name, dvs_name=None, options=None):
        LOG.info("Setting App PGs to Server VMs...")
        servers = config.get_devices(kind=F5D.KIND_CLOUD_VCENTER_SERVER)
        for server in servers:
            vcenter.assign_nic(server.address, server.specs.nic2.name,
                               pg_name, dvs_name=dvs_name)

    def traffic(self, ip):
        # generate traffic via Apache Bench
        LOG.info("Generating traffic via ab...")
        clients = self.get_config().get_devices(kind=F5D.KIND_CLOUD_VCENTER_CLIENT)
        for client in clients:
            with SSHInterface(device=client) as sshifc:

                wait_args(SCMD.ssh.generic, func_args=[PING % ip, sshifc],
                          condition=lambda x: PING_ERROR not in x.stdout,
                          progress_cb=lambda _: "Waiting until %s is ping-able" % ip,
                          timeout=30)

                for i in range(TRAFFIC_ATTEMPTS):
                    try:
                        resp = SCMD.ssh.generic(TRAFFIC % ip, ifc=sshifc)
                        self.assertFalse(resp.stderr, "Failed to generate traffic:\n %s" % resp)
                        break
                    except:
                        if i >= TRAFFIC_ATTEMPTS - 1:
                            raise

    def trigger_recover_graphs(self, trigger_xmls, apicifc):
        for graph, ldevvip in trigger_xmls:
            LOG.info("Recovering device cluster...")
            substrs = ldevvip.get('dn').split('/')
            for substr in substrs:
                if 'tn-' in substr:
                    ldevvip_tenant = "uni/{}".format(substr)

            self.apicifc.api.post(ManagedObject.URI % ldevvip.get('dn'), payload=ldevvip)
            ldevvip.wait(ifc=apicifc, tenant=ldevvip_tenant)

            LOG.info("Recovering graph...")
            self.apicifc.api.post(ManagedObject.URI % graph.get('dn'), payload=graph)

            LOG.info("Waiting until Graph is deployed")
            graph.wait_graph(self.apicifc, graph.get('name'))

    def complete_recover_graphs(self, original_xmls, apicifc, bigips):
        '''
        Delete all graphs and Device Clusters
        Create Device Cluster and Graphs
        '''
        try:
            LOG.info("Deleting graphs and device clusters...")
            for graph, ldevvip in reversed(original_xmls):
                vdev = ACMD.system.get_vdev(Tenant.TENANT_DN % graph.get('name'),
                                            ifc=self.apicifc)
                self.apicifc.api.delete(ManagedObject.URI % graph.get('dn'))

                if vdev is not None:
                    partition_number = vdev.get('id')
                    ctx_name = vdev.get('ctxName')
                    tenant_name = graph.get('name')
                    ip_partition_name = "apic-{0}-{1}-{2}".format(tenant_name,
                                                                  ctx_name,
                                                                  partition_number)

                    LOG.info("Waiting until partition is removed from BIG-IPs:"
                             " %s" % ip_partition_name)
                    for bigip in self.get_data('devices'):
                        r = self.get_icontrol_rest(device=bigip).api
                        wait_args(r.get, func_args=[Folders.URI],
                                  condition=lambda x: ip_partition_name not in [item.name for item in x['items']],
                                  progress_cb=lambda x: "{0}".format([item.name for item in x['items']]))

                if ldevvip is not None:
                    self.apicifc.api.delete(ManagedObject.URI % ldevvip.get('dn'))
                    ldevvip_name = ldevvip.get('name')
                    LOG.info("Waiting until Device Group gets removed from BIG-IPs: "
                             "{0}".format(ldevvip_name))

                    for bigip in bigips:
                        rstifc = self.get_icontrol_rest(device=bigip)
                        wait(lambda: rstifc.api.get(DeviceGroup.URI),
                             condition=lambda x: ldevvip_name not in [y.name for y in x['items']],
                             progress_cb=lambda x: "Device Groups: {0}".format([y.name for y in x['items']]),
                             stabilize=5)

            LOG.info("Re-deploying graphs...")
            for graph, ldevvip in original_xmls:
                if ldevvip is not None:
                    substrs = ldevvip.get('dn').split('/')
                    for substr in substrs:
                        if 'tn-' in substr:
                            ldevvip_tenant = "uni/{}".format(substr)

                    self.apicifc.api.post(ManagedObject.URI % ldevvip.get('dn'), payload=ldevvip)
                    ldevvip.wait(ifc=apicifc, tenant=ldevvip_tenant)

                self.apicifc.api.post(ManagedObject.URI % graph.get('dn'), payload=graph)
                graph.wait_graph(self.apicifc, graph.get('name'))
        except:
            raise
