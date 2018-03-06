#!/usr/bin/python
'''
Created on Mar 5, 2018

@author: jono
'''
from ansible.plugins.action import ActionBase
from f5test.base import Options
from f5test.macros.unmerge import Tool

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(ActionBase):
    ''' Print statements during execution '''

    TRANSFERS_FILES = False
    VALID_ARGS = frozenset(('filename', 'address', 'port', 'username', 'password',
                            'verbose', 'timeout'))

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        for arg in self._task.args:
            if arg not in self.VALID_ARGS:
                return {"failed": True, "msg": "'%s' is not a valid option for f5_unmerge" % arg}

        result = super(ActionModule, self).run(tmp, task_vars)
        #result['_ansible_verbose_override'] = True

        options = Options()

        options.port = self._task.args.get('port')
        options.username = self._task.args.get('username')
        options.password = self._task.args.get('password')
        options.verbose = self._task.args.get('verbose')
        options.timeout = int(self._task.args.get('timeout', 60))
        address = self._task.args.get('address')
        filename = self._task.args.get('filename')

        macro = Tool(options, address, filename)
        result['output'] = macro.run()

        return result
