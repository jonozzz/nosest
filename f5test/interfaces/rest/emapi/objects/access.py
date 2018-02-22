'''
Created on Apr 14, 2015

@author: ivanitskiy
'''

from .....utils.wait import wait
from .base import Reference, Task, TaskError, DEFAULT_TIMEOUT
from f5test.base import AttrDict


class AccessTask(Task):

    def wait(self, rest, resource, loop=None, timeout=DEFAULT_TIMEOUT, interval=1,
             timeout_message=None):
        def get_status():
            resp = rest.api.get(resource.selfLink)
            return resp
        if loop is None:
            loop = get_status
        if rest.version < "bigiq 5.0.0":
            raise TaskError("Task failed: Access supported since bigiq 5.0.0")

        ret = wait(loop, timeout=timeout, interval=interval,
                   timeout_message=timeout_message,
                   condition=lambda x: x.status not in Task.PENDING_STATUSES,
                   progress_cb=lambda x: 'Status: {0}'.format(x.status))
        assert ret.status in Task.FINAL_STATUSES, "{0.status}:{0.error}".format(ret)

        if ret.status == Task.FAIL_STATE:
            Task.fail('Task failed', ret)

        return ret


class DeletingAccessGroupTask(AccessTask):
    URI = '/mgmt/cm/access/tasks/mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(DeletingAccessGroupTask, self).__init__(*args, **kwargs)
        self.setdefault("actionType", "RMA_ACCESS_GROUP")
        self.setdefault("groupName")


class RemoveGroupAccessGroupTask(AccessTask):
    URI = '/mgmt/cm/access/tasks/remove-group-mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(RemoveGroupAccessGroupTask, self).__init__(*args, **kwargs)
        access_group_reference = AttrDict()
        access_group_reference.setdefault("link")
        self.setdefault("deviceGroupReference", access_group_reference)


class AccessDMADeviceReference(AttrDict):
    """That Object with two properties is used for mgmt-authority
     - 'deviceReference' is a RestReference to the source or nonSource device
     - 'skipConfigDiscovery' is a Boolean to indicate skip config discovery"""
    def __init__(self, *args, **kwargs):
        self.setdefault("clusterName", None)
        self.setdefault("skipConfigDiscovery", False)
        link = AttrDict()
        link.setdefault("link", None)
        self.setdefault("deviceReference", link)


class AddDeviceClusterTask(AccessTask):
    """Add device to cluster
    Request includes
    1) clusterName
    2) deviceReference - RestReference to the device: /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx
    3) useBigiqSync
    """
    URI = '/mgmt/cm/global/tasks/bigip-cluster-mgmt'

    def __init__(self, *args, **kwargs):
        super(AddDeviceClusterTask, self).__init__(*args, **kwargs)
        self.setdefault("clusterName")
        self.setdefault("deviceReference", AccessDMADeviceReference())
        self.setdefault("useBigiqSync", False)


class CreateAccessGroupTask(AccessTask):
    """Create a new Access Group. Source DevicesReference is required.
    Request includes
    1) groupName
    2) actionType - Type of action to do
    3) sourceDeviceReference - RestReference to the source device: /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx
    4) non Source Device References - RestReference to the nonSourceDeviceReferences: List of devices:  /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx
    """
    URI = '/mgmt/cm/access/tasks/mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(CreateAccessGroupTask, self).__init__(*args, **kwargs)
        self.setdefault("actionType", "CREATE_ACCESS_GROUP")
        self.setdefault("groupName")
        self.setdefault("sourceDevice", AccessDMADeviceReference())
        self.setdefault("nonSourceDevices", [])  # list of AccessDMADeviceReference


class EditingDevicesInAccessGroupTask(AccessTask):
    """Edit existing Access Group
    Request includes
    1) groupName - name of access group to be edited
    2) actionType = EDIT_ACCESS_GROUP  Type of action to do
    3) rmaNonSourceDeviceReferences - RestReference to delete devices in the group (List of devices:  /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx)
    4) nonSourceDeviceReferences - RestReference to the nonSourceDeviceReferences to be added (List of devices:  /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx)
    """
    URI = '/mgmt/cm/access/tasks/mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(EditingDevicesInAccessGroupTask, self).__init__(*args, **kwargs)
        self.setdefault("actionType", "EDIT_ACCESS_GROUP")
        self.setdefault("groupName")
        self.setdefault("rmaNonSourceDeviceReferences", [Reference()])
        self.setdefault("nonSourceDevices", [])


class ReimportSourceDeviceInAccessGroupTask(AccessTask):
    """ Re-import Source DEvice in Access Group
    Request includes
    1) groupName
    2) actionType - Type of action to do. In this case its re-import
    3) sourceDeviceReference - RestReference of the source device to do the re-import.
    """
    URI = '/mgmt/cm/access/tasks/mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(ReimportSourceDeviceInAccessGroupTask, self).__init__(*args, **kwargs)
        self.setdefault("actionType", "REIMPORT_SOURCE_DEVICE")
        self.setdefault("groupName")
        self.setdefault("sourceDevice", AccessDMADeviceReference())


class ChangeSourceDeviceInAccessGroupTask(AccessTask):
    """
    Request includes
    1) groupName
    2) actionType - Type of action to do. In this case its change source
    3) sourceDeviceReference - RestReference of the new source device source device to do the re-import.
    """
    URI = '/mgmt/cm/access/tasks/mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(ChangeSourceDeviceInAccessGroupTask, self).__init__(*args, **kwargs)
        self.setdefault("actionType", "CHANGE_SOURCE_DEVICE")
        self.setdefault("groupName")
        self.setdefault("sourceDevice", AccessDMADeviceReference())


class DeployConfigurationTask(AccessTask):
    """
    If skipDistribution is false it deploys the configuration to devices.
    if skipDistribution is true, it only evaluates the configuration.
    """
    URI = '/mgmt/cm/access/tasks/deploy-configuration'

    def __init__(self, *args, **kwargs):
        super(DeployConfigurationTask, self).__init__(*args, **kwargs)
        self.setdefault("name", "Deploy-sample-task")
        self.setdefault("description", "Deploy sample task description")
        self.setdefault('deviceGroupReference', Reference())
        self.setdefault("deviceReferences", [])


class AccessGroupTask(AccessTask):
    """Create a new Access Group. Add device to Access group. Re import device in Access group.
    DevicesReference is required.
    Request includes
    1) properties -
        cm:access:import-shared - True/False
        cm:access:access-group-name - String
    2) snapshotWorkingConfig - True/False
    3) deviceReference - RestReference to the device:
        /mgmt/shared/resolver/device-groups/cm-access-allBigIpDevices/devices/xxx
    """
    URI = '/mgmt/cm/access/tasks/declare-mgmt-authority'

    def __init__(self, *args, **kwargs):
        super(AccessGroupTask, self).__init__(*args, **kwargs)
        properties = AttrDict()
        properties.setdefault("cm:access:import-shared", True)
        properties.setdefault("cm:access:access-group-name")
        self.setdefault("properties", properties)
        link = AttrDict()
        link.setdefault("link", None)
        self.setdefault("deviceReference", link)
        self.setdefault("snapshotWorkingConfig", False)
        self.setdefault("clusterName", None)
