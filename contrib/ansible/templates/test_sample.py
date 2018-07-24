import logging

LOG = logging.getLogger(__name__)


class Tests(object):
    """Describe what these tests have in common."""

    def test_hello_world_01(self, context):
        """A passing test."""
        LOG.info('Hello world.')
