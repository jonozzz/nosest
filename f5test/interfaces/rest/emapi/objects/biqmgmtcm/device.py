"""
Objects for endpoints in the bigiq-mgmt-cm branch cm/Device
"""
from f5test.interfaces.rest.emapi.objects.base import (Reference,
                                                       ReferenceList,
                                                       Task,
                                                       TaskError)


class RefreshCurrentConfig(Task):
    """
    Retrieves devices (peers), device groups, certificates, and traffic groups
    for the devices DSC config
    """
    URI = '/mgmt/cm/device/dsc/refresh-current-config'

    def __init__(self, *args, **kwargs):
        super(RefreshCurrentConfig, self).__init__(*args, **kwargs)
        self.setdefault('configPaths', [])
        self.setdefault('deviceReference', Reference())


class DscGroup(Task):
    """ Perform GET to refresh dsc clusters """
    URI = '/mgmt/cm/device/dsc-group'
    ITEM_URI = URI + '/%s'


class DscGroupTask(Task):
    """
    default refresh of all managed BGI-IP devices
    add "deviceReference": [{"link": "<device group ref for BIG-IP>"}] for item refresh
    NOTE: deviceReference must be from cm-bigip-allBigipDevices collection
    """
    URI = '/mgmt/cm/device/dsc-group-task'
    ITEM_URI = URI + '/%s'

    def __init__(self, *args, **kwargs):
        super(DscGroupTask, self).__init__(*args, **kwargs)
        self.setdefault('name', 'UI refresh request')
        self.setdefault('deviceReferences', ReferenceList())


class DiscoverDscClustersException(TaskError):
    def __init__(self, message):
        self.args = (message,)
        self.message = message


class DeviceUpgradesTask(Task):
    URI = '/mgmt/cm/device/upgrades'
    ITEM_URI = '/mgmt/cm/device/upgrades/%s'

    def __init__(self, *args, **kwargs):
        super(DeviceUpgradesTask, self).__init__(*args, **kwargs)
        self.setdefault('deviceInput', [])
        self.setdefault('name', '')
        self.setdefault('softwareImageReference', Reference())
        self.setdefault('stopBeforeInstall', True)
        self.setdefault('stopBeforeReboot', True)
