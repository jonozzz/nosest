'''
Created on Feb 22, 2017

@author: jono
'''
from f5test.macros.base import Macro
from f5test.base import Options
from f5test.defaults import ROOT_PASSWORD, ROOT_USERNAME
from f5test.interfaces.ssh import SSHInterface
import logging
#import re
from f5test.utils.parsers import tmsh
#import shlex
#from collections import OrderedDict


LOG = logging.getLogger(__name__)
UCS_TMP = '/shared/tmp/ucs_tmp'
__version__ = '1.0'


class UcsTool(Macro):

    def __init__(self, options, address=None, ucs_name=None):
        self.options = Options(options)
        self.ucs_name = ucs_name

        self.sshparams = Options(device=self.options.device,
                                 address=address, timeout=self.options.timeout,
                                 username=self.options.username,
                                 password=self.options.password)

        super(UcsTool, self).__init__()

    def prep(self):
        self.sshifc = SSHInterface(**self.sshparams)
        self.api = self.sshifc.open()
        self.api.run('rm -rf {0} && mkdir -p {0}'.format(UCS_TMP))

    def cleanup(self):
        self.sshifc.close()

    def setup(self):
        if not self.api.exists('/var/local/ucs/{}.ucs'.format(self.ucs_name)):
            raise RuntimeError('UCS not found on the target.')
        LOG.info('Processing...')
        self.api.run(r'cd {} && tar xf /var/local/ucs/{}.ucs'.format(UCS_TMP, self.ucs_name))

        # Replace all encrypted secrets which will fail to load anyway.
        self.api.run(r"sed -ibak '/^\s*#/!s/secret.*$/secret default/g' {}/config/bigip.conf".format(UCS_TMP))

        # Adding the license back
        self.api.run(r"cp -f /config/bigip.license {}/config/".format(UCS_TMP))

        # Preserve:
        # - management IP
        # - management route
        # Note: DHCP is not supported
        text = self.api.sftp().open('/config/bigip_base.conf').read()
        config = tmsh.parser(text)
        with self.api.sftp().open('{}/config/bigip_base.conf'.format(UCS_TMP), 'at+') as f:
            f.write(config.match('sys management-ip .*').dumps())
            f.write(config.match('sys management-route /Common/default').dumps())
            bit = config.match('sys global-settings')
            bit['sys global-settings']['mgmt-dhcp'] = 'disabled'
            bit['sys global-settings']['gui-security-banner-text'] = 'Welcome to the BIG-IP Configuration Utility. Configuration imported by UCS Tool 1.0'
            f.write(bit.dumps())
        
        self.api.run(r'tar -C {} --xform s:"^./":: -czf /var/local/ucs/{}_imported.ucs .'.format(UCS_TMP, self.ucs_name))
        #print config
        if self.options.load:
            LOG.info('Loading UCS...')
            self.api.run('tmsh load sys ucs {}_imported no-platform-check no-license'.format(self.ucs_name))

        LOG.info('Done.')


def main():
    import optparse
    import sys

    usage = """%prog [options] <address> [ucs]...""" \
        """
  Converts and loads a UCS file imported from another device.

  Examples:
  %prog 172.27.96.7 blah.ucs
"""

    formatter = optparse.TitledHelpFormatter(indent_increment=2,
                                             max_help_position=60)
    p = optparse.OptionParser(usage=usage, formatter=formatter,
                              version="TMOS config extractor %s" % __version__)
    p.add_option("-v", "--verbose", action="store_true",
                 help="Debug logging")

    p.add_option("-u", "--username", metavar="USERNAME",
                 default=ROOT_USERNAME, type="string",
                 help="Root username (default: %s)"
                 % ROOT_USERNAME)
    p.add_option("-p", "--password", metavar="PASSWORD",
                 default=ROOT_PASSWORD, type="string",
                 help="Root password (default: %s)"
                 % ROOT_PASSWORD)

    p.add_option("-l", "--load", action="store_true",
                 help="Load the UCS after converting")
    p.add_option("-t", "--timeout", metavar="SECONDS", type="int", default=60,
                 help="Timeout (default: 60)")

    options, args = p.parse_args()

    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
        logging.getLogger('paramiko.transport').setLevel(logging.ERROR)
        logging.getLogger('f5test').setLevel(logging.INFO)
        logging.getLogger('f5test.macros').setLevel(logging.INFO)

    LOG.setLevel(level)
    logging.basicConfig(level=level)

    if len(args) < 2:
        p.print_version()
        p.print_help()
        sys.exit(2)

    ut = UcsTool(options=options, address=args[0], ucs_name=args[1])
    ut.run()

if __name__ == '__main__':
    main()
