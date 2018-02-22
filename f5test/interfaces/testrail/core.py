'''
Created on Apr 20, 2017

@author: jono
'''
from ...base import Interface
from .driver import APIClient, APIError, TestRail
import logging
from ...base import AttrDict

LOG = logging.getLogger(__name__)


class TestRailInterface(Interface):
    """Boilerplate code.
    """
    def __init__(self, url=None, username=None, password=None, timeout=90,
                 debug=False, *args, **kwargs):
        super(TestRailInterface, self).__init__()

        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout
        self.debug = debug

    def __repr__(self):
        name = self.__class__.__name__
        return "<{0}: {1.username}:{1.password}@{1.url}>".format(name, self)

    def open(self):  # @ReservedAssignment
        """Returns the handle to a TestRail API client.

        @return: the selenium remote client object.
        @rtype: L{RemoteWrapper}
        """
        if self.api:
            return self.api

        client = APIClient(self.url, self.debug)
        client.user = self.username
        client.password = self.password
        self.api = TestRail(client)

        return self.api

#     def close(self, *args, **kwargs):
#         if self.api:
#             self.api.quit()
#         super(TestRailInterface, self).close()
