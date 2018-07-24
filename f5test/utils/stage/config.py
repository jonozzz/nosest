'''
Created on Feb 21, 2014

@author: jono
'''
from .base import Stage
from ...base import Options
from ...interfaces.config import (ConfigInterface, KEYSET_COMMON, KEYSET_DEFAULT,
                                  KEYSET_LOCK)
from ...interfaces.icontrol import IcontrolInterface
from ...interfaces.ssh import SSHInterface
from ...macros.base import Macro
from ...macros.keyswap import KeySwap
from ...macros.tmosconf.placer import (ConfigPlacer, DNS_SERVERS,
                                       DNS_SUFFIXES, NTP_SERVERS)
from ...macros.tmosconf.scaffolding import make_partitions, Partition
from ...utils.parsers.tmsh import RawEOL
from ...utils.dicts import replace

import f5test.commands.icontrol as ICMD
import f5test.commands.shell as SCMD
import datetime
import logging
import importlib

DEFAULT_TIMEOUT = 600
LOG = logging.getLogger(__name__)


class ConfigStage(Stage, ConfigPlacer):
    """
    This stage makes sure the devices are configured with the 'stock' settings.
    Its functionally is similar to the f5.configurator CLI utility.
    """
    name = 'config'

    def __init__(self, device, specs, *args, **kwargs):
        configifc = ConfigInterface()
        config = configifc.open()
        self._context = specs.get('_context')
        common = config.get('platform', Options())

        options = Options(device=device,
                          ssh_port=device.ports.get('ssh'),
                          ssl_port=device.ports.get('https'),
                          license=specs.get('license'),
                          timezone=specs.get('timezone',
                                             common.get('timezone')),
                          timeout=specs.get('timeout'),
                          selfip_internal=specs.get('selfip internal'),
                          selfip_external=specs.get('selfip external'),
                          vlan_internal=specs.get('vlan internal'),
                          vlan_external=specs.get('vlan external'),
                          trunks_lacp=specs.get('trunks lacp'),
                          provision=specs.get('provision'),
                          partitions=specs.get('partitions'),
                          node_count=specs.get('node count'),
                          pool_count=specs.get('pool count'),
                          vip_count=specs.get('vip count'),
                          pool_members=specs.get('pool members'),
                          node_start=specs.get('node start'),
                          vip_start=specs.get('vip start'),
                          no_irack=specs.get('no irack'),
                          csv=specs.get('csv'),
                          hostname=specs.get('hostname'),
                          dns_servers=specs.get('dns servers',
                                                common.get('dns servers')),
                          dns_suffixes=specs.get('dns suffixes',
                                                 common.get('dns suffixes')),
                          ntp_servers=specs.get('ntp servers',
                                                common.get('ntp servers')),
                          clean=specs.get('clean', False),
                          force_license=specs.get('force license', False))

        if config.irack:
            options.irack_address = config.irack.address
            options.irack_username = config.irack.username
            options.irack_apikey = config.irack.apikey

        super(ConfigStage, self).__init__(options, *args, **kwargs)

    def setup(self):
        ret = super(ConfigStage, self).setup()
        LOG.debug('Locking device %s...', self.options.device)
        ICMD.system.SetPassword(device=self.options.device).run_wait(timeout=300)
        self.options.device.specs._x_tmm_bug = True
        self.options.device.specs.has_tmm_restarted = datetime.datetime.now()
        self.options.device.specs.is_cluster = SCMD.ssh.is_cluster(device=self.options.device)

        return ret

    def revert(self):
        super(ConfigStage, self).revert()
        if self._context:
            LOG.debug('In ConfigStage.revert()')
            device = self.options.device
            # If the installation has failed before rebooting then no password
            # change is needed.
            #ICMD.system.set_password(device=self.options.device)
            self._context.get_interface(SSHInterface, device=device)


class SetPasswordStage(Stage, Macro):
    """
    A teardown stage that resets the password on configured devices.
    """
    name = 'setpassword'

    def __init__(self, device, specs=None, *args, **kwargs):
        self.device = device
        self.specs = specs
        super(SetPasswordStage, self).__init__(*args, **kwargs)

    def run(self):
        LOG.debug('Unlocking device %s', self.device)
        keysets = Options(default=KEYSET_DEFAULT, common=KEYSET_COMMON, lock=KEYSET_LOCK)
        ICMD.system.set_password(device=self.device,
                                 keyset=keysets.get(self.specs.keyset, KEYSET_COMMON))

        # Save the config after password change otherwise it will be reverted
        # upon reboot.
        with IcontrolInterface(device=self.device) as icifc:
            icifc.api.System.ConfigSync.save_configuration(filename='',
                                                           save_flag="SAVE_HIGH_LEVEL_CONFIG")


class KeySwapStage(Stage, KeySwap):
    """
    This stage makes sure the SSH keys are exchanged between the test runner
    system and the devices.
    """
    name = 'keyswap'

    def __init__(self, device, specs=None, *args, **kwargs):
        options = Options(device=device)
        super(KeySwapStage, self).__init__(options, *args, **kwargs)


class TmosConfigStage(Stage, ConfigPlacer):
    name = 'tmosconfig'

    def __init__(self, device, specs, *args, **kwargs):
        configifc = ConfigInterface()
        config = configifc.open()
        self._context = specs.get('_context')
        common = config.get('platform', Options())
        self.specs = specs

        options = Options(device=device,
                          ssh_port=device.ports.get('ssh'),
                          ssl_port=device.ports.get('https'),
                          license=specs.get('license'),
                          provision=specs.get('provision'),
                          clean=specs.get('clean', False),
                          timeout=specs.get('timeout'),
                          verify=specs.get('verify'),
                          no_irack=specs.get('no irack', True),
                          force_license=specs.get('force license', False),
                          license_only=specs.get('license only', False)
                          )
        super(TmosConfigStage, self).__init__(options, *args, **kwargs)

    def prep(self):
        self._context.set_stat_counter(__name__,
                                       'stage.setup.%s' % self.device.alias)
        super(TmosConfigStage, self).prep()

    def cleanup(self):
        self._context.set_stat_counter(__name__,
                                       'stage.cleanup.%s' % self.device.alias)
        super(TmosConfigStage, self).cleanup()

    def setup(self):
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

        for klass_path, specs in self.specs.get('classes', {}).items():
            path, klass_name = klass_path.rsplit('.', 1)
            module = importlib.import_module('...macros.tmosconf.%s' % path,
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
