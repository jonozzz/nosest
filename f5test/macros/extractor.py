# -*- coding: utf-8 -*-
'''
Created on May 12, 2016

@author: jono
'''
from f5test.macros.base import Macro
from f5test.base import Options
from f5test.defaults import ROOT_PASSWORD, ROOT_USERNAME
from f5test.interfaces.ssh import SSHInterface
import logging
import re
from f5test.utils.parsers import tmsh
import shlex
from collections import OrderedDict


LOG = logging.getLogger(__name__)
SCF_OUTPUT = '/shared/tmp/a.scf'
__version__ = '1.2'


class Extractor(Macro):

    def __init__(self, options, address=None, params=None):
        self.options = Options(options)
        self.params = ' '.join(params or [])

        self.sshparams = Options(device=self.options.device,
                                 address=address, timeout=self.options.timeout,
                                 username=self.options.username,
                                 password=self.options.password)

        super(Extractor, self).__init__()

    def prep(self):
        self.sshifc = SSHInterface(**self.sshparams)
        self.api = self.sshifc.open()

    def cleanup(self):
        self.sshifc.close()

    def dump_config(self, filename):
        LOG.info('Dumping configuration...')
        if self.options.ucs:
            LOG.info('Extracting ucs %s...', self.options.ucs)
            self.api.run('mkdir -p /var/local/ucs/tmp')
            self.api.run('cd /var/local/ucs/tmp && tar xf ../{}'.format(self.options.ucs))
            self.api.run('cp /var/local/ucs/tmp/config/bigip.conf {}'.format(filename))
            self.api.run('rm -rf /var/local/ucs/tmp')
            text = self.api.run('cat {}'.format(filename)).stdout
        else:
            if self.sshifc.version > 'bigip 12.1.0':
                text = self.api.run('tmsh save sys config file {0} no-passphrase && cat {0}'.format(filename)).stdout
            else:
                text = self.api.run('tmsh save sys config file {0} && cat {0}'.format(filename)).stdout
        return text

    def setup(self):
        output = SCF_OUTPUT
        if self.options.cache:
            if self.api.exists(output):
                text = self.api.run('cat {0}'.format(output)).stdout
            else:
                text = self.dump_config(output)
        else:
            text = self.dump_config(output)

        if not self.options.cache:
            self.api.run('rm -f {0}*'.format(output)).stdout

        LOG.info('Parsing...')
        config = tmsh.parser(unicode(text, errors='ignore'))
        LOG.debug(config)
        all_keys = config.keys()
        LOG.info('Last key: %s', all_keys[-1])
        all_ids = {}
        for x in all_keys:
            k = shlex.split(x)[-1]
            if k in all_ids:
                all_ids[k].append(config.glob(x))
            else:
                all_ids[k] = [config.glob(x)]
        vip = config.match("^{}$".format(self.params))
        if not vip:
            raise Exception('No objects found matching "%s"' % self.params)

        def rec2(root, deps=OrderedDict()):
            deps.update(root)

            def guess_key(k, d):
                this_id = re.split('[:]', k, 1)[0]
                if not this_id.startswith('/'):
                    this_id = '/Common/%s' % this_id

                if k.startswith('/'):
                    folder = k.rsplit('/', 1)[0]
                    if folder in all_ids:
                        for x in all_ids[folder]:
                            d.update(x)

                if this_id in all_ids:
                    for x in all_ids[this_id]:
                        d.update(x)

                # ipv6.port
                if re.search(':.*\.[^\.]*$', k):
                    this_id = re.split('[\.]', k, 1)[0]
                    this_id = '/Common/%s' % this_id
                    if this_id in all_ids:
                        for x in all_ids[this_id]:
                            d.update(x)

            def rec(root, deps=None):
                if deps is None:
                    deps = {}
                if isinstance(root, dict):
                    for k, v in root.iteritems():
                        guess_key(k, deps)
                        rec(v, deps)
                elif isinstance(root, (set, list, tuple)):
                    for v in root:
                        rec(v, deps)
                else:
                    root = str(root)
                    assert isinstance(root, basestring), root
                    guess_key(root, deps)
                return deps
            d = rec(root)
            if d:
                # Try to avoid circular dependencies
                map(lambda x: d.pop(x), [x for x in d if x in deps])
                deps.update(d)
                rec2(d, deps)
            return deps

        ret = rec2(vip)
        # Sort keys
        if self.options.sort:
            ret = tmsh.GlobDict(sorted(ret.iteritems(), key=lambda x: x[0]))
        return tmsh.dumps(ret)


def main():
    import optparse
    import sys

    usage = """%prog [options] <address> [regex]...""" \
        u"""
  Extract TMOS configuration recursively from existing systems.

  Examples:
  %prog 10.1.2.3 ltm virtual cgnat_http
  %prog 10.1.2.3 'ltm virtual cgnat_http|net vlan *'
"""

    formatter = optparse.TitledHelpFormatter(indent_increment=2,
                                             max_help_position=60)
    p = optparse.OptionParser(usage=usage, formatter=formatter,
                              version="TMOS config extractor %s" % __version__)
    p.add_option("-v", "--verbose", action="store_true",
                 help="Debug logging")

    p.add_option("-c", "--cache", action="store_true",
                 help="Don't remove SCF file ({}) after parsing".format(SCF_OUTPUT))
    p.add_option("-s", "--sort", action="store_true",
                 help="Sort objects alphabetically")
    p.add_option("-u", "--username", metavar="USERNAME",
                 default=ROOT_USERNAME, type="string",
                 help="Root username (default: %s)"
                 % ROOT_USERNAME)
    p.add_option("-p", "--password", metavar="PASSWORD",
                 default=ROOT_PASSWORD, type="string",
                 help="Root password (default: %s)"
                 % ROOT_PASSWORD)
    p.add_option("", "--ucs", metavar="FILE", type="string",
                 help="UCS File to look at (Optional)")

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

    cs = Extractor(options=options, address=args[0],
                   params=args[1:])
    print cs.run()

if __name__ == '__main__':
    main()
