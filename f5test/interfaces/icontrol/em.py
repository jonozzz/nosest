'''
An EMPython port as an interface.

Created on Apr 21, 2011

@author: jono
'''
from ...base import Interface
from ...defaults import ADMIN_USERNAME, ADMIN_PASSWORD, DEFAULT_PORTS
from ..config import ConfigInterface, DeviceAccess
from .core import IcontrolInterface


class EmApi(object):

    def __init__(self, icontrol):
        self.icontrol = icontrol

    @property
    def device(self):
        from .empython.api.DeviceAPI import DeviceAPI
        return DeviceAPI(self.icontrol)

    @property
    def discovery(self):
        from .empython.api.DiscoveryAPI import DiscoveryAPI
        return DiscoveryAPI(self.icontrol)

    @property
    def file(self):  # @ReservedAssignment
        from .empython.api.FileAPI import FileAPI
        return FileAPI(self.icontrol)

    @property
    def legacy_software_install(self):
        from .empython.api.LegacySoftwareInstallAPI import LegacySoftwareInstallAPI
        return LegacySoftwareInstallAPI(self.icontrol)

    @property
    def software_install(self):
        from .empython.api.SoftwareInstallAPI import SoftwareInstallAPI
        return SoftwareInstallAPI(self.icontrol)

    @property
    def enabledisable(self):
        from .empython.api.EnableDisableAPI import EnableDisableAPI
        return EnableDisableAPI(self.icontrol)

    @property
    def big3d_install(self):
        from .empython.api.Big3dInstallAPI import Big3dInstallAPI
        return Big3dInstallAPI(self.icontrol)

    @property
    def stats(self):
        from .empython.api.StatsAPI import StatsAPI
        return StatsAPI(self.icontrol)

    def get_by_name(self, name):
        module = __import__('empython.api.' + name, globals(), locals(),
                            [name], 1)
        return module.__dict__[name](self.icontrol)


class EMInterface(Interface):

    def __init__(self, device=None, icifc=None, address=None, username=None,
                 password=None, port=None, proto='https', timeout=180,
                 *args, **kwargs):
        super(EMInterface, self).__init__()

        self.icifc = icifc
        self.device = device if isinstance(device, DeviceAccess) \
            else ConfigInterface().get_device(device)

        if self.device:
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

    @property
    def version(self):
        from ...commands.icontrol.system import get_version
        return get_version(ifc=self.icifc)

    def open(self):  # @ReservedAssignment
        if self.api:
            return self.api

        if not self.icifc:
            self.icifc = IcontrolInterface(address=self.address,
                                           username=self.username,
                                           password=self.password,
                                           port=self.port,
                                           proto=self.proto,
                                           timeout=self.timeout,
                                           debug=False)
            self.icifc.open()
        self.api = EmApi(self.icifc.api)
        return self.api
