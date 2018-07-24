'''
Created on Mar 29, 2018

@author: jono
'''

import pytest
from ..utils.convert import to_bool
from ..base import AttrDict
from ..utils.ansible import run_playbooks, FIXTURES_DIR
import os


def __run_ansible_playbooks(request, source=None):
    if source:
        basename = '__init__'
        basedir = os.path.dirname(source)
    else:
        basename = request.fspath.purebasename
        basedir = request.fspath.dirname
    playbook = os.path.join(basedir, FIXTURES_DIR, os.path.extsep.join(
        [basename, 'yaml']))
    plugin = request.config.pluginmanager.get_plugin('ansible-plugin')
    if plugin.enabled and os.path.isfile(playbook):
        print(('Running module playbook=%s setup...' % (playbook,)))
        result = run_playbooks(playbook, tags=['setup'], context=request,
                               options=plugin.options)
        if result.rc:
            raise AnsibleError(result)

    yield

    if plugin.enabled and os.path.isfile(playbook):
        print(('Running module playbook=%s teardown...' % (playbook,)))
        result = run_playbooks(playbook, tags=['teardown'], context=request,
                               options=plugin.options)
        if result.rc:
            raise AnsibleError(result)


@pytest.fixture(scope='module', autouse=True)
def __module_ansible_playbooks(request):
    from f5test.pytestplugins.ansible import __run_ansible_playbooks
    for item in __run_ansible_playbooks(request):
        yield item


class AnsibleError(Exception):

    def __init__(self, result):
        self.result = result

    def __str__(self):
        if len(self.result.failed) == 0:
            msg = "Errors found while playing playbook:\n".format(len(self.result.failed))
        else:
            msg = "Found {} errors while playing playbook:\n".format(len(self.result.failed))
        tpl = """Host/Task: {}/{}\n{}\n"""

        def get_exc(x):
            if 'exception' in x._result:
                return x._result['exception'] + x._result['msg']
            elif 'module_stderr' in x._result:
                return x._result['module_stderr'] + x._result['msg']
            else:
                return x._result.get('reason') or x._result.get('msg')
        msg += "\n".join([tpl.format(x._host, x.task_name, get_exc(x))
                         for x in self.result.failed])
        return msg


class Plugin(object):
    """
    .
    """
    def __init__(self, config):
        self.config = config
        if hasattr(config, '_tc') and config._tc.plugins:
            self.options = config._tc.plugins.ansible or AttrDict()
            self.enabled = to_bool(self.options.enabled)
        else:
            self.enabled = False

    # @pytest.fixture(scope='module', autouse=True)
    # def __look_for_ansible(self, request, respool):
    #     #vip = respool.vips.get()
    #     basename = request.fspath.purebasename
    #     basedir = request.fspath.dirname
    #     playbook = os.path.join(basedir, FIXTURES_DIR, os.path.extsep.join(
    #         [basename, 'yaml']))
    #     if os.path.isfile(playbook):
    #         print('Running module playbook=%s setup...' % (playbook,))
    #         result = run_playbooks(playbook, tags=['setup'], context=request,
    #                                options=self.options)
    #         if result.rc:
    #             raise AnsibleError(result)
    #
    #     yield
    #
    #     if os.path.isfile(playbook):
    #         print('Running module playbook=%s teardown...' % (playbook,))
    #         result = run_playbooks(playbook, tags=['teardown'], context=request,
    #                                options=self.options)
    #         if result.rc:
    #             raise AnsibleError(result)

        #respool.vips.free(vip)


def pytest_configure(config):
    config.pluginmanager.register(Plugin(config), 'ansible-plugin')
