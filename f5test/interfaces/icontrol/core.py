from ..config import ConfigInterface, DeviceAccess
from .driver import Icontrol, ICONTROL_URL
from ...base import Interface
from ...defaults import ADMIN_USERNAME, ADMIN_PASSWORD, DEFAULT_PORTS
import logging

LOG = logging.getLogger(__name__)


class IcontrolInterface(Interface):

    def __init__(self, device=None, address=None, username=None, password=None,
                 port=None, proto='https', timeout=90, debug=False, *args, **kwargs):
        super(IcontrolInterface, self).__init__()

        self.device = device if isinstance(device, DeviceAccess) \
            else ConfigInterface().get_device(device)

        if self.device:
            assert self.device is not None
            if username is None:
                username = self.device.get_admin_creds().username
            if password is None:
                password = self.device.get_admin_creds().password
            if address is None:
                address = self.device.address
            if port is None:
                port = self.device.ports.get(proto)

        assert address is not None
        self.address = address
        self.username = username or ADMIN_USERNAME
        self.password = password or ADMIN_PASSWORD
        self.port = port or DEFAULT_PORTS[proto]
        self.proto = proto
        self.timeout = timeout
        self.debug = debug

    @property
    def version(self):
        from ...commands.icontrol.system import get_version
        return get_version(ifc=self)

    def set_session(self, session=None):
        v = self.version
        if v.product.is_bigip and v >= 'bigip 11.0' or \
           v.product.is_em and v >= 'em 3.0':
            if not session:
                session = self.api.System.Session.get_session_identifier()
            LOG.debug('iControl session: %s', session)
            self.api._session = session
        return session

    def clear_session(self):
        if self.api._session:
            LOG.debug('iControl session cleared.')
            self.api._session = None

    def get_session(self):
        return self.api._session

    def set_query_params(self, **query):
        LOG.debug('iControl query: %s', query)
        self.api._cache.clear()
        self.api._url_params = query

    def set_url(self, url=ICONTROL_URL):
        LOG.debug('iControl URL: %s', url)
        self.api._icontrol_url = url

    def open(self):  # @ReservedAssignment
        if self.api:
            return self.api
        address = self.address
        username = self.username
        password = self.password

        self.api = Icontrol(address, username, password, port=self.port,
                            timeout=self.timeout, proto=self.proto,
                            debug=self.debug)
        return self.api
