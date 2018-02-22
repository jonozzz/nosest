import atexit
import logging
from pyVim import connect
from pyVmomi import vim, vmodl

LOG = logging.getLogger(__name__)


class vCenterCommandFail(Exception):
    pass


class vCenter(object):
    """ vCenter Tool

    input args: host - vCenter IP
                user - vCenter login user
                pwd  - vCenter login password
    """

    def __init__(self, host, user, pwd, port=443):
        # No need to use ssl CERT
        self.host = host
        self.user = user
        self.pwd = pwd
        self.port = port
        self._login()

    def _login(self):
        connect.ssl.CERT_REQUIRED = False
        self.si = connect.SmartConnect(host=self.host, user=self.user, pwd=self.pwd, port=self.port)
        self.content = self.si.content
        atexit.register(connect.Disconnect, self.si)

    def _get_obj(self, vimtype, name, dvs_name=None):
        '''
        This function will look for the name of a given object type. If the
        object name is found, the object will be returned.

        @param vimtype: list of vim object types.
        @type vimtype: a vim type

        @param name: name of the object
        @type name: string
        '''
        container = self.content.viewManager.CreateContainerView(self.content.
                                                                 rootFolder,
                                                                 vimtype, True)
        for cont in container.view:
            if not dvs_name and cont.name == name:
                return cont
            elif dvs_name and cont.name == name and cont.config.distributedVirtualSwitch.name == dvs_name:
                return cont

    def _get_vm(self, vm_name):
        return self._get_obj([vim.VirtualMachine], vm_name)

    def _get_nic(self, vm_name, nic_name):
        vm = self._get_obj([vim.VirtualMachine], vm_name)
        for dev in vm.config.hardware.device:
            if dev.deviceInfo.label == nic_name:
                return dev
        raise vCenterCommandFail("Failed to find nic '%s' from %s" % (nic_name, vm_name))

    def _assign_nic(self, vm_name, nic_name, network_name, dvs_name):
        nic = self._get_nic(vm_name, nic_name)
        vm = self._get_obj([vim.VirtualMachine], vm_name)

        nicspec = vim.vm.device.VirtualDeviceSpec()
        nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        nicspec.device = nic

        net = self._get_obj([vim.dvs.DistributedVirtualPortgroup], network_name, dvs_name=dvs_name)
        # If this is a DVS Port Group
        if net:
            LOG.info("This is a dvs port group network")
            port_connection = vim.dvs.PortConnection()
            port_connection.portgroupKey = net.key
            port_connection.switchUuid = net.config.distributedVirtualSwitch.uuid

            nicspec.device.backing = vim.vm.device.VirtualEthernetCard.\
                DistributedVirtualPortBackingInfo()
            nicspec.device.backing.port = port_connection

        # Assume it is a standard network
        else:
            LOG.info("Assuming this is a standard network")
            nicspec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
            nicspec.device.backing.network = self._get_obj([vim.Network], network_name)
            nicspec.device.backing.deviceName = network_name
            nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
            nicspec.device.connectable.startConnected = True
            nicspec.device.connectable.allowGuestControl = True

        vmconf = vim.vm.ConfigSpec(deviceChange=[nicspec])
        task = vm.ReconfigVM_Task(vmconf)
        self._wait_for_tasks(self.si, [task])
        LOG.info("Successfully assigned vm '%s' VNic '%s' to network '%s'"
                 % (vm_name, nic_name, network_name))

    def assign_nic(self, vm_name, nic_name, network_name, dvs_name=None):
        try:
            self._assign_nic(vm_name, nic_name, network_name, dvs_name)
        except:
            LOG.info('Failure: log on then retry')
            self._login()
            self._assign_nic(vm_name, nic_name, network_name, dvs_name)

    """
    Written by Michael Rice <michael@michaelrice.org>
    Github: https://github.com/michaelrice
    Website: https://michaelrice.github.io/
    Blog: http://www.errr-online.com/
    This code has been released under the terms of the Apache 2 licenses
    http://www.apache.org/licenses/LICENSE-2.0.html
    Helper module for task operations.
    """
    def _wait_for_tasks(self, service_instance, tasks):
        """Given the service instance si and tasks, it returns after all the
        tasks are complete
        """
        property_collector = service_instance.content.propertyCollector
        task_list = [str(task) for task in tasks]
        # Create filter
        obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                     for task in tasks]
        property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                                   pathSet=[],
                                                                   all=True)
        filter_spec = vmodl.query.PropertyCollector.FilterSpec()
        filter_spec.objectSet = obj_specs
        filter_spec.propSet = [property_spec]
        pcfilter = property_collector.CreateFilter(filter_spec, True)
        try:
            version, state = None, None
            # Loop looking for updates till the state moves to a completed state.
            while len(task_list):
                update = property_collector.WaitForUpdates(version)
                for filter_set in update.filterSet:
                    for obj_set in filter_set.objectSet:
                        task = obj_set.obj
                        for change in obj_set.changeSet:
                            if change.name == 'info':
                                state = change.val.state
                            elif change.name == 'info.state':
                                state = change.val
                            else:
                                continue

                            if not str(task) in task_list:
                                continue

                            if state == vim.TaskInfo.State.success:
                                # Remove task from taskList
                                task_list.remove(str(task))
                            elif state == vim.TaskInfo.State.error:
                                raise task.info.error
                # Move to next version
                version = update.version
        finally:
            if pcfilter:
                pcfilter.Destroy()
