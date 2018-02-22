'''
Created on Feburary 9, 2016
@author: jwong

'''
from .base import Vns, TaskError
from .....utils.wait import wait_args
import xml.etree.ElementTree as ET
from f5test.base import Options


class Tenant(ET.Element):
    # Need tenant_dn
    TENANT_DN = 'uni/tn-%s'
    OBJECTS = '/api/node/class/fvTenant'
    URI = '/api/node/mo/%s' % TENANT_DN
    PENDING_STATES = ('init', 'modifypending', 'auditpending')
    GRAPH_APPLIED = 'applied'
    DONE = 'stable'

    def __init__(self, *args, **kwargs):
        super(Tenant, self).__init__('fvTenant', *args, **kwargs)

    def add_context(self, name):
        context = ET.Element('fvCtx', attrib={'name': name})
        self.append(context)
        return context

    def add_bridge_domain(self, *args, **kwargs):
        bridge_domain = BridgeDomain(*args, **kwargs)
        self.append(bridge_domain)
        return bridge_domain

    def add_application_profile(self, *args, **kwargs):
        application_profile = ApplicationProfile(*args, **kwargs)
        self.append(application_profile)
        return application_profile

    def add_contract(self, *args, **kwargs):
        contract = Contract(*args, **kwargs)
        self.append(contract)
        return contract

    def add_device_selector(self, *args, **kwargs):
        device_selector = DeviceSelectorPolicy(*args, **kwargs)
        self.append(device_selector)
        return device_selector

    def export_device_cluster(self, *args, **kwargs):
        ldevvip = ExportDeviceCluster(*args, **kwargs)
        self.append(ldevvip)
        return ldevvip

    @staticmethod
    def wait_graph(ifc, tenant, *args, **kwargs):
        """
        We will need to wait on 2 spots: vnsGraphInst and vnsVDevOperInfo.
        """
        def done_graph(resp):
            return all([x.get('configSt') in Tenant.GRAPH_APPLIED
                        for x in resp]) and len(resp) != 0

        def done_vdev(resp):
            return all([x.get('operState') not in Tenant.PENDING_STATES
                        for x in resp]) and len(resp) != 0

        wait_args(Vns.get_vns, func_args=[ifc, 'vnsGraphInst'],
                  condition=done_graph,
                  progress_cb=lambda ret: "configSt: {}".format([x.get('configSt') for x in ret]),
                  *args, **kwargs)

        resp = wait_args(Vns.get_vns, func_args=[ifc, 'vnsVDevOperInfo'],
                         condition=done_vdev,
                         progress_cb=lambda ret: "operState: {}".format([x.get('operState') for x in ret]),
                         *args, **kwargs)

        for item in resp:
            if item.get('operState') != Tenant.DONE:
                raise TaskError("{0}:\n{1}".format('Failed to setup Deploy Service Graph',
                                                   ET.tostring(item)))


class BridgeDomain(ET.Element):
    def __init__(self, name, options=None, *args, **kwargs):
        super(BridgeDomain, self).__init__('fvBD', *args, **kwargs)
        o = Options(options)

        if o.context:
            self.set('name', name)
            context = ET.Element('fvRsCtx')
            context.set('tnFvCtxName', options.context)
            self.append(context)

        if o.subnet:
            subnet = ET.Element('fvSubnet', attrib={'scope': 'private'})
            subnet.set('ip', options.subnet)
            self.append(subnet)


class Contract(ET.Element):
    class Subject(ET.Element):
        def add_filter(self, filt):
            subject_filter = ET.Element('vzRsSubjFiltAtt')
            subject_filter.set('tnVzFilterName', filt)
            self.append(subject_filter)

    def __init__(self, name, *args, **kwargs):
        super(Contract, self).__init__('vzBrCP', *args, **kwargs)
        self.set('name', name)

    def add_subject(self, name, filter_names=None, *args, **kwargs):
        subject = self.Subject('vzSubj')
        subject.set('name', name)

        # Initialize if this isn't set
        if filter_names is None:
            filters = ['default']

        for filt in filters:
            subject.add_filter(filt)

        self.append(subject)

    def attach(self, subject_name, graph_name):
        subject = self.find('*[@name="%s"]' % subject_name)
        graph = ET.Element('vzRsSubjGraphAtt')
        graph.set('tnVnsAbsGraphName', graph_name)
        subject.append(graph)


class ApplicationProfile(ET.Element):
    class EPG(ET.Element):
        def initial_set(self, bd_name, vmm):
            bd = ET.Element('fvRsBd')
            bd.set('tnFvBDName', bd_name)
            self.append(bd)

            #  uni/vmmp-VMware/dom-$$dvs_name$$
            domain = ET.Element('fvRsDomAtt')
            domain.set('tDn', vmm.get('dn'))
            self.append(domain)

        def add_folder(self, *args, **kwargs):
            folder = FolderInst(*args, **kwargs)
            self.append(folder)

            return folder

        def add_network_folder(self, devices, param, ip_set=1):
            node_name = param.node_name
            graph_name = param.graph_name
            contract_name = param.contract_name

            # Set Network Folder
            param = Options(key="Network", name="Network",
                                node_name=node_name,
                                graph_name=graph_name,
                                contract_name=contract_name)
            network_folder = FolderInst(param)

            # TODO: Need to put logic here to check if an IP is within a network
            for idx, bigip in enumerate(devices):
                if ip_set == 1:
                    int_ip = bigip.specs.internal.address1
                    ext_ip = bigip.specs.external.address1
                elif ip_set == 2:
                    int_ip = bigip.specs.internal.address2
                    ext_ip = bigip.specs.external.address2

                # Add external selfip
                param = Options(key="ExternalSelfIP",
                                name="ExternalSelfIP%s" % idx,
                                node_name=node_name,
                                graph_name=graph_name,
                                contract_name=contract_name,
                                dev_label=bigip.specs.ctx_name)
                folder_params = FolderInst(param)
                params = []
                params.append(Options(key="Floating", name="Floating",
                                      value='NO'))
                params.append(Options(key="PortLockdown",
                                      name="PortLockdown", value='DEFAULT'))
                params.append(Options(key="SelfIPAddress",
                                      name="SelfIPAddress", value=ext_ip))
                params.append(Options(key="SelfIPNetmask",
                                      name="SelfIPNetmask",
                                      value=bigip.specs.external.netmask))
                folder_params.add_params(params)
                network_folder.append(folder_params)

                # Add internal selfip
                param = Options(key="InternalSelfIP",
                                name="InternalSelfIP%s" % idx,
                                node_name=node_name,
                                graph_name=graph_name,
                                contract_name=contract_name,
                                dev_label=bigip.specs.ctx_name)
                folder_params = FolderInst(param)
                params = []
                params.append(Options(key="Floating", name="Floating",
                                      value='NO'))
                params.append(Options(key="PortLockdown",
                                      name="PortLockdown", value='DEFAULT'))
                params.append(Options(key="SelfIPAddress",
                                      name="SelfIPAddress", value=int_ip))
                params.append(Options(key="SelfIPNetmask",
                                      name="SelfIPNetmask",
                                      value=bigip.specs.internal.netmask))
                folder_params.add_params(params)
                network_folder.append(folder_params)

            self.append(network_folder)

        def add_float_selfips(self, device, param):
            # TODO: Need to put logic here to check if an IP is within a network
            node_name = param.node_name
            graph_name = param.graph_name
            contract_name = param.contract_name
            network_folder = self.find('*[@key="Network"]')

            # Add external float selfip
            param = Options(key="ExternalSelfIP", name="ExternalFloat",
                            node_name=node_name,
                            graph_name=graph_name,
                            contract_name=contract_name)
            folder_params = FolderInst(param)
            params = []
            params.append(Options(key="Floating", name="Floating", value='YES'))
            params.append(Options(key="PortLockdown", name="PortLockdown",
                                  value='DEFAULT'))
            params.append(Options(key="SelfIPAddress", name="SelfIPAddress",
                                  value=device.specs.external.float1))
            params.append(Options(key="SelfIPNetmask", name="SelfIPNetmask",
                                  value=device.specs.external.netmask))
            folder_params.add_params(params)
            network_folder.append(folder_params)

            # Add internal float selfip
            param = Options(key="InternalSelfIP", name="InternalFloat",
                            node_name=node_name,
                            graph_name=graph_name,
                            contract_name=contract_name)
            folder_params = FolderInst(param)
            params = []
            params.append(Options(key="Floating", name="Floating", value='YES'))
            params.append(Options(key="PortLockdown", name="PortLockdown",
                                  value='DEFAULT'))
            params.append(Options(key="SelfIPAddress", name="SelfIPAddress",
                                  value=device.specs.internal.float1))
            params.append(Options(key="SelfIPNetmask", name="SelfIPNetmask",
                                  value=device.specs.internal.netmask))
            folder_params.add_params(params)
            network_folder.append(folder_params)

        def set_network_relation(self, param):
            network_name = self.find('*[@key="Network"]').get('name')
            param = Options(key="NetworkRelation", name="NetworkRelation",
                            node_name=param.node_name,
                            graph_name=param.graph_name,
                            contract_name=param.contract_name)
            network_relation = FolderInst(param)
            config = ET.Element('vnsCfgRelInst')
            config.set('name', 'NetworkRel')
            config.set('key', 'NetworkRel')
            config.set('targetName', network_name)
            network_relation.append(config)
            self.append(network_relation)

        def set_contract_provider(self, contract_name):
            provider = ET.Element('fvRsProv')
            provider.set('tnVzBrCPName', contract_name)
            self.append(provider)

        def set_contract_consumer(self, contract_name):
            consumer = ET.Element('fvRsCons')
            consumer.set('tnVzBrCPName', contract_name)
            self.append(consumer)

    def __init__(self, name, *args, **kwargs):
        super(ApplicationProfile, self).__init__('fvAp', *args, **kwargs)
        self.set('name', name)

    def add_epg(self, epg_name):
        epg = self.EPG('fvAEPg')
        epg.set('name', epg_name)

        self.append(epg)
        return epg


class DeviceSelectorPolicy(ET.Element):
    def __init__(self, param, *args, **kwargs):
        super(DeviceSelectorPolicy, self).__init__('vnsLDevCtx', *args,
                                                   **kwargs)
        self.set('nodeNameOrLbl', param.node_name)
        self.set('graphNameOrLbl', param.graph_name)
        self.set('ctrctNameOrLbl', param.contract_name)

    def set_ldevif(self, ldevif):
        ldev_relation = ET.Element('vnsRsLDevCtxToLDev')
        ldev_relation.set('tDn', ldevif.get('dn'))
        self.append(ldev_relation)

    def add_lif(self, lif, *args, **kwargs):
        logical_interface_context = ET.Element('vnsLIfCtx')
        logical_interface_context.set('connNameOrLbl', lif.get('name'))
        logical_interface_relation = ET.Element('vnsRsLIfCtxToLIf')
        logical_interface_relation.set('tDn', lif.get('dn'))
        logical_interface_context.append(logical_interface_relation)
        self.append(logical_interface_context)


class FolderInst(ET.Element):
    def __init__(self, param, *args, **kwargs):
        super(FolderInst, self).__init__('vnsFolderInst', *args, **kwargs)
        self.set('key', param.key)
        self.set('name', param.name)
        self.set('nodeNameOrLbl', param.node_name)
        self.set('graphNameOrLbl', param.graph_name)
        self.set('ctrctNameOrLbl', param.contract_name)
        if param.dev_label:
            self.set('devCtxLbl', param.dev_label)

    def add_params(self, params):
        if not isinstance(params, list):
            params = [params]

        for item in params:
            param = ET.Element('vnsParamInst')

            param.set('key', item.key)
            param.set('name', item.name)
            param.set('value', item.value)
            self.append(param)


class Chassis(ET.Element):
    URI = '/api/node/class/vnsChassis'

    def __init__(self, name, device, *args, **kwargs):
        super(Chassis, self).__init__('vnsChassis', *args, **kwargs)
        self.set('name', name)

        username = ET.Element('vnsCCred')
        username.set('name', 'username')
        username.set('value', device.get_admin_creds().username)

        password = ET.Element('vnsCCredSecret')
        password.set('name', 'password')
        password.set('value', device.get_admin_creds().password)

        mgmt = ET.Element('vnsCMgmts')
        mgmt.set('port', '443')
        mgmt.set('host', device.get_address())

        self.append(username)
        self.append(password)
        self.append(mgmt)

    def set_type(self, mchassis):
        chassis_type = ET.Element('vnsRsChassisToMChassis')
        chassis_type.set('tDn', mchassis.get('dn'))

        self.append(chassis_type)


class DevMgr(ET.Element):
    URI = '/api/node/class/vnsDevMgr'

    def __init__(self, name, device, *args, **kwargs):
        super(DevMgr, self).__init__('vnsDevMgr', *args, **kwargs)
        self.set('name', name)

        username = ET.Element('vnsCCred')
        username.set('name', 'username')
        username.set('value', device.get_admin_creds().username)

        password = ET.Element('vnsCCredSecret')
        password.set('name', 'password')
        password.set('value', device.get_admin_creds().password)

        self.append(username)
        self.append(password)

    def add_mgmt(self, device):
        mgmt = ET.Element('vnsCMgmts')
        mgmt.set('port', '443')
        mgmt.set('host', device.get_address())

        self.append(mgmt)

    def set_type(self, mchassis):
        chassis_type = ET.Element('vnsRsDevMgrToMDevMgr')
        chassis_type.set('tDn', mchassis.get('dn'))

        self.append(chassis_type)


class ExportDeviceCluster(ET.Element):
    URI = '/api/node/class/vnsLDevIf'

    def __init__(self, ldev, *args, **kwargs):
        super(ExportDeviceCluster, self).__init__('vnsLDevIf', *args, **kwargs)
        self.set('ldev', ldev.get('dn'))  # uni/tn-common/lDevVip-F5
