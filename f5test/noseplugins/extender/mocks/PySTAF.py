'''
Created on Jan 29, 2018

@author: jono
'''
from f5test.interfaces.testcase import ContextHelper
import logging

from f5test.utils.respool import IpPortResourcePool, MemcachePool
from f5test.utils.respool.base import IPAddressPortResourceItem, NumericResourceItem, IPAddressResourceItem

LOG = logging.getLogger(__name__)


class STAFResult(object):
    Ok = 0

    def __init__(self, rc):
        self.rc = rc
        self.result = None


class STAFException(Exception):
    pass


class STAFHandle(object):
    Synchronous = 1
    Standard = 1
    Static = 1

    _handle_vars = {'staf-map-class-name': 'STAF/Service/Var/VarInfo', 'name/member1/member/ip': '10.22.3.1',
                    'apache/docroots': '/ite-http/7980', 'name/vip2/vip': '10.22.40.1:20902',
                    'name/vip4/vip': '10.22.40.1:20171', 'name/vip3/vip': '10.22.40.1:20486',
                    'name/vip1/vip': '10.22.40.1:20007', 'name/member1/member': '10.22.3.1:20897',
                    'name/doc/docroot': '/ite-http/7980'}

    _system_vars = {'staf/env/staf_instance_name': 'STAF', 'staf/env/pwd': '/',
                    'staf/env/qtlib': '/usr/lib64/qt-3.3/lib', 'staf/env/shell': '/bin/bash',
                    'staf/config/sep/path': ':', 'staf-map-class-name': 'STAF/Service/Var/VarInfo',
                    'staf/config/mem/physical/bytes': '14610649088', 'staf/config/processor/numavail': '1',
                    'staf/version': '3.4.1', 'staf/config/os/minorversion': '#1 SMP Fri Nov 22 03:15:09 UTC 2013',
                    'staf/config/instancename': 'STAF', 'staf/env/hostname': 'Guest1-ITE',
                    'staf/env/django_settings_module': 'allu.settings', 'staf/env/tz': 'America/Los_Angeles',
                    'staf/config/machine': 'Guest1-ITE', 'staf/config/bootdrive': '/',
                    'staf/config/codepage': 'UTF-8', 'staf/env/lang': 'en_US.UTF-8',
                    'staf/env/path': '',
                    'staf/env/_': '/usr/local/staf/bin/STAFProc', 'staf/config/os/revision': 'x86_64',
                    'staf/env/home': '/root', 'staf/config/machinenickname': 'Guest1-ITE',
                    'staf/config/sep/line': '\n', 'staf/env/shlvl': '5',
                    'staf/config/mem/physical/kb': '14268212', 'staf/env/p4editor': 'vim', 'staf/env/logname': 'root',
                    'staf/env/g_broken_filenames': '1', 'staf/env/staf_quiet_mode': '1', 'staf/config/sep/command': ';',
                    'staf/env/p4user': '', 'staf/env/f5ite_host_vars_dir': '/etc',
                    'staf/env/mount_dir': '',
                    'staf/env/ls_colors': '',
                    'staf/env/ssh_askpass': '',
                    'staf/env/p4client': '', 'staf/env/f5ite_chroot_script_dir': '/root',
                    'staf/env/lessopen': '|/usr/bin/lesspipe.sh %s',
                    'staf/env/ld_library_path': '',
                    'staf/env/cvs_rsh': 'ssh', 'staf/env/histcontrol': 'ignoredups', 'staf/env/ssh_tty': '/dev/pts/0',
                    'staf/env/file_sys_name': 'chroot',
                    'staf/env/perl5lib': '',
                    'staf/config/defaultauthenticator': 'none', 'staf/env/ssh_client': '',
                    'staf/env/inputrc': '/etc/inputrc', 'staf/datadir': '/HostShare/STAF',
                    'staf/env/p4port': 'perforce:1666', 'staf/env/name_cap': 'F5ITE',
                    'staf/env/qtdir': '/usr/lib64/qt-3.3', 'staf/env/user': '', 'staf/env/version': 'main',
                    'staf/env/stafconvdir': '/usr/local/staf/codepage', 'staf/config/sep/file': '/',
                    'staf/env/term': 'xterm', 'staf/env/module_conf_flag': '0',
                    'staf/config/configfile': '',
                    'staf/env/pythonpath': '',
                    'staf/env/mail': '/var/spool/mail/root', 'staf/env/ipv6_ok': '0',
                    'staf/config/mem/physical/mb': '13933', 'staf/config/os/name': 'Linux',
                    'staf/config/os/majorversion': '2.6.32-431.el6.x86_64',
                    'staf/env/ssh_connection': '',
                    'staf/env/classpath': '',
                    'staf/config/defaultinterface': 'ssl', 'staf/config/startuptime': '20180126-11:59:25',
                    'staf/env/display': 'localhost:10.0', 'staf/config/stafroot': '/usr/local/staf',
                    'staf/env/histsize': '1000', 'staf/env/f5ite_host_resolv': '/etc/resolv.conf'}

    _shared_vars = {'f5ite/bigip.1/details/dut_annunciator_board_serial': '',
                    'f5ite/bigip/1/net/external/1/tag-id': '1234',
                    'f5ite/bigip/1/details/dut_package_edition': 'Point Release 1',
                    'f5ite/net/external.1/respool/freeip/v6mask': '/64',
                    'f5ite/bigip.1/details/dut_os_version': '#1 SMP Mon Dec 18 08:44:23 PST 2017',
                    'f5ite/bigip.1/net/external.1/if/1/if': 'VLAN1234', 'f5ite/ite-ui/port': '50888',
                    'f5ite/bigip.1/details/dut_date': 'Mon Dec 18 10:06:59 PST 2017',
                    'f5ite/bigip.1/net/external.1/if/1/trunk_interfaces': '',
                    'f5ite/config-module/tc_file': '/path/to/foo.py',
                    'f5ite/net/external.1/respool/freeip/v6start': '2002::10:22:40:1',
                    'f5ite/cs.1/net/external.1/if/1/respool/aliasip/start': '10.22.3.1', 'f5ite/bigip/1/v6mask': 'None',
                    'f5ite/echo-port': '50007',
                    'f5ite/bigip/1/details/dut_package_version': 'Build 0.0.6 - Mon Dec 18 10:06:59 PST 2017',
                    'f5ite/bigip/1/details/dut_project': 'bigip13.1.x-dizzy', 'f5ite/ha-enabled': 'False',
                    'f5ite/bigip/1/mgmt/route/default': '',
                    'f5ite/bigip/1/details/dut_system_name': 'Linux',
                    'f5ite/bigip/1/details/dut_annunciator_board_serial': '',
                    'f5ite/bigip.1/route/default': '', 'f5ite/bigip.1/details/dut_version': '13.1.0.1',
                    'f5ite/bigip/1/details/dut_jobid': '960829',
                    'f5ite/bigip/1/details/dut_host_board_part_revision': '',
                    'f5ite/bigip.1/details/dut_build': '0.0.6', 'f5ite/net/external.1/respool/freeip/nm': '255.255.0.0',
                    'f5ite/chargen-port': '50019', 'f5ite/admin-net/alias/ip': '',
                    'f5ite/bigip.1/details/dut_built': '171218100659', 'f5ite/bigip/1/details/dut_basebuild': '0.0.6',
                    'f5ite/admin-net/alias/if': 'eth2', 'f5ite/bigip.1/default-failover-state': 'active',
                    'f5ite/sleuth/tcexec/logdir': '',
                    'f5ite/config-module/tc_id': '8229', 'f5ite/bigip.1/details/dut_base_mac': '00:23:E9:8F:14:89',
                    'f5ite/bigip.1/details/dut_host_board_part_revision': '',
                    'f5ite/cs.1/net/external.1/if/1/respool/aliasip/nm': '255.255.0.0',
                    'f5ite/bigip.1/details/dut_annunciator_board_part_revision': '',
                    'f5ite/selenium/display': 'localhost:99', 'f5ite/bigip/1/details/dut_mac_offset': '0',
                    'f5ite/sleuth/tcexec/current_runid': '201801291125.0.0719', 'f5ite/products-supported': 'BigIP ',
                    'f5ite/sleuth/tcexec/logdir_current': '/HostShare/sleuth/201801291125.0.0719',
                    'f5ite/bigip.1/details/dut_system_type': '0x75', 'f5ite/bigip.1/ui-name': 'admin',
                    'f5ite/bigip.1/mgmt/v6ip': 'None', 'f5ite/cs.1/username': 'root',
                    'f5ite/bigip-ha/1/net/external/1/v6vip/1/ip': '2002::10:22:40:1',
                    'f5ite/config-module/output': '',
                    'f5ite/bigip.1/mgmt/v6mask': 'None', 'f5ite/bigip/1/net/external/1/self/1/v6ip': '',
                    'f5ite/cs.1/ssh_port': '', 'f5ite/bigip.1/details/dut_system_name': 'Linux',
                    'f5ite/bigip/1/details/dut_product': 'BIG-IP',
                    'f5ite/bigip.1/details/dut_package_version': 'Build 0.0.6 - Mon Dec 18 10:06:59 PST 2017',
                    'f5ite/bigip.1/details/dut_host_id': 'Z101', 'f5ite/bigip/1/default-failover-state': 'active',
                    'f5ite/host/admin-net/nm': '255.255.255.0', 'f5ite/sleuth/sleuth_dut_jobid': '',
                    'f5ite/bigip/1/details/dut_system_id': 'Z101',
                    'f5ite/bigip/1/details/dut_switch_board_part_revision': '', 'f5ite/bigip.1/blades': '',
                    'f5ite/bigip-ha/1/net/external/1/vip/1/ip': '10.22.40.1',
                    'f5ite/bigip/1/details/dut_edition': 'Point Release 1', 'f5ite/http-port': '',
                    'f5ite/bigip/1/details/dut_annunciator_board_part_revision': '',
                    'f5ite/bigip.1/net/external.1/self/1/nm': '255.255.0.0',
                    'f5ite/bigip.1/details/dut_system_family': '0xC0000000',
                    'f5ite/net/external.1/respool/freeip/wanted': '249',
                    'f5ite/bigip.1/details/dut_project': 'dizzy',
                    'f5ite/bigip.1/net/external.1/self/1/v6mask': '/64', 'f5ite/test-net/alias/v6ip': '2002::10:22:3:1',
                    'f5ite/bigip/1/details/dut_os_release': '3.10.0-514.26.2.el7.x86_64',
                    'f5ite/cs.1/net/admin/if/1/nm': '255.255.255.0', 'staf-map-class-name': 'STAF/Service/Var/VarInfo',
                    'f5ite/bigip.1/details/dut_changelist': '2455422', 'f5ite/bigip/1/ui-name': 'admin',
                    'f5ite/cs.1/password': '', 'f5ite/bigip/1/net/external/1/name': 'VLAN1522',
                    'f5ite/bigip/1/details/dut_sequence': '13.1.0.1-0.0.6.0',
                    'f5ite/bigip.1/details/dut_package_edition': 'Point Release 1',
                    'f5ite/bigip/1/ui-password': '', 'f5ite/bigip/1/v6ip': 'None', 'f5ite/selenium/port': '54444',
                    'f5ite/test-net/alias/v6mask': '/64', 'f5ite/bigip.1/details/dut_edition': 'Point Release 1',
                    'f5ite/ntp-remote': 'None', 'f5ite/test-net/alias/wanted': '249',
                    'f5ite/cs.1/route/default': '', 'f5ite/bigip.1/username': '',
                    'f5ite/sleuthdb/host': '',
                    'f5ite/bigip/1/net/external/1/self/1/nm': '255.255.0.0',
                    'f5ite/host/default-route': '', 'f5ite/bigip.1/mgmt/nm': '255.255.255.0',
                    'f5ite/bigip/1/details/dut_host_name': '',
                    'f5ite/bigip.1/details/dut_sequence': '13.1.0.1-0.0.6.0',
                    'f5ite/bigip.1/details/dut_host_board_serial': '',
                    'f5ite/cs.1/net/external.1/if/1/trunk_enabled': 'False',
                    'f5ite/sleuth/sleuth_dut_version': '13.1.0.1',
                    'f5ite/bigip-ha/1/net/external/1/v6vip/1/v6mask': '/64',
                    'f5ite/bigip/1/external-net/self/ip': '10.22.1.1',
                    'f5ite/bigip.1/net/external.1/if/1/trunk_lacp': 'disabled',
                    'f5ite/bigip/1/mgmt/nm': '255.255.255.0', 'f5ite/sleuth/sleuth_dut_project': 'dizzy',
                    'f5ite/bigip.1/details/dut_switch_board_part_revision': '',
                    'f5ite/bigip/1/details/dut_system_type': '0x75', 'f5ite/bigip/count': '1',
                    'f5ite/cs.1/net/external.1/if/1/respool/aliasip/v6start': '2002::10:22:3:1',
                    'f5ite/bigip/1/vip': '10.22.40.1', 'f5ite/bigip/1/details/dut_product_category': 'VCMP',
                    'f5ite/sleuth/sleuth_dut_platform': 'Z101', 'f5ite/bigip.1/details/dut_product_category': 'VCMP',
                    'f5ite/bigip/1/details/dut_system_family': '0xC0000000',
                    'f5ite/cs.1/net/external.1/if/1/respool/aliasip/wanted': '249',
                    'f5ite/sleuth/sleuth_dut_build': '0.0.6', 'f5ite/bigip.1/password': '',
                    'f5ite/dns-server': '172.27.2.1', 'f5ite/slam-port': '50999',
                    'f5ite/bigip.1/details/dut_switch_board_serial': '',
                    'f5ite/bigip.1/details/dut_product_features': "",
                    'f5ite/bigip.1/net/external.1/vlan_name': 'VLAN1522', 'f5ite/ntp-server': '',
                    'f5ite/sleuth/tc_result_reason': '', 'f5ite/bigip.1/details/dut_time': '2018-01-29 19-25-27 PST',
                    'f5ite/bigip/1/details/dut_switch_board_serial': '',
                    'f5ite/bigip/1/external-net/self/nm': '255.255.0.0', 'f5ite/bigip/1/mgmt/ip': '',
                    'f5ite/bigip.1/details/dut_product': 'BIG-IP',
                    'f5ite/net/external.1/respool/freeip/start': '',
                    'f5ite/bigip.1/details/dut_jobid': '960829', 'f5ite/bigip/1/details/dut_host_id': 'Z101',
                    'f5ite/bigip-ha/1/1': 'f5ite/bigip/1', 'f5ite/test-net/free-port-range': '20000 21000',
                    'f5ite/bigip.1/details/dut_os_machine': 'x86_64', 'f5ite/bigip/1/details/dut_changelist': '2455422',
                    'f5ite/bigip.1/net/external.1/if/1/trunk_enabled': 'False',
                    'f5ite/bigip.1/net/external.1/self/1/ip': '10.22.1.1',
                    'f5ite/bigip/1/details/dut_os_machine': 'x86_64', 'f5ite/test-net/alias/v6wanted': '249',
                    'f5ite/bigip/1/details/dut_time': '2018-01-29 19-25-27 PST',
                    'f5ite/sleuthdb/name': 'sleuthRun_TEST', 'f5ite/host/admin-net/ip': '',
                    'f5ite/cs.1/net/external.1/if/1/ip': '10.22.1.3', 'f5ite/host/test-net/nm': '255.255.0.0',
                    'f5ite/bigip.1/net/external.1/if/1/tag-state': 'tagged',
                    'f5ite/bigip.1/details/dut_mac_offset': '0', 'f5ite/bigip.1/details/dut_system_id': 'Z101',
                    'f5ite/bigip/1/username': 'root', 'f5ite/bigip.1/details/dut_product_code': 'BIG-IP',
                    'f5ite/bigip/1/details/dut_product_features': "",
                    'f5ite/bigip/1/details/dut_base_mac': '00:23:E9:8F:14:89', 'f5ite/free-port-range': '20000 21000',
                    'f5ite/bigip.1/net/external.1/self/1/v6ip': '2002::10:22:1:1',
                    'f5ite/bigip/1/details/dut_date': 'Mon Dec 18 10:06:59 PST 2017',
                    'f5ite/bigip.1/ui-password': '', 'f5ite/cs.1/net/external.1/if/1/if': '',
                    'f5ite/cs.1/net/external.1/if/1/trunk_interfaces': '',
                    'f5ite/bigip/1/details/dut_product_version': '13.1.0.1',
                    'f5ite/bigip/1/net/external/1/tag-state': 'tagged', 'f5ite/bigip.1/mgmt/ip': '',
                    'f5ite/bigip.1/details/dut_os_release': '3.10.0-514.26.2.el7.x86_64',
                    'f5ite/host/test-net/ip': '10.22.1.3', 'f5ite/bigip/1/details/dut_platform': 'Z101',
                    'f5ite/daytime-port': '50013', 'f5ite/cs.1/net/external.1/if/1/trunk_lacp': 'disabled',
                    'f5ite/host/test-net/if': 'lo', 'f5ite/cs.1/net/external.1/vlan_name': '',
                    'f5ite/bigip/1/net/external/1/self/1/ip': '10.22.1.1',
                    'f5ite/bigip/1/net/external/1/if': 'VLAN1522', 'f5ite/bigip/1/net/external/1/self/1/v6mask': '/64',
                    'f5ite/net/external.1/nm': '255.255.0.0', 'f5ite/bigip.1/details/dut_product_version': '13.1.0.1',
                    'f5ite/bigip.1/net/external.1/if/1/tag-id': '1522',
                    'f5ite/bigip.1/details/dut_chassis_serial': 'chs103447s', 'f5ite/bigip/1/sccp/ip': 'None',
                    'f5ite/harness-type': 'OneArmed', 'f5ite/bigip/1/details/dut_chassis_serial': 'chs103447s',
                    'f5ite/nfs-share': '/HostShare', 'f5ite/cs.1/net/external.1/if/1/respool/aliasip/v6mask': '/64',
                    'f5ite/bigip.1/details/dut_platform': 'Z101',
                    'f5ite/bigip.1/details/dut_host_name': '',
                    'f5ite/bigip/1/details/dut_built': '171218100659', 'f5ite/bigip/1/password': '',
                    'f5ite/bigip/1/details/dut_host_board_serial': 'bld202083s',
                    'f5ite/cs.1/net/external.1/if/1/nm': '255.255.0.0', 'f5ite/test-net/alias/ip': '',
                    'f5ite/cs.1/net/admin/if/1/if': 'eth2', 'f5ite/bigip/1/details/dut_product_code': 'BIG-IP',
                    'f5ite/bigip/1/details/dut_os_version': '#1 SMP Mon Dec 18 08:44:23 PST 2017',
                    'f5ite/host/admin-net/if': 'eth2', 'f5ite/bigip.1/details/dut_basebuild': '0.0.6',
                    'f5ite/bigip/1/details/dut_build': '0.0.6', 'f5ite/bigip/1/details/dut_version': '13.1.0.1',
                    'f5ite/cs.1/net/admin/if/1/ip': '', 'f5ite/test-net/alias/if': 'eth5',
                    'f5ite/bigip.1/sccp/ip': 'None'}

    def __init__(self, handle, type=None):
        #self.handle = handle
        self.handle = 0
        self.type = type
        context = ContextHelper()
        self.cfgifc = context.get_config()
        rr = self.cfgifc.get_ranges()
        self.pools = self.cfgifc.get_respools()
        self.value_to_item = {}
        # for i, node in enumerate(rr.http_nodes):
        #     self._handle_vars['name/member%d/member/ip' % i] = node.ip
        #     self._handle_vars['name/member%d/member' % i] = "{0.ip}:{0.port}".format(node)
        # LOG.info('in __init__')

    def _update_respool(self):
        rp = self.cfgifc.get_respools()
        for i, item in enumerate(rp.vips.pool.items.values()):
            self._handle_vars['name/vip%d/vip' % (i + 1)] = "{0.ip}:{0.port}".format(item)

        if rp.socats:
            for i, item in enumerate(rp.socats.pool.items.values()):
                self._handle_vars['name/socat%d/vip' % (i + 1)] = "{0.ip}:{0.port}".format(item)

        docroots = []
        for i, member in enumerate(rp.members.pool.items.values()):
            self._handle_vars['name/member%d/member/ip' % (i + 1)] = member.ip
            self._handle_vars['name/member%d/member' % (i + 1)] = "{0.ip}:{0.port}".format(member)
            docroots.append(member.local_dir)

        if docroots:
            self._handle_vars['name/doc/docroot'] = docroots[0]
            self._handle_vars['apache/docroots'] = ','.join(docroots)

    def submit(self, location, service=None, request=None, mode=None):
        # LOG.info('in submit')

        result = STAFResult(0)
        request = request.lower()
        LOG.debug('STAF request: %s %s %s', request, service, location)
        if request.startswith('list handles'):
            # result.result = [{'handle': 666}]
            result.result = [{'handle': 0}]
            # result.result = []
        elif request.startswith('get shared var'):
            var = request.rsplit()[-1].lower()
            var = var.rsplit(':', 1)[-1]
            result.result = self._shared_vars.get(var, '')
        elif request.startswith('list shared'):
            result.result = self._shared_vars
        elif request.startswith('list system'):
            result.result = self._system_vars
        elif request.startswith('list handle'):
            self._update_respool()
            result.result = self._handle_vars
        elif request.startswith('request pool'):
            bits = request.split()
            item = self.pools[bits[2]].get(encode=False)
            if isinstance(item, (IPAddressPortResourceItem, IPAddressResourceItem)):
                result.result = str(item.ip)
            elif isinstance(item, NumericResourceItem):
                result.result = item.value
            else:
                LOG.error('Unknown pool request: %s', request)
            self.value_to_item[result.result] = item
        elif request.startswith('release pool'):
            # release pool %s entry %s force
            bits = request.split()
            pool_name = bits[2]
            ip = bits[4]
            item = self.value_to_item.pop(ip)
            result.result = self.pools[pool_name].free(item)
        else:
            #print("XXX:", location, service, request, mode)
            LOG.warning('Ignoring request: %s', request)
            result.result = {}
        return result

    def unregister(self):
        pass


class STAFMarshallingContext(object):

    def __init__(self, text, b=None):
        self.text = text
        self.b = b

    def getRootObject(self):
        return self.text

    @property
    def rootObject(self):
        return self.text


def unmarshall(text):
    return STAFMarshallingContext(text)


class STAFWrapData(object):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name
