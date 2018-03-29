'''
Created on Dec 28, 2017

@author: jono
'''
from __future__ import absolute_import

import shutil

import __main__
import inspect
import logging
import os
from f5test.defaults import KIND_ANY

LOG = logging.getLogger(__name__)
LOG2 = logging.getLogger(__name__ + '.lib')

# BEGIN: Hijack Ansible's (very dumb) logging
from ansible.utils.display import Display


class MyDisplay(Display):

    def __init__(self, verbosity=0):
        Display.__init__(self, verbosity=verbosity)
        self.logger_level = logging.INFO

    def display(self, msg, **kwargs):
        """ Modified to output to logger only.
        """
        if 'screen_only' in kwargs:
            return
        LOG2._log(self.logger_level, msg, args=[])


display = MyDisplay()
__main__.display = display
# END

from ansible import constants as C
from ansible.plugins.callback import CallbackBase
from ansible.executor.playbook_executor import PlaybookExecutor
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play_context import (PlayContext, OPTION_FLAGS, boolean)
from ansible.vars.manager import VariableManager
from ansible.plugins.loader import action_loader, lookup_loader

from f5test.base import OptionsStrict
from f5test.interfaces.testcase import ContextHelper
from f5test.noseplugins.extender.report import nose_selector, test_address
from f5test.noseplugins.extender.ite import ITE_METADATA

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = '.playbooks'
HOST_VARS = 'vars'
GROUP_VARS = 'group_vars'
VAR_F5TEST_CONFIG = 'f5test_config'


# BEGIN MONKEY PATCH
def set_options(self, options):
    '''
    Configures this connection information instance with data from
    options specified by the user on the command line. These have a
    lower precedence than those set on the play or host.
    '''

    # privilege escalation
    self.become = options.become
    self.become_method = options.become_method
    self.become_user = options.become_user

    self.check_mode = boolean(options.check, strict=False)
    self.diff = boolean(options.diff, strict=False)

    #  general flags (should we move out?)
    #  should only be 'non plugin' flags
    for flag in OPTION_FLAGS:
        attribute = getattr(options, flag, False)
        if attribute:
            setattr(self, flag, attribute)

    if hasattr(options, 'timeout') and options.timeout:
        self.timeout = int(options.timeout)

    # get the tag info from options. We check to see if the options have
    # the attribute, as it is not always added via the CLI
    if hasattr(options, 'tags'):
        self.only_tags.clear()
        self.only_tags.update(options.tags)

    if len(self.only_tags) == 0:
        self.only_tags = set(['all'])

    if hasattr(options, 'skip_tags'):
        self.skip_tags.update(options.skip_tags)


PlayContext.set_options = set_options


# END MONKEY PATCH


class JinjaUtils(object):

    def format(self, fmt, iterable):
        return (fmt.format(**x) for x in iterable)

    def format_list(self, fmt, iterable, expand=False):
        if expand:
            return (fmt.format(*x) for x in iterable)
        return (fmt.format(x) for x in iterable)


class MyCallback(CallbackBase):

    def __init__(self, display=None, options=None):
        super(MyCallback, self).__init__(display, options)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        self._plugin_options.failed.append(result)

    def v2_runner_on_unreachable(self, result):
        self._plugin_options.failed.append(result)

    def v2_runner_item_on_failed(self, result):
        self._plugin_options.failed.append(result)

    def v2_runner_on_async_failed(self, result):
        self._plugin_options.failed.append(result)


def run_playbooks(playbook, tags=[], context=None, options=None):
    """
    @param playbook: The playbook(s) to be run.
    @type playbook: str or iterable
    @param tags: Run only plays tagged with these (or)
    @type tags: list
    @param context: The nose context where the playbook(s) will be executed
    @type context: instance
    """

    cfgifc = ContextHelper().get_config()
    LOG.debug('In run_playbooks(%s)...', playbook)

    # Really not liking how variables are called constants and how there are N
    # ways of assigning them.
    C.DEFAULT_ROLES_PATH = [os.path.expanduser('~/.ansible/roles'),
                            os.path.join(HERE, 'roles')]
    C.RETRY_FILES_ENABLED = False
    C.DEFAULT_HASH_BEHAVIOUR = 'merge'
    C.ANSIBLE_PIPELINING = True
    action_loader.add_directory(os.path.join(HERE, 'action_plugins'))
    lookup_loader.add_directory(os.path.join(HERE, 'lookup_plugins'))
    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources='/dev/null')
    variable_manager = VariableManager(loader, inventory)
    o = OptionsStrict(connection='smart', forks=10, become=None,
                      become_method=None, become_user=None, check=False,
                      listhosts=False, listtasks=False, listtags=False,
                      syntax=False, module_path=[os.path.join(HERE, 'library')],
                      diff=False,  # tags=tags,
                      verbosity=1, timeout=1,
                      )

    if options.logger_level:
        display.logger_level = options.pop('logger_level')

    if options:
        o.update(options)

    passwords = dict(vault_pass='secret')
    display.verbosity = o.verbosity

    inventory.add_group('all')
    a = inventory.groups['all']
    a.set_variable(VAR_F5TEST_CONFIG, cfgifc.api)
    a.set_variable('f5test_itemd', {})
    if context:
        tmp = nose_selector(context)
        address = test_address(context)
        a.set_variable('f5test_module', tmp.replace(':', '.'))
        # ITE compatibility: templates can refer to metadata values (e.g. TCID)
        if hasattr(context, ITE_METADATA):
            a.set_variable('f5test_itemd', getattr(context, ITE_METADATA))
        if address[1]:
            name = address[1].rsplit('.')[-1]
            a.set_variable('f5test_module_name', name)
    a.set_variable('playbook_name', os.path.splitext(os.path.basename(playbook))[0])
    for device in cfgifc.get_devices(KIND_ANY):
        prev = a
        name = ''
        for sub_kind in device.kind.bits:
            name += sub_kind
            inventory.add_group(name)
            prev.add_child_group(inventory.groups[name])
            prev = inventory.groups[name]
            name += '.'

        fingerprint = cfgifc.get_session().get_fingerprint(hash=True)
        for tag in tags:
            a.set_variable(tag, True)
        session = cfgifc.get_session()
        a.set_variable('f5test_session', OptionsStrict(name=session.name,
                                                       name_md5=session.name_md5))
        a.set_variable('f5test_respools', session.get_respool_handler().pools)
        a.set_variable('f5test_utils', JinjaUtils())
        a.set_variable('f5test_ranges', session.get_respool_handler().ranges)
        a.set_variable('machine_fingerprint', fingerprint)
        # Colon must mean something for Ansible
        if device.alias != 'localhost':
            inventory.add_host(device.alias, str(device.kind).replace(':', '.'))
        h = inventory.get_host(device.alias)
        h.set_variable('f5test_device', device)
        h.set_variable('f5test_kind', device.kind)
        h.set_variable('f5test_mgmt_address', device.get_address())
        h.set_variable('f5test_port_https', device.ports['https'])
        h.set_variable('f5test_username', device.get_admin_creds().username)
        h.set_variable('f5test_password', device.get_admin_creds().password)
        h.set_variable('ansible_host', device.get_discover_address())
        h.set_variable('ansible_ssh_port', device.ports['ssh'])
        h.set_variable('ansible_user', device.get_root_creds().username)
        h.set_variable('ansible_ssh_pass', device.get_root_creds().password)
        for spec, v in device.specs.get(HOST_VARS, {}).items():
            h.set_variable(spec, v)

        for group in device.groups:
            inventory.add_group(group)
            g = inventory.groups[group]
            a.add_child_group(g)
            g.add_host(h)

    names = [playbook] if isinstance(playbook, str) else playbook

    for g, v in cfgifc.api.get(GROUP_VARS, {}).items():
        group = inventory.groups.get(g)
        if group:
            group.vars.update(v)

    # Look for playbooks relative to caller's base directory
    frame = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    here = os.path.dirname(os.path.abspath(module.__file__))

    playbooks = [x if os.path.isabs(x) else os.path.join(here, FIXTURES_DIR, x)
                 for x in names]

    executor = PlaybookExecutor(
        playbooks=playbooks,
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        options=o,
        passwords=passwords)

    options = OptionsStrict(rc=-1, failed=[])
    cb = MyCallback(options=options)
    executor._tqm._callback_plugins.append(cb)
    try:
        options.rc = executor.run()
    finally:
        shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)

    # p.vips.sync()
    return options
