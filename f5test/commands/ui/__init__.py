import sys
import importlib


class Wrapper(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def __getattr__(self, name):
        if name.startswith('__'):
            return getattr(self.wrapped, name)
        return importlib.import_module(".%s" % name, __package__)

sys.modules[__name__] = Wrapper(sys.modules[__name__])
