from nose.plugins.attrib import attr
from f5test.interfaces.rest.apic.objects.system import ManagedObject
from f5test.interfaces.rest.apic.objects.tenant import Tenant
from f5test.interfaces.rest.emapi.objects.bigip import Folders
from f5test.utils.wait import wait_args
import f5test.commands.apic as ACMD
import logging

LOG = logging.getLogger(__name__)


@attr(rank=101,
      author='wong',
      scenario='BasicTriggers',
      doc='',
)
class BasicTriggers(object):
    """
    This is like a healper class for trigger tests. All trigger tests
    can be run on any graph.

    To use this class:
        class Tests(InterfaceTestCase, BasicTriggers):
            ...
    """

    @attr(duration=0)
#    @repeat(10)
    def test_100_tenant(self):
        """
        1) Delete Tenant
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back fvTenant
        """
        apicifc = self.get_data('apicifc')
        trigger_xmls = self.get_data('trigger_xmls')

        for graph, _ in trigger_xmls:
            # Get partition name on BIG-IP for this tenant
            tenant_name = graph.get('name')
            vdev = ACMD.system.get_vdev(Tenant.TENANT_DN % tenant_name,
                                        ifc=apicifc)
            partition_number = vdev.get('id')
            ctx_name = vdev.get('ctxName')
            ip_partition_name = "apic-{0}-{1}-{2}".format(tenant_name,
                                                          ctx_name,
                                                          partition_number)

            LOG.info("Deleting fvTenant: {}".format(tenant_name))
            apicifc.api.delete(Tenant.URI % tenant_name)
            self.set_data('trigger', True, overwrite=True)

            LOG.info("Waiting until partition is removed from BIG-IPs:"
                     " %s" % ip_partition_name)
            for bigip in self.get_data('devices'):
                r = self.get_icontrol_rest(device=bigip).api
                wait_args(r.get, func_args=[Folders.URI],
                          condition=lambda x: ip_partition_name not in [item.name for item in x['items']],
                          progress_cb=lambda x: "{0}".format([item.name for item in x['items']]))

        self.set_data('redeploy', False, overwrite=True)

    def test_101_provider(self):
        """
        1) Delete 1 provider EPG
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Verify faults
        4) Add back provider EPG
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting provider EPG...")
        self.set_data('redeploy', False, overwrite=True)

    def test_102_consumer(self):
        """
        1) Delete 1 consumer EPG
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Verify faults
        4) Add back consumer EPG
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting consumer EPG...")
        self.set_data('redeploy', False, overwrite=True)

    def test_103_provider_consumer(self):
        """
        1) Delete 1 provider and consumer EPG
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Verify faults
        4) Add back provider and consumer EPG
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting provider and consumer EPG...")
        self.set_data('redeploy', False, overwrite=True)

    def test_104_bridge_domain(self):
        """
        1) Delete 1 bridge domain
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Verify faults
        4) Add back fvBD
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting fvBD...")
        self.set_data('redeploy', False, overwrite=True)
