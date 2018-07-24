'''
Created on Dec 30, 2017

@author: jono

Ansible connected to Nose.
'''


import inspect
import logging
import os

from f5test.utils.ansible import run_playbooks, FIXTURES_DIR

from . import ExtendedPlugin


LOG = logging.getLogger(__name__)
PLUGIN_NAME = 'ansible'


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


class Ansible(ExtendedPlugin):
    """
    Ansible integration. Enabled by default.
    """
    enabled = True
    name = "ansible"
    score = 520

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--no-ansible', action='store_true',
                          dest='no_ansible', default=False,
                          help="Disable Ansible plugin. (default: no)")

    def configure(self, options, noseconfig):
        super(Ansible, self).configure(options, noseconfig)
        self.enabled = not noseconfig.options.no_ansible

    def startContext(self, context):
        if inspect.ismodule(context):
            basename = os.path.basename(os.path.splitext(context.__file__)[0])
            basedir = os.path.dirname(context.__file__)
            playbook = os.path.join(basedir, FIXTURES_DIR, os.path.extsep.join(
                                    [basename, 'yaml']))
            LOG.debug('Looking for module playbook (%s)', playbook)
            if os.path.isfile(playbook):
                def foo_wrapper(wrapped_func, tags):
                    def _w(*args, **kwargs):
                        try:
                            wrapped_func(*args, **kwargs)
                        finally:
                            LOG.info('Running module playbook=%s tags=%s...' % (playbook, tags))
                            result = run_playbooks(playbook, tags=tags, context=context,
                                                   options=self.options)
                            if result.rc:
                                raise AnsibleError(result)
                    return _w

                setup_func = getattr(context, 'setup_module', lambda: None)
                teardown_func = getattr(context, 'teardown_module', lambda: None)
                setattr(context, 'setup_module', foo_wrapper(setup_func, ['setup']))
                setattr(context, 'teardown_module', foo_wrapper(teardown_func, ['teardown']))

        elif inspect.isclass(context):
            module = inspect.getmodule(context)
            basename = os.path.basename(os.path.splitext(module.__file__)[0])
            basedir = os.path.dirname(module.__file__)
            class_name = context.__name__
            playbook = os.path.join(basedir, FIXTURES_DIR, os.path.extsep.join(
                                    [basename + '@' + class_name, 'yaml']))
            LOG.debug('Looking for class playbook (%s)', playbook)
            if os.path.isfile(playbook):
                def foo_wrapper(wrapped_func, tags):
                    wrapped_func = wrapped_func.__func__

                    def _w(*args, **kwargs):
                        try:
                            wrapped_func(*args, **kwargs)
                        finally:
                            LOG.info('Running class playbook=%s tags=%s...' % (playbook, tags))
                            result = run_playbooks(playbook, tags=tags, context=context,
                                                   options=self.options)
                            if result.rc:
                                raise AnsibleError(result)
                    return classmethod(_w)

                setup_func = getattr(context, 'setup_class',
                                     classmethod(lambda cls: None))
                teardown_func = getattr(context, 'teardown_class',
                                        classmethod(lambda cls: None))
                setattr(context, 'setup_class', foo_wrapper(setup_func, ['setup']))
                setattr(context, 'teardown_class', foo_wrapper(teardown_func, ['teardown']))
