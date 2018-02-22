from nose.plugins.attrib import attr
import logging

LOG = logging.getLogger(__name__)


@attr(rank=101,
      author='wong',
      scenario='BasicTriggers',
      doc='',
)
class ContractTriggers(object):
    """
    This is like a healper class for trigger tests. All trigger tests
    can be run on any graph.

    To use this class:
        class Tests(InterfaceTestCase, ContractTriggers):
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
    def test_100_contract(self):
        """
        1) Delete Contract
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back vzBrCP
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting vzBrCP...")
        self.set_data('redeploy', False, overwrite=True)

    def test_102_dev_folder(self):
        """
        1) Delete L4-L7 Service Graph Template
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back vzRsSubjGraphAtt
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting vzRsSubjGraphAtt...")
        self.set_data('redeploy', False, overwrite=True)

    def test_103_filter(self):
        """
        1) Delete filter
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back vzFilter
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()

        LOG.info("Deleting multiple vzFilter...")
        self.set_data('redeploy', False, overwrite=True)
