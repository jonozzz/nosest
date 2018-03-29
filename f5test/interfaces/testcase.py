from ..base import TestCase, Options
import datetime
import logging
import os
import re
import fnmatch
import time
from unittest.case import _AssertRaisesContext
from hashlib import md5
import threading

THREAD_STORAGE = threading.local()


INTERFACES_CONTAINER = 'interfaces'
# This container is used by logcollect plugin to copy extra files needed for
# troubleshooting in case of a failure/error. The format is expected to be:
# To copy files from a remote device.
# <filename>: (<SSHInterface instance>, <remote_file_path>)
# OR
# <filename>: <local_file_path>
# To copy from the local file system.
LOGCOLLECT_CONTAINER = 'logcollect'
DEFAULT_CONTAINER = '__main__'
LOG = logging.getLogger(__name__)


class FakeAssertionError(object):

    def __init__(self, msg):
        self.msg = msg

    def __call__(self, *args, **kwargs):
        return AssertionError(self.msg)


class AssertRaisesContext(_AssertRaisesContext):
    """A context manager used to implement TestCase.assertRaises* methods."""

    def __init__(self, expected, test_case, expected_regexp=None, msg=None):
        super(AssertRaisesContext, self).__init__(expected, test_case, expected_regexp)
        if msg:
            self.failureException = FakeAssertionError(msg)


class InterfaceHelper(object):
    """
    Provides a few helper methods that will make the interface handling
    easier and also data sharing between contexts. This class may be used
    stand-alone or subclassed by a TestCase class.
    """
    def _setup(self, name):
        """
        Initializes the class. The main reason why this is not called
        __init__ is because it would collide with TestCase class' __init__.

        :param name: The context name (usually the test name/id).
        :type name: string
        """
        if getattr(THREAD_STORAGE, '_attrs', None) is None:
            THREAD_STORAGE._attrs = Options()
        self._config = THREAD_STORAGE._attrs
        self._name = name

    def _teardown(self):
        """
        Closes every interface opened in the current context only! This method
        should be called from a teardown* method, __exit__ method of a context
        manager or a finally block.
        """
        for name, interface in self.get_container(container=INTERFACES_CONTAINER,
                                                  exact=True).items():
            interface.close()
            self.unset_data(name, container=INTERFACES_CONTAINER)

        if self._name in self._config:
            del self._config[self._name]

    def _clear(self):
        """
        WARNING: This clears *ALL* contexts, not only the current one.
        """
        if isinstance(self._config, dict):
            self._config.clear()

    def unique(self, prefix, use_time=False):
        session = self.get_config().get_session().session
        digest = md5(session)
        digest.update(self._name)
        if use_time:
            digest.update(str(time.time()))
        return ('%s-%s' % (prefix, digest.hexdigest()))

    def set_data(self, key, data=None, container='default', overwrite=False):
        """
        Sets a name=value for the current context, just like you'd do with a
        dictionary. Each context may have multiple containers. The default
        container is meant to be used for storing user data. Other containers
        may be used to avoid key collision with user data.

        :param key: The key (or name) of the mapping.
        :param data: The value (or data) of the mapping.
        :param container: Container name.
        :param overwrite: Try to find if there is another value for the given
            key in a parent container. If found it'll use that container
            to overwrite the value.
        """
        if overwrite:
            bits = self._name.split('.')
            for i in range(len(bits)):
                name = '.'.join(bits[:len(bits) - i])
                if name in self._config and key in self._config[name].get(container, {}):
                    break
            else:
                name = self._name
        else:
            name = None
        container = self.set_container(container, name)
        container[key] = data

    def get_data(self, key, container='default'):
        """
        Retrieve the data stored by set_data().

        Example:
        Current context is 'context.level.1.1'.

        context.level.1:
            foo=bar (container=default)
            foo=bar2 (container=other)
            foo2=masked (container=default)
        context.level.1.1:
            foo2=barbar (container=default)

        >>> get_data('foo')
        bar
        >>> get_data('foo', container='other')
        bar2
        >>> get_data('foo2')
        barbar

        :param key: The key (or name) of the mapping.
        :param container: Container name.
        """
        data = self.get_container(container)
        if isinstance(data, dict):
            return data.get(key)

    def set_stat_counter(self, owner, value):
        container = self.set_container('statistics', self._name)
        array = container.setdefault(owner, [])
        array.append(dict(time=datetime.datetime.utcnow(), value=value))

    def get_stat_counter(self, owner=None):
        container = self.set_container('statistics', self._name)
        if owner is None:
            return container
        else:
            return container.get(owner, [])

    def extend_stats(self, other):
        container = self.set_container('statistics', self._name)
        for owner, stats in other.get_stat_counter().items():
            array = container.setdefault(owner, [])
            array.extend(stats)

    def set_container(self, container='default', name=None):
        """
        Create an empty container or return an existing one.
        """
        if name is None:
            name = self._name
        root = self._config.setdefault(name, Options())
        return root.setdefault(container, Options())

    def get_container(self, container='default', exact=False):
        """
        Returns a *volatile* dictionary of a container built hierarchically from
        parent containers.

        :param container: Container name.
        :param exact: Allow values defined in parent contexts to be included in
        child contexts.
        :type exact: bool
        """
        i = pos = 0
        my_id = self._name
        data = Options()
        while pos != -1:
            if exact:
                pos = -1
            else:
                pos = my_id.find('.', i)

            if pos > 0:
                parent = my_id[:pos]
            else:
                parent = my_id

            for key in self._config.keys():
                if fnmatch.fnmatchcase(parent, key):
                    load = self._config.get(key)
                    if load and container in load and \
                       isinstance(load[container], dict):
                        data.update(load[container])
            i = pos + 1
        return data

    def unset_data(self, key, container='default'):
        """
        Delete a mapping from a container by its key.
        """
        root = self._config.setdefault(self._name, Options())
        container = root.setdefault(container, Options())
        del container[key]

    def get_interface(self, klass, reuse=True, *args, **kwargs):
        """
        Get a previously stored interface or create a new one. If the optional
        parameter name is given then the created interface will be stored as a
        mapping with that name. Interface specific arguments can be passed in
        *args and **kwargs.

        :param name_or_class: The interface class or name (given as a string)
        :type name_or_class: a subclass of Interface or a string
        :param name:  The name to be used when storing this newly created
        interface instance.
        :type name: string
        """
        if isinstance(klass, basestring):
            raise ValueError(klass)

        interface = klass(*args, **kwargs)
        name = repr(interface)
        found = False
        if reuse:
            previous = self.get_data(name, container=INTERFACES_CONTAINER)
            if previous:
                interface = previous
                found = True
            if not interface.is_opened():
                interface.open()

            if not found:
                self.set_data(name, interface, container=INTERFACES_CONTAINER)
        else:
            interface.open()
            name = id(interface)

        return interface

    def get_config(self, *args, **kwargs):
        from .config import ConfigInterface
        return self.get_interface(ConfigInterface, *args, **kwargs)

    def get_selenium(self, *args, **kwargs):
        """
        Historically get_selenium() would be called from the majority of tests
        without any arguments, in which case it should reuse a previously opened
        SeleniumInterface shared by all UI tests.

        As things got reworked in this class, the name/signature of these
        methods became obsolete.
        """
        from .selenium import SeleniumInterface
        return self.get_interface(SeleniumInterface, *args, **kwargs)

    def get_ssh(self, *args, **kwargs):
        from .ssh import SSHInterface
        return self.get_interface(SSHInterface, *args, **kwargs)

    def get_icontrol(self, new_session=False, *args, **kwargs):
        from .icontrol import IcontrolInterface
        ifc = self.get_interface(IcontrolInterface, *args, **kwargs)
        if new_session:
            ifc.set_session()
        return ifc

    def get_em(self, *args, **kwargs):
        from .icontrol import EMInterface
        return self.get_interface(EMInterface, *args, **kwargs)

    def get_rest(self, *args, **kwargs):
        from .rest import RestInterface
        return self.get_interface(RestInterface, *args, **kwargs)

    def get_icontrol_rest(self, *args, **kwargs):
        from .rest.emapi import EmapiInterface
        return self.get_interface(EmapiInterface, *args, **kwargs)

    def get_icontrol_rest2(self, *args, **kwargs):
        from .icr import IcontrolRestInterface
        return self.get_interface(IcontrolRestInterface, *args, **kwargs)

    def get_snmp(self, *args, **kwargs):
        from .snmp import SnmpInterface
        return self.get_interface(SnmpInterface, *args, **kwargs)

    def get_aws(self, *args, **kwargs):
        from .aws import AwsInterface
        return self.get_interface(AwsInterface, *args, **kwargs)

    def get_apic(self, *args, **kwargs):
        from .rest.apic import ApicInterface
        return self.get_interface(ApicInterface, *args, **kwargs)

    def get_netx(self, *args, **kwargs):
        from .rest.netx import NetxInterface
        return self.get_interface(NetxInterface, *args, **kwargs)


class ContextHelper(InterfaceHelper):

    def __init__(self, name=DEFAULT_CONTAINER):
        self.name = name
        self._setup(name)

    def teardown(self):
        self._teardown()
    
    def __enter__(self):
        self._setup(self.name)
        return self

    def __exit__(self, type, value, traceback):  # @ReservedAssignment
        self._teardown()


class InterfaceTestCase(InterfaceHelper, TestCase):
    """
    A TestCase subclass that brings the functionality of the InterfaceHelper
    class to each test case method.
    """
    @classmethod
    def setup_class(cls):
        name = "%s.%s" % (cls.__module__, cls.__name__)
        context = ContextHelper(name)
        # This is here for backwards compatibility
        cls.ih = context
        cls._context = context

    @classmethod
    def teardown_class(cls):
        cls.ih.teardown()

    def setUp(self, *args, **kwargs):
        self._setup(self.id())

        super(TestCase, self).setUp(*args, **kwargs)

    def tearDown(self, *args, **kwargs):
        self._teardown()

        super(TestCase, self).tearDown(*args, **kwargs)

    def assertRaises(self, excClass, callableObj=None, *args, **kwargs):
        """Add the msg argument. This will mask any 'msg' argument that is
        passed to the callableObj, in that case the workaround is to use the
        context form:

        with self.assertRaises(SomeException, msg='yay!'):
            do_something(msg='some msg')

        """
        msg = kwargs.pop('msg', None)
        context = AssertRaisesContext(excClass, self, msg=msg)
        if callableObj is None:
            return context
        with context:
            callableObj(*args, **kwargs)

    def assertRaisesRegexp(self, expected_exception, expected_regexp,
                           callable_obj=None, *args, **kwargs):
        """Add the msg argument"""
        msg = kwargs.pop('msg', None)
        if isinstance(expected_regexp, basestring):
            expected_regexp = re.compile(expected_regexp)
        context = AssertRaisesContext(expected_exception, self, expected_regexp,
                                      msg)
        if callable_obj is None:
            return context
        with context:
            callable_obj(*args, **kwargs)

    def session_file(self, name, mode='w'):
        cfgifc = self.get_config()
        path = os.path.join(cfgifc.get_session().path, self.id())

        if path and not os.path.exists(path):
            oldumask = os.umask(0)
            os.makedirs(path)
            os.umask(oldumask)

        return open(os.path.join(path, name), mode)
