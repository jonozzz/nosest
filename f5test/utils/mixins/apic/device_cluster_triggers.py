# from nose.plugins.skip import SkipTest
from nose.plugins.attrib import attr
import logging

LOG = logging.getLogger(__name__)


@attr(rank=101,
      author='wong',
      scenario='BasicTriggers',
      doc='',
)
class DeviceClusterTriggers(object):
    """
    This is like a healper class for trigger tests. All trigger tests
    can be run on any graph.

    To use this class:
        class Tests(InterfaceTestCase, DeviceClusterTriggers):
            ...
    """

#    @classmethod
#    def setup_class(cls):
#        super(Tests, cls).setup_class()

#    @classmethod
#    def teardown_class(cls):
#        try:
#            pass
#        #except Exception, e:
#        #    print e
#        finally:
#            super(Tests, cls).setup_class()

    @attr(duration=0)
#    @repeat(10)
    def test_100_ldevvip(self):
        """
        1) Delete Device Cluster
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back LDevVip
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting Device Cluster...")
        self.set_data('redeploy', False, overwrite=True)

    def test_102_dev_folder(self):
        """
        1) Delete 1 DevFolder
        2) ???
        3) ???
        4) Add back DevFolder
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting DevFolder...")
        self.set_data('redeploy', False, overwrite=True)

    def test_103_multiple_dev_folder(self):
        """
        1) Delete multiple DevFolders
        2) ???
        3) ???
        4) Add back multiple DevFolders
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting multiple DevFolder...")
        self.set_data('redeploy', False, overwrite=True)

    def test_104_rs_meta_if(self):
        """
        1) Delete Relation from a Logical Interface to an Interface Label
        2) ???
        3) ???
        4) Add back vnsRsMetaIf
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting vnsRsMetaIf...")
        self.set_data('redeploy', False, overwrite=True)

    def test_105_rs_cif_att(self):
        """
        1) Delete relation to a Set of Concrete Interfaces from the Device in
           the Cluster
        2) ???
        3) ???
        4) Add back vnsRsCIfAtt
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()

        LOG.info("Deleting vnsRsCIfAtt...")
        self.set_data('redeploy', False, overwrite=True)

    def test_106_cdev(self):
        """
        1) Delete Concrete Device
        2) ???
        3) ???
        4) Add back Concrete Device
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()

        LOG.info("Deleting vnsCDev...")
        self.set_data('redeploy', False, overwrite=True)
