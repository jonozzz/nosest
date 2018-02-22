from ..scaffolding import Stamp, Literal
import logging
import os
from ....base import enum
from ....utils.parsers import tmsh
from ....utils.parsers.tmsh import RawEOL

LOG = logging.getLogger(__name__)


class LargeStamp(Stamp):

    def __init__(self):
        filename = "{}.tmpl".format(self.name)
        with open(os.path.join(os.path.dirname(__file__), filename)) as f:
            self.TMSH = f.read()
        super(LargeStamp, self).__init__()

    def _cache_key(self, name):
        klass = type(self)
        return "_%d_%s_%s" % (hash(klass), name, self.name)


class iApp(LargeStamp):
    #TMSH = "f5.microsoft_exchange_2010_2013_cas.v1.2.0.tmpl"
    TMSH = None

    def __init__(self, name='f5.microsoft_exchange_2010_2013_cas.v1.2.0'):
        self.name = name
        super(iApp, self).__init__()

    def tmsh(self, obj):
        key = self.get_full_path()
        # partition = self.folder.partition().name
        value = obj.format(key=key, _maxdepth=1)
        return key, value
