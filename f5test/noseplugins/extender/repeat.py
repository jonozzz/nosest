'''
Created on Feb 20, 2014

@author: jono
'''
from __future__ import absolute_import
from . import ExtendedPlugin
from ...interfaces.config import ConfigError
from nose.case import Test
from nose.suite import ContextSuite, LazySuite
from nose.failure import Failure
import itertools
import logging
import datetime
import re

LOG = logging.getLogger(__name__)
ATTR = '_repeat'


def repeat(times=None, seconds=None):
    def _my_decorator(f):
        attrs = {}
        if times:
            attrs.update(times=times)
        if seconds:
            attrs.update(seconds=seconds)
        setattr(f, ATTR, attrs)
        return f
    return _my_decorator


class Repeat(ExtendedPlugin):
    """
    Repeat a test plugin. Enabled by default.
    """
    enabled = True
    name = "repeat"
    score = 520

    def options(self, parser, env):
        """Register commandline options."""
        parser.add_option('--no-repeat', action='store_true',
                          dest='no_repeat', default=False,
                          help="Disable Repeat plugin. (default: no)")

    def configure(self, options, noseconfig):
        """ Call the super and then validate and call the relevant parser for
        the configuration file passed in """
        super(Repeat, self).configure(options, noseconfig)
        self.options = options
        if not options.no_repeat:
            # Monkey patch Test.__call__ to handle @repeat decorated tests.
            def __call__(self, result, blocking_context=None):
                attrs = {}
                self._repeat = attrs
                if isinstance(self, Test):
                    testMethod = getattr(self.test, self.test._testMethodName)
                    attrs = getattr(testMethod, ATTR, {})
                elif isinstance(self, ContextSuite):
                    if self.context:
                        attrs = getattr(self.context, ATTR, {})
                #else:
                #    return self.run(result, blocking_context)
                if isinstance(self, (Test, ContextSuite)):
                    for k, v in options.items():
                        if self.context and self.context != Failure:
                            id_ = self.id()
                        else:
                            id_ = None

                        if id_ and re.match('^%s$' % k, id_):
                            attrs.update(v)
                if not any(attrs):
                    return self.run(result, blocking_context)
                else:
                    if len(attrs) > 1:
                        raise ConfigError('times and seconds are mutually exclusive (%s)' % attrs)

                id_ = self.id()
                self._repeat.update(attrs)
                times = attrs.get('times') or -1
                end = datetime.datetime.now() + datetime.timedelta(seconds=attrs.get('seconds') or -1)
                ret = i = 0
                if isinstance(self, ContextSuite):
                    def _get_wrapped_tests(self):
                        if self._repeat.get('times'):
                            times = self._repeat['times']
                            _ = itertools.repeat(list(self._get_wrapped_tests()),
                                                 times)
                            for test in itertools.chain.from_iterable(_):
                                yield test
                        elif self._repeat.get('seconds'):
                            end = datetime.datetime.now() + \
                                datetime.timedelta(seconds=self._repeat['seconds'] or -1)
                            for test in itertools.cycle(self._get_wrapped_tests()):
                                if datetime.datetime.now() < end:
                                    yield test
                                else:
                                    break
                        else:
                            for test in self._get_wrapped_tests():
                                yield test

                    _tests = property(_get_wrapped_tests, LazySuite._set_tests, None,
                                      "Wrap the _tests getter yet again...")

                    # Ugly!
                    tmp = ContextSuite._tests
                    try:
                        ContextSuite._tests = _tests
                        ret = self.run(result, blocking_context)
                    finally:
                        ContextSuite._tests = tmp
                else:
                    while i < times or datetime.datetime.now() < end:
                        ret = self.run(result, blocking_context)
                        i += 1
                        if blocking_context:
                            break
                return ret
            Test.__call__ = __call__
            ContextSuite.__call__ = __call__
