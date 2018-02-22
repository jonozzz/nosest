'''
Created on Feburary 9, 2016
@author: jwong

'''
from .base import Vns, TaskError
from .....utils.wait import wait_args
import xml.etree.ElementTree as ET


class LDevVip(ET.Element):
    URI = '/api/node/class/vnsLDevVip'
    PENDING_STATES = ('init', 'validaterequested', 'validatepending',
                      'auditrequested', 'auditpending', "modifypending")
    DONE = 'stable'

    def __init__(self, name, *args, **kwargs):
        super(LDevVip, self).__init__('vnsLDevVip', *args, **kwargs)
        self.set('name', name)

    @staticmethod
    def wait(ifc, tenant, *args, **kwargs):
        """
        We will need to wait on 2 spots: vnsLDevOperInfo and vnsCDevState.
        """

        def done(resp):
            ret = set()
            items = [x for x in resp if tenant in x.get('dn')]
            for item in items:
                ret.add(item.get('devState') not in LDevVip.PENDING_STATES)
            return all(ret) and ret

        resp = wait_args(ifc.api.get, func_args=[Vns.URI % 'vnsLDevOperInfo'],
                         condition=done,
                         progress_cb=lambda ret: "devState: {0}".format([x.get('devState') for x in ret]),
                         *args, **kwargs)

        # Cisco APIC bug where the status will go into a failed state for about
        # a second then into a stable state.
        for item in resp:
            if item.get('devState') != LDevVip.DONE and tenant in item.get('dn'):
                resp = wait_args(ifc.api.get, func_args=[Vns.URI % 'vnsLDevOperInfo'],
                                 condition=done,
                                 progress_cb=lambda ret: "devState: {0}".format([x.get('devState') for x in ret]),
                                 stabilize=30,
                                 *args, **kwargs)

        for item in resp:
            if item.get('devState') != LDevVip.DONE and tenant in item.get('dn'):
                raise TaskError("{0}:\n{1}".format('LDevVip failed...',
                                                   ET.tostring(item)))

        resp = wait_args(ifc.api.get, func_args=[Vns.URI % 'vnsCDevState'],
                         condition=done,
                         progress_cb=lambda ret: "devState: {0}".format([x.get('devState') for x in ret]),
                         *args, **kwargs)

        for item in resp:
            if item.get('devState') != LDevVip.DONE and tenant in item.get('dn'):
                raise TaskError("{0}:\n{1}".format('CDev failed...',
                                                   ET.tostring(item)))

    def set_phy(self, device, mdev):
        self.set('devtype', 'PHYSICAL')
        self.set('contextAware', 'multi-Context')

        # Select Device Package
        rs_mdev_att = ET.Element('vnsRsMDevAtt',
                                 attrib={'tDn': mdev.get('dn')})
        self.append(rs_mdev_att)

        # Select domain
        domain = ET.Element('vnsRsALDevToPhysDomP',
                            attrib={"tDn": "uni/phys-phys"})
        self.append(domain)

        # Set Cluster section
        cred = ET.Element('vnsCCred', attrib={'name': 'username'})
        cred.set('value', device.get_admin_creds().username)
        self.append(cred)

        cred_secret = ET.Element('vnsCCredSecret', attrib={'name': 'password'})
        cred_secret.set('value', device.get_admin_creds().password)
        self.append(cred_secret)

        mgmt = ET.Element('vnsCMgmt')
        mgmt.set('port', '443')
        mgmt.set('host', device.get_address())
        self.append(mgmt)

    def set_devmgr(self, name):
        dev_mgr = ET.Element('vnsRsALDevToDevMgr')
        dev_mgr.set('tnVnsDevMgrName', name)
        self.append(dev_mgr)

    def add_cdev_phy(self, device):
        name = device.specs.name
        label = device.specs.ctx_name

        cdev = CDev(name, label)
        cdev.set_cred(device)
        cdev.set_phy(device)

        self.append(cdev)

        return cdev

    def add_cdev_vcmp(self, host, guest):
        name = host.specs.name
        label = host.specs.ctx_name

        cdev = CDev(name, label)
        cdev.set_cred(guest)
        cdev.set_phy(host)

        self.append(cdev)

        return cdev

    def set_logical_ifc(self, device, tenant, dp=None):
        '''
        device needs to be the vCMP Host if vcmp harness is used
        '''
        # Add internal Cluster Interface
        internal = self.find('.//vnsLIf[@name="internal"]')
        external = self.find('.//vnsLIf[@name="external"]')

        # If XML payload doesn't contain vnsLIf, create it and setup initial
        # vnsRsMetaIf.
        if (internal is None or external is None) and dp is None:
            raise TaskError("You need to provide device package xml")

        if internal is None:
            internal = LIf('internal')
            internal.set_metaif(dp)
            self.append(internal)
        if external is None:
            external = LIf('external')
            external.set_metaif(dp)
            self.append(external)

        def get_cdev(address):
            cdev = None
            cdevs = self.findall('.//vnsCDev')
            for x in cdevs:
                if x.find('vnsCMgmt').get('host') == address:
                    cdev = x
            return cdev

        cdev = get_cdev(device.get_address())
        cdev_name = cdev.get('name') if cdev is not None else device.specs.name

        # Add internal Cluster Interface
        internal.add_cif(tenant, self.get('name'), cdev_name,
                         device.specs.internal.bigip_iface)

        # Add external Cluster Interface
        external.add_cif(tenant, self.get('name'), cdev_name,
                         device.specs.external.bigip_iface)


class CDev(ET.Element):

    def __init__(self, name, label, *args, **kwargs):
        super(CDev, self).__init__('vnsCDev', *args, **kwargs)
        self.set('name', name)
        self.set('devCtxLbl', label)

    def set_cred(self, device):
        """
        This function will set vnsCCred, vnsCCredSecret, and vnsCMgmt shown
        below. Need to pass in device access.
            <vnsCDev ...>
                <vnsCCred name="username" value="admin"/>
                <vnsCCredSecret name="password" value="admin"/>
                <vnsCMgmt port="443" host="10.10.10.10"/>
                .
                .
                .
            </vnsCDev>
        """
        cred = ET.Element('vnsCCred', attrib={'name': 'username'})
        cred.set('value', device.get_admin_creds().username)
        self.append(cred)

        cred_secret = ET.Element('vnsCCredSecret', attrib={'name': 'password'})
        cred_secret.set('value', device.get_admin_creds().password)
        self.append(cred_secret)

        mgmt = ET.Element('vnsCMgmt')
        mgmt.set('port', '443')
        mgmt.set('host', device.address)
        self.append(mgmt)

    def set_phy(self, device):
        """
        Set the device interface. This specifies the leaf to BIG-IP physically
        connection.
        """

        # External
        cif = CIf(device.specs.external.bigip_iface)
        cif.set_phy(device.specs.external.apic_eth)
        self.append(cif)

        # Internal
        cif = CIf(device.specs.internal.bigip_iface)
        cif.set_phy(device.specs.internal.apic_eth)
        self.append(cif)

    def set_ve(self):
        """"""

    def set_vcmp(self):
        """"""

    def set_chassis(self, chassis_name):
        """"""
        cdev_chassis = ET.Element('vnsRsCDevToChassis')
        cdev_chassis.set('tnVnsChassisName', chassis_name)

        self.append(cdev_chassis)


class LIf(ET.Element):
    URI = '/api/node/class/vnsLDevIfLIf'

    def __init__(self, name, *args, **kwargs):
        super(LIf, self).__init__('vnsLIf', *args, **kwargs)
        self.set('name', name)
        self.name = name

    def add_cif(self, tenant, ldev, cdev, ifc):
        rs_cif_att = ET.Element('vnsRsCIfAtt')
        # tdn = "uni/tn-common/lDevVip-F5/cDev-F5_Device_1/cIf-eth1/21"
        tdn = "%s/lDevVip-%s/cDev-%s/cIf-%s" % (tenant, ldev, cdev, ifc)
        rs_cif_att.set('tDn', tdn)

        self.append(rs_cif_att)

    def set_metaif(self, mdev):
        rs_meta_if = ET.Element('vnsRsMetaIf')
        # tdn = "uni/infra/mDev-F5-BIGIQ-2.0-apic-test/mIfLbl-internal"/
        tdn = '%s/mIfLbl-%s' % (mdev.get('dn'), self.name)
        rs_meta_if.set('tDn', tdn)

        self.append(rs_meta_if)


class CIf(ET.Element):
    def __init__(self, ip_iface, *args, **kwargs):
        super(CIf, self).__init__('vnsCIf', *args, **kwargs)
        self.set('name', ip_iface)

    def set_phy(self, apic_eth):
        # 'topology/pod-1/paths-101/pathep-[%s]' % apic_eth
        cif = ET.Element('vnsRsCIfPathAtt')
        cif.set('tDn', str(apic_eth))
        self.append(cif)

    def set_ve(self, vnic_name):
        self.set('vnicName', vnic_name)


class DevFolder(ET.Element):
    '''
    Try to mimic something like this:
        <vnsDevFolder key="HighAvailability" name="HA">
            <vnsDevParam key="VLAN" name="VLAN" value="3000"/>
            .
            .
            .
        </vnsDevFolder>

    a = DevFolder(attrib={'name':'HA', 'key': 'HighAvailability'})
    params = [{'key': 'VLAN', 'name': 'VLAN', 'value': '3000'}, {...}, ...]
    a.add_params(params)

    '''
    def __init__(self, key, name, *args, **kwargs):
        super(DevFolder, self).__init__('vnsDevFolder', *args, **kwargs)
        self.set('key', key)
        self.set('name', name)

    def add_params(self, params):
        """
        params can be a list or dictionary. If it is a dictionary it will put
        put it in a list.
        """
        if not isinstance(params, list):
            params = [params]

        for attrib in params:
            param = ET.Element('vnsDevParam', attrib=attrib)
            self.append(param)


class DeviceManager(ET.Element):
    '''
    Try to mimic something like this:
      <vnsDevMgr name="bigiq_management">
        <vnsCMgmts host="10.10.10.10" port="443"/>
        <vnsCCred name="username" value="admin"/>
        <vnsCCredSecret name="password" value="admin"/>
        <vnsRsDevMgrToMDevMgr
            tDn="uni/infra/mDevMgr-F5-BIGIQ-2.0-test-apic"
            />
      </vnsDevMgr>

    a = DeviceManager('bigiq_management')
    a.set_cred(device)
    a.set_device_manager_type(mdevmgr)
    for bigiq in bigiqs:
        a.add_device(bigiq)

    '''
    def __init__(self, name, device, mdevmgr, *args, **kwargs):
        super(DeviceManager, self).__init__('vnsDevMgr', *args, **kwargs)
        self.set('name', name)

        username = ET.Element('vnsCCred')
        username.set('name', 'username')
        username.set('value', device.get_admin_creds().username)
        self.append(username)

        password = ET.Element('vnsCCredSecret')
        password.set('name', 'password')
        password.set('value', device.get_admin_creds().password)
        self.append(password)

        dev_mgr_type = ET.Element('vnsRsDevMgrToMDevMgr')
        dev_mgr_type.set('tDn', mdevmgr.get('dn'))
        self.append(dev_mgr_type)

    def add_device(self, device):
        """
        device is DeviceAccess
        """
        management_interface = ET.Element('vnsCMgmts')
        management_interface.set('host', device.get_address())
        management_interface.set('port', '443')
        self.append(management_interface)


class ChassisManager(ET.Element):
    '''
    Try to mimic something like this:
      <vnsChassis name="chassis_manager1">
        <vnsCMgmts host="10.10.10.10" port="443"/>
        <vnsCCred name="username" value="admin"/>
        <vnsCCredSecret name="password" value="admin"/>
        <vnsRsChassisToMChassis tDn="uni/infra/mChassis-F5-BIGIQ-2.0-test-apic"/>
      </vnsChassis>


    a = DeviceManager('bigiq_management')
    a.set_cred(device)
    a.set_device_manager_type(mdevmgr)
    for bigiq in bigiqs:
        a.add_device(bigiq)

    '''
    def __init__(self, name, device, mchassis, *args, **kwargs):
        super(ChassisManager, self).__init__('vnsChassis', *args, **kwargs)
        self.set('name', name)

        management_interface = ET.Element('vnsCMgmts')
        management_interface.set('host', device.get_address())
        management_interface.set('port', '443')
        self.append(management_interface)

        username = ET.Element('vnsCCred')
        username.set('name', 'username')
        username.set('value', device.get_admin_creds().username)
        self.append(username)

        password = ET.Element('vnsCCredSecret')
        password.set('name', 'password')
        password.set('value', device.get_admin_creds().password)
        self.append(password)

        dev_mgr_type = ET.Element('vnsRsDevMgrToMDevMgr')
        dev_mgr_type.set('tDn', mchassis.get('dn'))
        self.append(dev_mgr_type)
