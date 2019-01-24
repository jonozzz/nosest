'''
Created on Mar 16, 2013

@author: jono
'''
from ...base import Interface, Options, Kind
from ...defaults import ADMIN_PASSWORD, ADMIN_USERNAME, ROOT_PASSWORD, \
    ROOT_USERNAME, DEFAULT_PORTS, KIND_TMOS, KIND_ANY
from ...compat import _bool
from ...utils import net
from ...utils.dicts import inverse
import copy
from fnmatch import fnmatch
import logging
import os
import time
from hashlib import md5
from .respool import RespoolFactory
import platform as p
import uuid
from functools import reduce

LOG = logging.getLogger(__name__)
STDOUT = logging.getLogger('stdout')
REACHABLE_HOST = 'f5.com'
KEYSET_DEFAULT = 0
KEYSET_COMMON = 1
KEYSET_LOCK = 2
KEYSET_ALL = 3

ADMIN_ROLE = 0
ROOT_ROLE = 1
DEFAULT_ROLE = 2

CFG_DEVICES = 'devices'
CFG_SELENIUM = 'selenium'
CFG_SESSION = '_session'

class ConfigError(Exception):
    """Base exception for all exceptions raised in module config."""
    pass


class DeviceDoesNotExist(ConfigError):
    """Device alias requested doesn't exist."""
    pass


def expand_devices(specs, section=CFG_DEVICES):
    devices = []
    cfgifc = ConfigInterface()
    all_devices = sorted(cfgifc.get_devices(kind=KIND_ANY),
                         key=lambda x: x.alias)
    aliases = specs.get(section) if isinstance(specs, dict) else specs
    aliases = [aliases] if isinstance(specs, str) else aliases
    if aliases is None:
        return
    for device in aliases:
        if device == '^all':  # Backward compatibility and deprecated
            all_tmos = sorted(cfgifc.get_devices(kind=KIND_TMOS),
                              key=lambda x: x.alias)
            devices.extend(all_tmos)
            break
        devices.extend([x for x in all_devices if fnmatch(x.alias, device)])
    return devices


class DeviceCredential(object):

    def __init__(self, username, password):
        """
        @param username: The username
        @type username: str
        @param password: The password
        @type password: str
        """
        self.username = username
        self.password = password

    def __repr__(self):
        return "%s:%s" % (self.username, self.password)

    def __hash__(self):
        return hash((self.username, self.password))

    def __eq__(self, other):
        return self.username == other.username and self.password == other.password


class DeviceAccess(object):

    def __init__(self, address, credentials=None, alias=None, specs=None):
        self.address = address
        self.credentials = credentials
        self.alias = alias
        self.specs = specs or Options()
        self.tags = set([])
        self.groups = set([])
        self.hostname = self.specs.get('address')
        self.discover_address = self.specs.get('discover address')
        self.set_tags(self.specs.get('tags'))
        self.set_groups(self.specs.get('groups'))
        self.ports = copy.copy(DEFAULT_PORTS)
        self.ports.update(self.specs.get('ports', {}))
        self.specs.setdefault('_keyset', KEYSET_COMMON)
        self.kind = Kind(self.specs.get('kind', KIND_TMOS))
        self.specs.setdefault('enabled', True)

    def __repr__(self):
        return "%s:%s" % (self.alias, self.address)

    def __cmp__(self, other):
        return cmp(self.address, other.address)

    def __hash__(self):
        return hash((self.alias, self.address))

    @property
    def instances(self):
        return expand_devices(self.specs, 'instances')

    @property
    def enabled(self):
        return self.specs.enabled

    @enabled.setter
    def enabled(self, value):
        self.specs.enabled = bool(value)

    def is_default(self):
        return _bool(self.specs.get('default'))

    def get_by_username(self, username):
        for cred in list(self.credentials.values()):
            if cred.username == username:
                return cred

    def get_creds(self, role=DEFAULT_ROLE, keyset=None):
        creds = self.credentials[role]
        if keyset == KEYSET_ALL:
            return creds
        if keyset is None:
            keyset = self.specs._keyset

        if keyset == KEYSET_LOCK:
            return creds.lock or creds.common or creds.default
        elif keyset == KEYSET_COMMON:
            return creds.common or creds.default
        else:
            return creds.default

    def get_admin_creds(self, *args, **kwargs):
        return self.get_creds(role=ADMIN_ROLE, *args, **kwargs)

    def get_root_creds(self, *args, **kwargs):
        return self.get_creds(role=ROOT_ROLE, *args, **kwargs)

    def get_address(self):
        return self.address

    def get_discover_address(self):
        return self.discover_address or self.address

    def get_hostname(self):
        return self.hostname

    def get_alias(self):
        return self.alias

    def set_tags(self, tags):
        if isinstance(tags, (str, int)):
            self.tags = self.tags.union([tags])
        elif isinstance(tags, (list, tuple, set)):
            self.tags = self.tags.union(tags)

    def set_groups(self, groups):
        if isinstance(groups, (str, int)):
            self.groups = self.groups.union([groups])
        elif isinstance(groups, (list, tuple, set)):
            self.groups = self.groups.union(groups)


class Session(object):

    def __init__(self, config):
        self.config = config
        self.level1 = time.strftime("%Y%m%d")
        self.level2 = "{0}-{1}".format(time.strftime("%H%M%S"), os.getpid())
        self.name = "%s-%s" % (self.level1, self.level2)
        session = os.path.join('session-%s' % self.level1, self.level2)
        self.session = session
        self.name_md5 = md5(self.name.encode()).hexdigest()
        self.respool_handler = None

        if self.config.paths and self.config.paths.logs:
            path = os.path.join(self.config.paths.logs, session)
            path = os.path.expanduser(path)
            path = os.path.expandvars(path)
            self.path = path
        else:
            self.path = None

    def get_url(self, local_ip=None, test=None):
        # local_ip = net.get_local_ip(peer)
        if not local_ip:
            local_ip = net.get_local_ip(REACHABLE_HOST)
        if self.config.paths and self.config.paths.sessionurl:
            url = self.config.paths.sessionurl % dict(runner=local_ip,
                                                      session=self.session)
            if test:
                url += ('/%s' % test.id()).replace(':', '@')
            return url

    def get_harness_id(self):
        if self.config.testrun and self.config.testrun.harness:
            return self.config.testrun.harness
        else:
            if self.config.devices:
                return md5(''.join(sorted([x.address for x in list(self.config.devices.values())
                                           if _bool(x.enabled)]))).hexdigest()

    def get_respool_handler(self):
        if not self.respool_handler:
            machine_id = self.get_fingerprint(True)
            self.respool_handler = RespoolFactory(self.config.memcache, machine_id)
        #self.config.respool = self.respool_handler.hook
        return self.respool_handler

    def get_fingerprint(self, hash=False):
        """
        Fingerprint of the current operating system/platform.
        If md5 is True, a digital fingerprint is returned.
        """
        sb = []
        sb.append(p.node())
        sb.append(p.architecture()[0])
        sb.append(p.architecture()[1])
        sb.append(p.machine())
        sb.append(p.processor())
        sb.append(p.system())
        sb.append(str(uuid.getnode()))    # MAC address
        text = '#'.join(sb)
        if hash:
            return md5(text.encode()).hexdigest()
        else:
            return text


class ConfigInterface(Interface):

    def __init__(self, data=None, loader=None):
        from .driver import CONFIG

        if data:
            self.config = data
        elif loader:
            self.config = loader.load()
        else:
            self.config = getattr(CONFIG, 'data', None)
            if self.config is None:
                LOG.debug('No global test config found.')
                self.config = Options()
                setattr(CONFIG, 'data', self.config)

        super(ConfigInterface, self).__init__()

    def __repr__(self):
        name = self.__class__.__name__
        return "<{0}>".format(name, self)

    def get_config(self):
        return self.config

    def set_global_config(self):
        from .driver import CONFIG

        setattr(CONFIG, 'data', self.get_config())

    def open(self):  # @ReservedAssignment
        self.api = self.get_config()
        return self.api

    def copy(self):
        config = dict((k, v) for k, v in list(self.api.items()) if k != CFG_SESSION)
        return config

    def get_default_key(self, collection):
        if not collection:
            return
        _ = list([x for x in list(collection.items()) if _bool(x[1] and x[1].get('default'))])
        return _[0][0] if _ else Options()

    def get_default_value(self, collection):
        return list([x for x in list(collection.values()) if _bool(x.get('default'))])[0]

    def _get_roles(self, specs):
        default = Options()
        default.default = DeviceCredential(specs.get('username'),
                                           specs.get('password'))

        admin = Options()
        admin.default = DeviceCredential(ADMIN_USERNAME, ADMIN_PASSWORD)
        admin.common = DeviceCredential(specs.get('admin username',
                                                  admin.default.username),
                                        specs.get('admin password',
                                                  admin.default.password))
        admin.lock = DeviceCredential(specs.get('lock admin username',
                                                admin.common.username),
                                      specs.get('lock admin password',
                                                admin.common.password))

        root = Options()
        root.default = DeviceCredential(ROOT_USERNAME, ROOT_PASSWORD)
        root.common = DeviceCredential(specs.get('root username',
                                                 root.default.username),
                                       specs.get('root password',
                                                 root.default.password))
        root.lock = DeviceCredential(specs.get('lock root username',
                                               root.common.username),
                                     specs.get('lock root password',
                                               root.common.password))

        return {ADMIN_ROLE: admin, ROOT_ROLE: root, DEFAULT_ROLE: default}

    def get_device(self, device=None):
        if isinstance(device, DeviceAccess):
            return device

        if device is None:
            device = self.get_default_key(self.config.get(CFG_DEVICES))
            if not device:
                LOG.debug("No default device found. Check your test configuration.")
                return

        try:
            specs = self.config[CFG_DEVICES][device]
            if not specs:
                return
        except KeyError:
            raise DeviceDoesNotExist(device)

        roles = self._get_roles(specs)
        return DeviceAccess(specs['address'], credentials=roles, alias=device,
                            specs=specs)

    def set_default_device(self, device):
        current = self.get_device()
        if current:
            current.specs['default'] = False
        device.specs['default'] = True
        return current

    def get_device_by_address(self, address):
        for device in self.get_devices():
            if device.address == address or device.discover_address == address:
                return device
        LOG.warning('A device with address %s was NOT found in the configuration!', address)

    def get_device_address(self, device):
        device_access = self.get_device(device)
        return device_access.address

    def get_devices(self, kind=KIND_TMOS, only_enabled=True):
        if not self.config.get(CFG_DEVICES):
            raise StopIteration
        for device in self.config[CFG_DEVICES]:
            device = self.get_device(device)
            if device.kind == kind and (not only_enabled or device.enabled):
                yield device

    def get_device_groups(self, devices=None):
        if devices is None:
            devices = self.get_devices()
        return inverse(dict((x, x.groups) for x in devices if x.groups))

    @staticmethod
    def get_devices_instances(devices):
        return reduce(set.union, [x.instances for x in devices])

    def get_selenium_head(self, head=None):
        if CFG_SELENIUM not in self.config:
            return head, Options()

        if head is None:
            head = self.get_default_key(self.config[CFG_SELENIUM])

        return head, self.config[CFG_SELENIUM][head]

    def get_session(self):
        if not self.config._session:
            self.config[CFG_SESSION] = Session(self.config)
        return self.config[CFG_SESSION]

    def get_respool(self, name):
        pools = self.get_session().get_respool_handler().pools
        pool = pools.get(name)
        if hasattr(pool, 'sync'):
            pool.sync()
        return pool

    def get_respools(self):
        pools = self.get_session().get_respool_handler().pools
        for pool in list(pools.values()):
            if hasattr(pool, 'sync'):
                pool.sync()
        return pools

    def get_ranges(self):
        return self.get_session().get_respool_handler().ranges
