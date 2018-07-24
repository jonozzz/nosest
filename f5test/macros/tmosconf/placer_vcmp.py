#!/usr/bin/env python
'''
Created on Dec 30, 2015

@author: jwong
'''

from f5test.interfaces.config import DeviceAccess
from f5test.macros.tmosconf.placer import ConfigPlacer
from f5test.macros.tmosconf.base import SystemConfig
from f5test.macros.tmosconf.canned.vcmp import vCMPConfig
from f5test.interfaces.icontrol import IcontrolInterface
from f5test.base import Options as O
from f5test.defaults import ADMIN_PASSWORD, ADMIN_USERNAME
from netaddr import IPAddress, IPNetwork
import f5test.commands.shell as SCMD
import f5test.commands.icontrol as ICMD
import logging
import sys
import time

__version__ = 1.0

LOG = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 300
DEFAULT_NETMASK_PREFIX = 24
GUEST_NAME = 'vcmp_guest-%s'
VCMP_ONLINE_STATES = ('provisioned', 'deployed')
VCMP_TIMEOUT = 600


# TODO: Would be nice one day if this can go into placer.py. Need to think of
#       put to put it in place but also not configure anything else on vCMP
#       Host, like what is happening here. This is a Cisco APIC specific
#       pre-condition.
class VcmpPlacer(ConfigPlacer):
    SystemConfig = SystemConfig
    vCMPConfig = vCMPConfig

    def __init__(self, guests, *args, **kwargs):
        super(VcmpPlacer, self).__init__(*args, **kwargs)
        # Case when there is no vCMP guests to setup.
        if not guests:
            guests = []

        self.guests = []
        for guest in guests:
            if isinstance(guest, DeviceAccess):
                item = guest
            else:
                if len(guest.split(':')) > 2:
                    address, gw, name = guest.split(':')
                elif len(guest.split(':')) > 1:
                    address, gw = guest.split(':')
                    name = None
                else:
                    address, gw, name = guest, None, None

                item = O()
                item.specs = O()
                spec = item.specs
                spec.address = IPNetwork(address)
                spec.gw = IPAddress(gw) if gw else None
                spec.cores = self.options.get('cores')
                spec.name = name
            self.guests.append(item)

        if isinstance(self.device, DeviceAccess):
            self.options.admin_username = self.device.get_admin_creds().username or ADMIN_USERNAME
            self.options.admin_password = self.device.get_admin_creds().password or ADMIN_PASSWORD

        self.options.setifnone('admin_username', ADMIN_USERNAME)
        self.options.setifnone('admin_password', ADMIN_PASSWORD)

        # Assumed we are using vcmp provisioning here if we are not reverting
        # BIG-IP back to whatever provision.
        if not self.options.revert:
            self.options.provision = 'vcmp'

    def prep(self):
        super(VcmpPlacer, self).prep()
        self.icifc = IcontrolInterface(address=self.address,
                                       username=self.options.admin_username,
                                       password=self.options.admin_password,
                                       port=self.options.ssl_port)

    def get_provider(self, address, csv):
        provider = O()
        if not self.options.no_irack and not csv:
            LOG.info("Using data from iRack")
            provider = self.irack_provider(address=self.options.irack_address,
                                           username=self.options.irack_username,
                                           apikey=self.options.irack_apikey,
                                           mgmtip=address,
                                           timeout=self.options.timeout)
        elif csv:
            LOG.info("Using data from CSV: %s" % csv)
            provider = self.csv_provider(mgmtip=address, csv_rpath=csv)

        return provider

    def wait_reboot(self, icifc, timeout=None):
        timeout = timeout or self.options.timeout

        ICMD.system.IsServiceUp('MCPD', ifc=icifc).\
            run_wait(timeout=timeout,
                     timeout_message="Timeout ({0}s) while waiting for MCPD "
                                     "to come up")
        ICMD.system.IsServiceUp('TMM', ifc=icifc).\
            run_wait(timeout_message="Timeout ({0}s) while waiting for TMM "
                                     "to come up")

        ICMD.management.GetDbvar('Configsync.LocalConfigTime', ifc=icifc).\
            run_wait(lambda x: int(x) > 0,
                     progress_cb=lambda x: 'waiting configsync...',
                     timeout=timeout)

        ICMD.system.FileExists('/var/run/mprov.pid', ifc=self.icifc).\
            run_wait(lambda x: x is False,
                     progress_cb=lambda x: 'mprov still running...',
                     timeout=timeout)
        ICMD.system.FileExists('/var/run/grub.conf.lock', ifc=self.icifc).\
            run_wait(lambda x: x is False,
                     progress_cb=lambda x: 'grub.lock still present...',
                     timeout=timeout)

    def clean_vdisk(self):
        images = SCMD.tmsh.list('vcmp virtual-disk', ifc=self.sshifc)
        for image in images:
            LOG.info("Cleaning old Virtual Disk Image: %s" % image.split()[-1])
            SCMD.tmsh.run(image, command='delete', ifc=self.sshifc)

    def delete_guests(self):
        guests = SCMD.tmsh.list('vcmp guest', ifc=self.sshifc)
        for guest, items in guests.items():
            if 'state' in items and items['state'] in VCMP_ONLINE_STATES:
                LOG.info("Disabling %s..." % guest.split()[-1])
                SCMD.tmsh.run(guest + ' state configured', command='modify',
                              ifc=self.sshifc)
            LOG.info("Deleting %s..." % guest.split()[-1])
            SCMD.tmsh.run(guest, command='delete', ifc=self.sshifc)

    def setup(self):
        ctx = self.make_context()
        if self.options.revert:
            LOG.info("Reverting by provisioning to %s" % self.options.provision)

        if self.options.clean_only and 'vcmp' in list(ctx.provision.keys()):
            # Disable any running vCMP Guests then delete them
            self.delete_guests()
            self.clean_vdisk()
            return

        if not self.guests and not self.revert:
            LOG.warning("No vCMP Guests to setup. Just use the normal "
                        "configurator if you only need to do vcmp "
                        "provisioning only...")
            return

        provider = self.get_provider(self.address, self.options.csv)
        reboot = True

        # TODO: We will need to add more logic here to check if the current
        # running guests are the same as our config. If so, leave it, otherwise
        # clean it out.
        if 'vcmp' in list(ctx.provision.keys()):
            # Disable any running vCMP Guests then delete them
            self.delete_guests()
            self.clean_vdisk()

        if self.options.provision in list(ctx.provision.keys()):
            LOG.info("No need for reboot...")
            reboot = False
        # System
        o = O()
        o.hostname = self.options.hostname or provider.get('hostname')
        self.set_networking(o)
        self.set_provisioning(o)
        if provider.mgmtip and (o.mgmtip.ip != provider.mgmtip.ip or
                                o.mgmtip.cidr != provider.mgmtip.cidr):
            LOG.warning('Management address mismatch. iRack/CSV has {0} but '
                        'found {1}. iRack/CSV will take '
                        'precedence.'.format(provider.mgmtip, o.mgmtip))
            o.mgmtip = provider.mgmtip

        if provider.gateway and o.gateway != provider.gateway:
            LOG.warning('Default gateway address mismatch. iRack/CSV has '
                        '{0} but found {1}. iRack/CSV will take '
                        'precedence.'.format(provider.gateway, o.gateway))
            o.gateway = provider.gateway
        tree = self.SystemConfig(self.context, partitions=0, **o).run()

        # Skip this if we are reverting back to another provision
        if not self.options.revert:
            # vCMP Guests
            LOG.info("Generating vCMP Guests...")

            # Look for image and hotfix with the same version as BIG-IP Host.
            target_version = ctx.version.version
            images = SCMD.ssh.generic('ls /shared/images', ifc=self.sshifc).stdout
            hotfix = base = None
            for image in images.split():
                if target_version in image and 'Hotfix' in image:
                    hotfix = image
                elif target_version in image:
                    base = image

                if hotfix and image:
                    break

            for i, guest in enumerate(self.guests):
                csv = self.device.specs.csv if isinstance(self.device, DeviceAccess) else self.options.csv

                # Just IP, no netmask info like x.x.x.x/yy
                ip = guest.specs.address.ip if isinstance(guest.specs.address, IPNetwork) else guest.address
                provider = self.get_provider(ip, csv)

                management_ip = provider.mgmtip or IPNetwork(guest.specs.address)
                management_gw = provider.gateway or guest.specs.gw

                if str(management_ip.netmask) == '255.255.255.255':
                    LOG.warning("Mgmt netmask probably was not set! Defaulting to "
                                "/24 prefix.")
                    management_ip.prefixlen = DEFAULT_NETMASK_PREFIX

                if not management_gw:
                    LOG.warning("Gateway not set!!")
                    default_gw = management_ip.broadcast - 1
                    management_gw = default_gw
                    LOG.warning("Defaulting to %s" % default_gw)

                guest_name = guest.specs.name or GUEST_NAME % (i)
                o = O(tree=tree, name=guest_name,
                      management_ip=management_ip,
                      management_gw=management_gw,
                      initial_image=base, initial_hotfix=hotfix)
                if guest.specs.get('cores'):
                    o.cores_per_slot = guest.specs.get('cores')

                tree = self.vCMPConfig(self.context, **o).run()

        if self.options.stdout:
            self.dump(tree, ctx)
            return

        self.load(tree, ctx)

        # If BIG-IP isn't already provisioned, a reboot will happen.
        timeout = self.options.timeout
        if reboot:
            ic = self.icifc.open()
            uptime = ic.System.SystemInfo.get_uptime()
            LOG.info("Pausing 30 seconds to wait until reboot has happened...")
            time.sleep(30)

            if uptime:
                ICMD.system.HasRebooted(uptime, ifc=self.icifc).\
                    run_wait(timeout=timeout)
                LOG.info('Device is rebooting...')

            LOG.info('Wait for box to be ready...')
            self.wait_reboot(self.icifc)

        self.reset_trust()
        self.ready_wait()

        # Skip this if we are reverting back to another provision
        if not self.options.revert:
            # There shouldn't be any virtual disks so clean out any remaining ones
            # from previous runs
            self.clean_vdisk()

            # Deploy vCMP Guests.
            guests = SCMD.tmsh.list('vcmp guest', ifc=self.sshifc)
            for guest, items in guests.items():
                if 'state' not in items or items['state'] != 'deployed':
                    LOG.info("Deploying %s..." % guest.split()[-1])
                    SCMD.tmsh.run(guest + ' state deployed', command='modify',
                                  ifc=self.sshifc)

            # Wait until vCMP guests are running
            timeout = VCMP_TIMEOUT * (len(self.guests) / 6 + 1)  # Only 6 vCMP Guests can start in parallel
            for guest in self.guests:
                try:
                    ip = guest.specs.address.ip if isinstance(guest.specs.address, IPNetwork) else guest.address
                    icifc = IcontrolInterface(address=ip,
                                              username=ADMIN_USERNAME,
                                              password=ADMIN_PASSWORD,
                                              port=self.options.ssl_port)
                    LOG.info('Wait for %s to be ready...' % ip)
                    self.wait_reboot(icifc, timeout=timeout)
                finally:
                    icifc.close()

        self.save(ctx)
        self.ssh_key_exchange()

    def cleanup(self):
        super(VcmpPlacer, self).cleanup()
        self.icifc.close()


def main(*args, **kwargs):
    import optparse

    def _parser():
        usage = """%prog [options] <address> <guest_ip>/<prefix>:gateway[:name] [<guest_ip>/<netmask>:gateway[:name]]"""

        formatter = optparse.TitledHelpFormatter(max_help_position=30)
        p = optparse.OptionParser(usage=usage,
                                  formatter=formatter,
                                  version="Config Generator %s" % __version__,
                                  )

        p.add_option("", "--hostname", metavar="HOSTNAME",
                     type="string",
                     help="The device hostname")
        p.add_option("", "--mgmtip", metavar="IP/PREFIX",
                     type="string",
                     help="The device management address")
        p.add_option("", "--mgmtgw", metavar="IP",
                     type="string",
                     help="The device management gateway")
        p.add_option("", "--ssl-port", metavar="INTEGER", type="int", default=443,
                     help="SSL Port. (default: 443)")
        p.add_option("", "--ssh-port", metavar="INTEGER", type="int", default=22,
                     help="SSH Port. (default: 22)")
        p.add_option("", "--provision", metavar="MODULE:[LEVEL],[MODULE:LEVEL]",
                     type="string",
                     help="Provision module list")
        p.add_option("", "--clean-only",
                     action="store_true",
                     help="Clean vcmp guests and vdisks. Only works when vcmp provisioned")
        p.add_option("", "--verify",
                     action="store_true",
                     help="Verify configuration")
        p.add_option("", "--cores", metavar="CORES",
                     type="string",
                     help="cores for all vcmp guests")

        p.add_option("", "--irack-address", metavar="HOSTNAME",
                     type="string", default="irack",
                     help="The iRack hostname or IP address")
        p.add_option("", "--irack-username", metavar="STRING",
                     type="string", default="guest",
                     help="Username used to authenticate with iRack.")
        p.add_option("", "--irack-apikey", metavar="STRING",
                     type="string", default="b8e977cd-9b99-413b-8c3f-8c4411941b8e",
                     help="API key used to authenticate with iRack")

        p.add_option("", "--no-irack",
                     action="store_true",
                     help="Don't attempt to connect to iRack. Useful when network connectivity is not available.")
        p.add_option("", "--csv",
                     type="string", default="",
                     help="Specify the CSV file you want to use. Ex. /config/users/shared/my_file.csv")
        p.add_option("", "--timeout",
                     default=DEFAULT_TIMEOUT, type="int",
                     help="The SSH timeout. (default: %d)" % DEFAULT_TIMEOUT)
        p.add_option("", "--revert",
                     action="store_true", default=False,
                     help="Revert back to values in 'provision'?")
        p.add_option("", "--verbose",
                     action="store_true",
                     help="Debug messages")
        p.add_option("", "--stdout",
                     action="store_true",
                     help="Dump configuration to stdout")
        return p

    p = _parser()
    options, args = p.parse_args()

    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
        # Shut paramiko's mouth
        logging.getLogger('paramiko.transport').setLevel(logging.ERROR)
        logging.getLogger('f5test').setLevel(logging.ERROR)
        logging.getLogger('f5test.macros').setLevel(logging.INFO)

    LOG.setLevel(level)
    logging.basicConfig(level=level)

    if not args:
        p.print_version()
        p.print_help()
        sys.exit(2)  # @UndefinedVariable

    guests = []
    for spec in args[1:]:
        guests.append(spec)

    m = VcmpPlacer(options=options, address=args[0], guests=guests)
    m.run()

if __name__ == '__main__':
    main()
