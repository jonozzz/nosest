'''
Created on Feburary 9, 2016
@author: jwong

'''
from .....base import AttrDict
from f5test.base import Options
import xml.etree.ElementTree as ET


class GraphTemplate(ET.Element):
    URI = '/api/node/class/vnsAbsGraph'

    def __init__(self, name, arm='UNSPECIFIED', *args, **kwargs):
        super(GraphTemplate, self).__init__('vnsAbsGraph', *args, **kwargs)
        self.set('name', name)
        self.set('uiTemplateType', arm)

        # Add consumer terminal node
        consumer = ET.Element('vnsAbsTermNodeCon')
        consumer.set('name', 'T1')

        term_conn = ET.Element('vnsAbsTermConn')
        term_conn.set('name', '1')
        term_conn.set('attNotify', 'no')

        consumer.append(term_conn)
        self.append(consumer)

        # Add consumer provider node
        provider = ET.Element('vnsAbsTermNodeProv')
        provider.set('name', 'T2')

        term_conn = ET.Element('vnsAbsTermConn')
        term_conn.set('name', '1')
        term_conn.set('attNotify', 'no')

        provider.append(term_conn)
        self.append(provider)

    def set_function_node(self, ifc, catalog, ldevif, name='ADC'):
        function_node = ET.Element('vnsAbsNode')
        function_node.set('name', name)
        function_node.set('funcType', 'GoTo')

        # Add function connector
        r = ifc.api
        resp = r.get(MetaFunctionConnector.URI)
        metas = [x for x in resp if 'mFunc-%s' % catalog.templateName in x.get('dn')]

        for meta in metas:
            function_connector = ET.Element('vnsAbsFuncConn')
            function_connector.set('attNotify', 'no')
            meta_connector = ET.Element('vnsRsMConnAtt')

            if "mConn-external" in meta.get('dn'):
                function_connector.set('name', 'external')
                meta_connector.set('tDn', meta.get('dn'))
            elif "mConn-internal" in meta.get('dn'):
                function_connector.set('name', 'internal')
                meta_connector.set('tDn', meta.get('dn'))

            function_connector.append(meta_connector)
            function_node.append(function_connector)

        # Add function profile
        function_profile = ET.Element('vnsRsNodeToAbsFuncProf')
        resp = r.get(FunctionProfile.URI)
        for item in resp:
            if catalog.templateName in item.get('dn'):
                function_profile.set('tDn', item.get('dn'))
        function_node.append(function_profile)

        # Add service function
        service_function = ET.Element('vnsRsNodeToMFunc')
        resp = r.get(ServiceFunction.URI)
        for item in resp:
            if catalog.templateName in item.get('dn'):
                service_function.set('tDn', item.get('dn'))
        function_node.append(service_function)

        # Add device cluster
        device_cluster = ET.Element('vnsRsNodeToLDev')
        device_cluster.set('tDn', ldevif.get('dn'))
        function_node.append(device_cluster)

        self.append(function_node)

    def set_connections(self, tenant_name):
        attrib = Options(unicastRoute='yes', connType='external', adjType='L2')
        graph_name = self.get('name')
        node_name = self.find('vnsAbsNode').get('name')
        provider_name = self.find('vnsAbsTermNodeProv').get('name')
        consumer_name = self.find('vnsAbsTermNodeCon').get('name')
        connectors = self.findall('*vnsAbsFuncConn')
        for connector in connectors:
            if 'mConn-external' in connector.find('vnsRsMConnAtt').get('tDn'):
                external_connector_name = connector.get('name')
            elif 'mConn-internal' in connector.find('vnsRsMConnAtt').get('tDn'):
                internal_connector_name = connector.get('name')

        # Add external connection
        external_connection = ET.Element('vnsAbsConnection', attrib=attrib)
        external_connection.set('name', 'C1')

        tdn = 'uni/tn-%s/AbsGraph-%s/AbsNode-%s/AbsFConn-%s' % (tenant_name,
                                                                graph_name,
                                                                node_name,
                                                                external_connector_name)
        connection_to_connector = ET.Element('vnsRsAbsConnectionConns')
        connection_to_connector.set('tDn', tdn)
        external_connection.append(connection_to_connector)

        tdn = 'uni/tn-%s/AbsGraph-%s/AbsTermNodeCon-%s/AbsTConn' % (tenant_name,
                                                                    graph_name,
                                                                    consumer_name)
        connection_to_connector = ET.Element('vnsRsAbsConnectionConns')
        connection_to_connector.set('tDn', tdn)
        external_connection.append(connection_to_connector)

        # Add internal connection
        internal_connection = ET.Element('vnsAbsConnection', attrib=attrib)
        internal_connection.set('name', 'C2')

        tdn = 'uni/tn-%s/AbsGraph-%s/AbsNode-%s/AbsFConn-%s' % (tenant_name,
                                                                graph_name,
                                                                node_name,
                                                                internal_connector_name)
        connection_to_connector = ET.Element('vnsRsAbsConnectionConns')
        connection_to_connector.set('tDn', tdn)
        internal_connection.append(connection_to_connector)

        tdn = 'uni/tn-%s/AbsGraph-%s/AbsTermNodeProv-%s/AbsTConn' % (tenant_name,
                                                                    graph_name,
                                                                    provider_name)
        connection_to_connector = ET.Element('vnsRsAbsConnectionConns')
        connection_to_connector.set('tDn', tdn)
        internal_connection.append(connection_to_connector)

        self.append(external_connection)
        self.append(internal_connection)


class FolderInst(ET.Element):
    class vnsParamInst(ET.Element):
        def __init__(self, name, key, value):
            self.setdefault('@name', name)
            self.setdefault('@key', key)
            self.setdefault('@value', value)

    class vnsCfgRelInst(ET.Element):
        def __init__(self, name, key, target):
            self.setdefault('@name', name)
            self.setdefault('@key', key)
            self.setdefault('@targetName', target)

    def __init__(self, *args, **kwargs):
        super(FolderInst, self).__init__(*args, **kwargs)
        self.setdefault('vnsFolderInst', AttrDict())
        self.vnsFolderInst.setdefault('vnsFolderInst', list())
        self.vnsFolderInst.setdefault('vnsParamInst', list())
        self.vnsFolderInst.setdefault('vnsCfgRelInst', list())
        self.vnsFolderInst.setdefault('@name', '')
        self.vnsFolderInst.setdefault('@nodeNameOrLbl', '')
        self.vnsFolderInst.setdefault('@graphNameOrLbl', '')
        self.vnsFolderInst.setdefault('@ctrctNameOrLbl', '')
        self.vnsFolderInst.setdefault('@key', '')
        self.vnsFolderInst.setdefault('@devCtxLbl', '')

    def add_param(self, *args, **kwargs):
        param = self.vnsParamInst(*args, **kwargs)
        self.vnsFolderInst.vnsParamInst.append(param)

    def add_relation(self, *args, **kwargs):
        param = self.vnsCfgRelInst(*args, **kwargs)
        self.vnsFolderInst.vnsCfgRelInst.append(param)


class FunctionProfile(object):
    URI = '/api/node/class/vnsAbsFuncProf'


class MetaFunctionConnector(object):
    URI = '/api/node/class/vnsMConn'


class ServiceFunction(object):
    URI = '/api/node/class/vnsMFunc'
