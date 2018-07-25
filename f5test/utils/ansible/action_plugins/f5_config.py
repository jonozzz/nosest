'''
Created on Jan 16, 2018

@author: jono
'''
from ansible.plugins.action import ActionBase
from f5test.base import Options
from f5test.macros.tmosconf.placer import (ConfigPlacer, DNS_SERVERS,
                                           DNS_SUFFIXES, NTP_SERVERS,
                                           DEFAULT_PARTITIONS, DEFAULT_NODE_START,
                                           DEFAULT_NODES, DEFAULT_POOLS,
                                           DEFAULT_MEMBERS, DEFAULT_VIPS)
from f5test.macros.tmosconf.scaffolding import make_partitions, Partition
from f5test.utils.parsers.tmsh import RawEOL
from f5test.utils.dicts import replace
from f5test.utils.ansible import VAR_F5TEST_CONFIG
import importlib
import logging

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

LOG = logging.getLogger(__name__)


class TmosConfig(ConfigPlacer):

    def __init__(self, address, specs, *args, **kwargs):
        self.specs = specs

        options = Options(ssh_port=int(specs.get('ssh_port', 22)),
                          ssl_port=int(specs.get('ssl_port', 443)),
                          partitions=int(specs.get('partitions', DEFAULT_PARTITIONS)),
                          node_start=specs.get('node_start', DEFAULT_NODE_START),
                          node_count=int(specs.get('node_count', DEFAULT_NODES)),
                          pool_count=int(specs.get('pool_count', DEFAULT_POOLS)),
                          pool_members=int(specs.get('pool_members', DEFAULT_MEMBERS)),
                          vip_start=specs.get('vip_start'),
                          vip_count=int(specs.get('vip_count', DEFAULT_VIPS)),
                          username=specs.get('username'),
                          password=specs.get('password'),
                          license=specs.get('license'),
                          provision=specs.get('provision'),
                          clean=specs.get('clean', False),
                          timeout=specs.get('timeout'),
                          verify=specs.get('verify'),
                          verbose=specs.get('verbose'),
                          hostname=specs.get('hostname'),
                          mgmtip=specs.get('mgmtip'),
                          mgmtgw=specs.get('mgmtgw'),
                          selfip_internal=specs.get('selfip_internal'),
                          selfip_external=specs.get('selfip_external'),
                          vlan_internal_name=specs.get('vlan_internal_name',
                                                       'internal'),
                          vlan_external_name=specs.get('vlan_external_name',
                                                       'external'),
                          vlan_internal=specs.get('vlan_internal'),
                          vlan_external=specs.get('vlan_external'),
                          irack_address=specs.get('irack_address'),
                          irack_username=specs.get('irack_username'),
                          irack_apikey=specs.get('irack_apikey'),
                          no_irack=specs.get('no_irack', False),
                          force_license=specs.get('force_license', False),
                          license_only=specs.get('license_only', False)
                          )
        super(TmosConfig, self).__init__(options, address, *args, **kwargs)

    def setup_with_classes(self):
        provider = Options()
        if not self.options.no_irack and not self.options.csv:
            LOG.info("Using data from iRack")
            provider = self.irack_provider(address=self.options.irack_address,
                                           username=self.options.irack_username,
                                           apikey=self.options.irack_apikey,
                                           mgmtip=self.address,
                                           timeout=self.options.timeout)
        elif self.options.csv:
            LOG.info("Using data from CSV: %s" % self.options.csv)
            provider = self.csv_provider(mgmtip=self.address)

        ctx = self.make_context()
        tree = make_partitions(count=0, context=ctx)

        # System
        o = Options(context=ctx)
        o.tree = tree
        o.partitions = self.options.partitions
        o.nameservers = DNS_SERVERS if self.options.dns_servers is None else \
            self.options.dns_servers
        o.suffixes = DNS_SUFFIXES if self.options.dns_suffixes is None else \
            self.options.dns_suffixes
        o.ntpservers = NTP_SERVERS if self.options.ntp_servers is None else \
            self.options.ntp_servers
        o.smtpserver = 'mail'
        o.hostname = self.options.hostname
        o.timezone = self.options.timezone
        self.set_networking(o)
        self.set_provisioning(o)
        self.set_users(o)
        self.SystemConfig(**o).run()

        if not self.options.stdout:
            # XXX: Add any given DNS before attempting to relicense.
            # Licensing may need to resolve the license server hostname.
            if self.can.tmsh(ctx.version):
                self.call('tmsh modify sys dns name-servers add { %s }' % ' '.join(o.nameservers))
            self.license(ctx, self.options.license or provider and provider.licenses.reg_key[0])
            if self.options.license_only:
                return

        if self.options.clean:
            self.load_default_config()
            self.ready_wait()

        if not self.options.stdout:
            self.ready_wait()
            self.load(tree, ctx, func=lambda x: not isinstance(x, Partition))
            self.ready_wait()

        if self.options.clean:
            self.reset_trust()
            return

        for dict_items in self.specs.get('classes', []):
            klass_path, specs = list(dict_items.items())[0]
            path, klass_name = klass_path.rsplit('.', 1)
            module = importlib.import_module('f5test.macros.tmosconf.%s' % path,
                                             __package__)
            klass = getattr(module, klass_name, None)
            if klass is None:
                LOG.warning('%s was not found', klass_path)
                continue

            o = Options(context=ctx)
            o.tree = tree
            specs = replace(specs, old=None, new=RawEOL)

            o.update(specs)
            LOG.debug("%s %s", klass, o)
            tree = klass(**o).run()

        LOG.info("Call ready_wait again to make sure the device is ready")
        self.ready_wait()
        self.load(tree, ctx)
        if not self.options.verify:
            self.reset_trust()
            self.ready_wait()

            self.save(ctx)
            self.ssh_key_exchange()
            self.ssl_signedcert_install(o.hostname)
            self.bigiq_special_rest_handling(tree, ctx)
            self.bigip_special_rest_handling(tree, ctx)

        return True

    def setup(self):
        if self.specs.get('classes'):
            return self.setup_with_classes()
        else:
            return super(TmosConfig, self).setup()


class ActionModule(ActionBase):
    ''' Print statements during execution '''

    TRANSFERS_FILES = False
    VALID_ARGS = frozenset(('address', 'username', 'password', 'classes',
                            'provision', 'verify', 'timeout', 'ssh_port',
                            'ssl_port', 'license', 'clean', 'verbose',
                            'hostname', 'mgmtip', 'mgmtgw', 'selfip_internal',
                            'selfip_external', 'vlan_internal_name',
                            'vlan_external_name', 'vlan_internal',
                            'vlan_external', 'irack_address', 'irack_username',
                            'irack_apikey', 'no_irack', 'force_license',
                            'license_only', 'partitions', 'node_start',
                            'node_count', 'pool_count', 'pool_members',
                            'vip_start', 'vip_count'))

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        for arg in self._task.args:
            if arg not in self.VALID_ARGS:
                return {"failed": True, "msg": "'%s' is not a valid option in f5_config" % arg}

        result = super(ActionModule, self).run(tmp, task_vars)
        result['_ansible_verbose_override'] = True

        options = Options()
        address = self._task.args.get('address')
        if VAR_F5TEST_CONFIG in task_vars:
            irack = task_vars[VAR_F5TEST_CONFIG].irack
            if irack:
                options.irack_address = irack.address
                options.irack_username = irack.username
                options.irack_apikey = irack.apikey
        options.update(self._task.args)

        macro = TmosConfig(address=address, specs=options)
        result['output'] = macro.run()

        return result
