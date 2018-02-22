'''
Created on Feburary 9, 2016
@author: jwong

'''
from ...base import BaseApiObject
from .....base import AttrDict
import xml.etree.ElementTree as ET


class ManagedObject(object):
    URI = '/api/node/mo/%s'


class Infra(object):
    URI = ManagedObject.URI % 'uni/infra'


class aaaLogin(BaseApiObject):
    URI = '/api/aaaLogin'

    def __init__(self, *args, **kwargs):
        super(aaaLogin, self).__init__(*args, **kwargs)
        self.setdefault('aaaUser', AttrDict())
        self.aaaUser.setdefault('@name', 'admin')
        self.aaaUser.setdefault('@pwd', str())


class aaaRefresh(BaseApiObject):
    URI = '/api/aaaRefresh'

    def __init__(self, *args, **kwargs):
        super(aaaRefresh, self).__init__(*args, **kwargs)


class aaaLogout(BaseApiObject):
    URI = '/api/aaaLogout'

    def __init__(self, *args, **kwargs):
        super(aaaLogin, self).__init__(*args, **kwargs)
        self.setdefault('aaaUser', AttrDict())
        self.aaaUser.setdefault('@name', 'admin')


class DevicePackage(BaseApiObject):
    UPLOAD_URI = '/ppi/node/mo'
    DELETE_URI = '/api/node/mo/uni/infra'
    URI = '/api/node/class/vnsMDev'

    def __init__(self, *args, **kwargs):
        super(DevicePackage, self).__init__(*args, **kwargs)


class VlanPool(ET.Element):
    URI = '/api/node/mo/uni/infra'

    def __init__(self, *args, **kwargs):
        super(VlanPool, self).__init__('fvnsVlanInstP', *args, **kwargs)
        self.set('name', 'webService')
        self.set('allocMode', 'dynamic')
        vlan = ET.Element('fvnsEncapBlk')
        vlan.set('name', 'encap')
        vlan.set('from', 'vlan-200')
        vlan.set('to', 'vlan-299')
        self.append(vlan)

    def set_delete(self):
        self.set('status', 'deleted')


# A very specific URI that associates a VLAN Pool to the phy and VE domain
class RsVlanNs(ET.Element):
    PHY_URI = '/api/node/mo/uni/phys-phys/rsvlanNs'
    VM_URI = '/api/node/mo/uni/vmmp-VMware/dom-%s/rsvlanNs'

    def __init__(self, *args, **kwargs):
        super(RsVlanNs, self).__init__('infraRsVlanNs', *args, **kwargs)
        self.set('tDn', 'uni/infra/vlanns-[webService]-dynamic')

    def set_delete(self):
        self.set('status', 'deleted')


# This is used for a POST with XMLs
class GenericApicPost(BaseApiObject):
    URI = '/api/node/mo/.xml'

    def __init__(self, *args, **kwargs):
        super(GenericApicPost, self).__init__(*args, **kwargs)


class VDev(ET.Element):
    URI = '/api/node/class/vnsVDev'

    def __init__(self, *args, **kwargs):
        super(VDev, self).__init__(*args, **kwargs)


class MDevMgr(ET.Element):
    URI = '/api/node/class/vnsMDevMgr'

    def __init__(self, vendor, model, version, dp, *args, **kwargs):
        super(MDevMgr, self).__init__('vnsMDevMgr', *args, **kwargs)
        self.set('vendor', vendor)
        self.set('model', model)
        self.set('version', version)

        service_device_type = ET.Element('vnsRsMDevMgrToMDev')
        service_device_type.set('tDn', dp.get('dn'))
        self.append(service_device_type)


class MChassis(ET.Element):
    URI = '/api/node/class/vnsMChassis'

    def __init__(self, vendor, model, version, dp, *args, **kwargs):
        super(MChassis, self).__init__('vnsMChassis', *args, **kwargs)
        self.set('vendor', vendor)
        self.set('model', model)
        self.set('version', version)

        service_device_type = ET.Element('vnsRsMChassisToMDev')
        service_device_type.set('tDn', dp.get('dn'))
        self.append(service_device_type)
