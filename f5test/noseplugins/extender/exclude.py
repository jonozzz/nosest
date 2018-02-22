'''
Created on Sep 1, 2015

@author: jono
'''
import logging
from . import ExtendedPlugin
from nose.plugins.skip import SkipTest

LOG = logging.getLogger(__name__)


class Exclude(ExtendedPlugin):
    """
    Exclude tests from running based on test's address.

    Piggyback nose's -e (--exclude=REGEX) option.

    Example:
        nosetests -e test_file1.Tests -e test_file2.Tests.test_07

    """
    enabled = True

    def configure(self, options, noseconfig):
        super(Exclude, self).configure(options, noseconfig)
        from ...interfaces.testcase import ContextHelper
        self.context = ContextHelper(self.name)
        self.exclude = noseconfig.exclude

    def beforeTest(self, test):
        if self.exclude and any([exc.search(test.id()) for exc in self.exclude]):
            raise SkipTest
