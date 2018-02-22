"""
Implementation of Unified Device Discovery objects
/mgmt/cm/global/...
"""
from f5test.interfaces.rest.emapi.objects.base import Task
from f5test.interfaces.rest.emapi.objects.base import TaskError
from f5test.base import enum


class DeviceTrust(Task):
    URI = '/mgmt/cm/global/tasks/device-trust'
    ITEM_URI = URI + '/%s'
    UPDATE_STEP = 'PENDING_FRAMEWORK_UPGRADE_CONFIRMATION'


class DeviceDiscovery(Task):
    URI = '/mgmt/cm/global/tasks/device-discovery'
    ITEM_URI = URI + '/%s'
    SERVICES = ('access', 'adc_core', 'asm', 'firewall', 'security_shared', 'dns')


class DeviceRemoveMgmtAuthority(Task):
    URI = '/mgmt/cm/global/tasks/device-remove-mgmt-authority'
    ITEM_URI = URI + '/%s'


class DeviceRemoveTrust(Task):
    URI = '/mgmt/cm/global/tasks/device-remove-trust'
    ITEM_URI = URI + '/%s'


class BigipClusterMgmt(Task):
    URI = '/mgmt/cm/global/tasks/bigip-cluster-mgmt'
    ITEM_URI = URI + '/%s'


class EstablishTrustException(TaskError):
    def __init__(self, message, address):
        self.args = (message, address)
        self.message = message
        self.address = address


class AddServiceException(TaskError):
    def __init__(self, message, address, service):
        self.args = (message, address)
        self.message = message
        self.address = address
        self.service = service


class ImportServiceException(TaskError):
    def __init__(self, message, address, service):
        self.args = (message, address)
        self.message = message
        self.address = address
        self.service = service


class RemoveServiceException(TaskError):
    def __init__(self, message, address, service):
        self.args = (message, address)
        self.message = message
        self.address = address
        self.service = service


class RemoveTrustException(TaskError):
    def __init__(self, message, address):
        self.args = (message, address)
        self.message = message
        self.address = address
