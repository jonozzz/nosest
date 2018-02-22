import logging
from nose.plugins.attrib import attr
from f5test.noseplugins import repeat
from f5test.interfaces.testcase import InterfaceTestCase
import time

LOG = logging.getLogger(__name__)


@attr(rank=1,
      author='author@domain.com',
      scenario='RQ123',
      doc='link.to.documentation',
)
class Tests(InterfaceTestCase):
    """Describe what these tests have in common."""

    def test_hello_world_01(self):
        """A passing test."""
        cfgifc = self.get_config()
        cfgifc.get_all_devices()
        LOG.info('Hello world.')

    def test_fail(self):
        LOG.warn('About to fail...')
        self.fail('Done')

    def test_error(self):
        raise ValueError('error!')

    def test_known_issue(self):
        """A known issue test."""
        self.fail_ki('See BZ123456')

    def test_skip(self):
        """A test that skips all the time."""
        LOG.info('About to skip...')
        self.skipTest('No reason.')
