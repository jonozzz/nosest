'''
Created on Dec 8, 2017

@author: jono
'''
from ..config import ConfigInterface, DeviceAccess
from f5.bigip import ManagementRoot
from ...utils.version import Version
from ...base import Interface
from ...defaults import ADMIN_USERNAME, ADMIN_PASSWORD, DEFAULT_PORTS
import logging

LOG = logging.getLogger(__name__)


class IcontrolRestInterface(Interface):

    def __init__(self, device=None, address=None, username=None, password=None,
                 port=None, proto='https', timeout=90, debug=False, *args, **kwargs):
        super(IcontrolRestInterface, self).__init__()

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
        #self.api.tm.sys.software.volumes._meta_data['tmos_version'] = '99.99.99'
        self.api._meta_data['tmos_version'] = '99.99.99'
        active_volume = next(v for v in self.api.tm.sys.software.volumes.get_collection()
                             if v.attrs.get('active'))
        return Version("{0[product]} {0[version]}".format(active_volume.attrs))

    def open(self):  # @ReservedAssignment
        if self.api:
            return self.api
        address = self.address
        username = self.username
        password = self.password

        self.api = ManagementRoot(address, username, password,
                                  timeout=self.timeout, port=self.port,
                                  auth_provider='local')
        if self.version.product.is_bigiq:
            from f5.bigiq import ManagementRoot as BigiqManagementRoot
            self.api = BigiqManagementRoot(address, username, password,
                                           timeout=self.timeout, port=self.port,
                                           auth_provider='local')
        elif self.version.product.is_iworkflow:
            from f5.iworkflow import ManagementRoot as IwfManagementRoot
            self.api = IwfManagementRoot(address, username, password,
                                         timeout=self.timeout, port=self.port)
        return self.api
