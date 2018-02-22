from ...base import Macro
from ..base import PARTITION_COMMON
from ..net import RouteDomain
from ..scaffolding import make_partitions


class BaseConfig(Macro):
    def __init__(self, context, tree=None, folder=None, route_domain=None):
        self.context = context
        self.tree = tree or make_partitions(count=0, context=context)
        self.common = tree[PARTITION_COMMON]
        self.folder = folder if folder is not None else self.common
        self.route_domain = route_domain or RouteDomain(0)
        super(BaseConfig, self).__init__()
