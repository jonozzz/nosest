'''
Created on Jun 16, 2015

@author: wong
'''
from .base import ApicRestCommand
from ...base import AttrDict
from ...interfaces.rest.apic.objects.system import DevicePackage, VDev, ManagedObject
from f5test.interfaces.rest.apic.objects.base import TaskError
from f5test.base import Options
import logging
from f5test.utils.wait import wait_args

LOG = logging.getLogger(__name__)
DEFAULT_DP_PATH = '/build/platform/cisco-apic/daily/current/F5DevicePackage.zip'


upload_dp = None
class UploadDp(ApicRestCommand):  # @IgnorePep8
    """Upload Device Package (DP)

    This function will return the XML data for only the new device package
    that has been uploaded. This data will be useful when we go to delete
    the device package during cleanup.

    @param path: path
    @type name: string

    @param f: the file to upload
    @type f: needs to be file object or file-like object like SFTPFile

    @return: Return vsnMDev ElementTree after POST.
    @rtype: ElementTree
    """
    def __init__(self, path=None, f=None, *args, **kwargs):
        super(UploadDp, self).__init__(*args, **kwargs)
        self.path = path or DEFAULT_DP_PATH
        self.f = f

    def prep(self):
        self.element_tree_state = self.ifc.api.element_tree
        if not self.element_tree_state:
            self.ifc.api.element_tree = True

    def setup(self):
        """Uploads DP."""

        # Populate device packages in APIC.
        resp = self.ifc.api.get(DevicePackage.URI)
        pre_dns = [x.get('dn') for x in resp]

        headers = {'Content-Type': 'multipart/form-data'}
        payload = AttrDict()

        LOG.debug("Uploading...")
        if self.f:
            # The file object needs to have the 'name' attr for the POST to
            # work. SFTPFile Object does not have the 'name' attr.
            if not hasattr(self.f, 'name'):
                setattr(self.f, 'name', 'foo')
            payload.name = self.f
            self.ifc.api.post(DevicePackage.UPLOAD_URI, headers=headers,
                              payload=payload)

        else:
            with open(self.path, "r") as f:
                payload.name = f
                self.ifc.api.post(DevicePackage.UPLOAD_URI, headers=headers,
                                  payload=payload)

        post_dp = wait_args(self.ifc.api.get, func_args=[DevicePackage.URI],
                            condition=lambda x: len(x) > len(pre_dns),
                            progress_cb=lambda x: "items: %s" % len(x))

        for item in post_dp:
            if item.get('dn') not in pre_dns:
                return item

        return post_dp

    def cleanup(self):
        if not self.element_tree_state:
            self.ifc.api.element_tree = self.element_tree_state

delete_dp = None
class DeleteDp(ApicRestCommand):  # @IgnorePep8
    """Delete Device Package (DP)

    @param vns_mdev: vnsMDev response #mandatory
    @type vnsMDev: dict

    @param options: options to pass in here. So far only 'all' is be used. If
                    this is set, it will delete all device packages in APIC.
    @type options: dict

    @return: POST response of delete
    @rtype: Element
    """
    def __init__(self, vns_mdev, options=None, *args, **kwargs):
        super(DeleteDp, self).__init__(*args, **kwargs)
        self.vns_mdev = vns_mdev
        options = Options(options)
        self.all = options.all

    def prep(self):
        self.element_tree_state = self.ifc.api.element_tree
        if not self.element_tree_state:
            self.ifc.api.element_tree = True

    def setup(self):
        """Deletes DP."""

        if self.all:
            resp = self.ifc.api.get(DevicePackage.URI)

            for mdev in resp:
                dn = mdev.get('dn')
                LOG.info("Delete Device Package: %s" % dn)
                self.ifc.api.delete(ManagedObject.URI % dn)
            return

        dn = self.vns_mdev.get('dn')
        return self.ifc.api.delete(ManagedObject.URI % dn)

    def cleanup(self):
        if not self.element_tree_state:
            self.ifc.api.element_tree = self.element_tree_state

get_vdev = None
class GetVdev(ApicRestCommand):  # @IgnorePep8
    """Get partition number

    @param t_dn: t_dn of tenant. t_dn = "uni/tn-tenant"
    @type vnsMDev: str

    @return: Element of matching t_dn
    @rtype: Element
    """
    def __init__(self, t_dn, *args, **kwargs):
        super(GetVdev, self).__init__(*args, **kwargs)
        self.t_dn = t_dn.strip()
        self.t_dn = t_dn.strip('/')

    def setup(self):
        """Find and return partition number"""

        resp = self.ifc.api.get(VDev.URI)

        for item in resp:
            if item.get('tnDn') == self.t_dn:
                return item
