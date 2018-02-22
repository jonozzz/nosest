from nose.plugins.attrib import attr
import logging

LOG = logging.getLogger(__name__)


@attr(rank=101,
      author='wong',
      scenario='GraphTriggers',
      doc='',
)
class GraphTriggers(object):
    """
    This is like a healper class for trigger tests. All trigger tests
    can be run on any graph.

    To use this class:
        class Tests(InterfaceTestCase, GraphTriggers):
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
    def test_100_provider_node(self):
        """
        1) Delete Provider Terminal Node
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back vnsAbsTermNodeProv
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting Provider Terminal Node...")
        self.set_data('redeploy', False, overwrite=True)

    def test_101_consumer_node(self):
        """
        1) Delete Consumer Terminal Node
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Add back vnsAbsTermNodeCon
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting Consumer Terminal Node...")
        self.set_data('redeploy', False, overwrite=True)

    def test_102_rs_node_to_mfunc(self):
        """
        1) Delete Relation from an Function Node to Meta Function from the Package
        2) Wait until graphs deleted from BIG-IQ and BIG-IPs
        3) Verify faults
        4) Add back vnsRsNodeToMFunc
        """
        sshifc = self.get_ssh()
        cfgifc = self.get_config()
        emifc = self.get_em()

        LOG.info("Deleting vnsRsNodeToMFunc...")
        self.set_data('redeploy', False, overwrite=True)
