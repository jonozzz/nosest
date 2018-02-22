#!/usr/bin/python
'''
Created on Jan 16, 2018

@author: jono
'''
from ansible.plugins.action import ActionBase
from f5test.base import Options
from f5test.macros.ha import FailoverMacro
# import json

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(ActionBase):
    ''' Print statements during execution '''

    TRANSFERS_FILES = False
    VALID_ARGS = frozenset(('peers_group', 'config', 'sync', 'reset', 'ipv6',
                            'device_group', 'vlan', 'timeout', 'cas_group',
                            'set_default_active'))

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        for arg in self._task.args:
            if arg not in self.VALID_ARGS:
                return {"failed": True, "msg": "'%s' is not a valid option for f5_ha" % arg}

        result = super(ActionModule, self).run(tmp, task_vars)
        result['_ansible_verbose_override'] = True

        def parse_groups(group_name):
            devices = []
            if group_name in self._task.args:
                group = str(self._task.args[group_name])
                hosts = task_vars['groups'].get(group, [])
                if not hosts:
                    display.vvv('f5_ha: %s is empty!' % group_name)

                for host in hosts:
                    devices.append(task_vars['hostvars'][host]['f5test_device'])
            result[group_name] = devices
            return devices

        peers = parse_groups('peers_group')
        cas = parse_groups('cas_group')

        if not peers and cas:
            peers[:] = cas[1:]
            cas[:] = cas[:1]

        if not cas:
            return result

        options = Options()

        if 'set_default_active' in self._task.args:
            for device in cas + peers:
                if device.is_default():
                    # XXX: This is not OK, because the alias is controlled by
                    # FailoverMacro
                    options.set_active = '/Common/device-%s' % device.get_discover_address()

        options.config = self._task.args.get('config', False)
        options.sync = self._task.args.get('sync', False)
        options.reset = self._task.args.get('reset', False)
        options.ipv6 = self._task.args.get('ipv6', False)
        options.device_group = self._task.args.get('device_group', '/Common/f5test.ha-dg')
        options.ha_vlan = self._task.args.get('vlan', '/Common/internal')
        if not options.ha_vlan.startswith('/'):
            options.ha_vlan = '/Common/' + options.ha_vlan
        options.timeout = int(self._task.args.get('timeout', 60))

        macro = FailoverMacro(options=options, authorities=cas, peers=peers,
                              groups=[options.device_group])
        result['output'] = macro.run()

        return result
