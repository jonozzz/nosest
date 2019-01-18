'''
Created on Mar 5, 2018

@author: jono
'''
from f5test.macros.base import Macro
from f5test.base import Options
from f5test.defaults import ROOT_PASSWORD, ROOT_USERNAME
from f5test.interfaces.ssh import SSHInterface
import logging
from f5test.utils.parsers.tmsh import parser

LOG = logging.getLogger(__name__)
TMSH_DELETE = 'delete {}'
PROMPT = '# '
__version__ = '1.0'


class Tool(Macro):

    def __init__(self, options, address=None, filename=None):
        self.options = Options(options)
        self.filename = filename

        self.sshparams = Options(device=self.options.device,
                                 address=address, timeout=self.options.timeout,
                                 username=self.options.username,
                                 password=self.options.password,
                                 port=self.options.port)

        super(Tool, self).__init__()

    def prep(self):
        self.sshifc = SSHInterface(**self.sshparams)
        self.api = self.sshifc.open()

    def cleanup(self):
        self.sshifc.close()

    def setup(self):
        if not self.api.exists(self.filename):
            raise RuntimeError('File %s not found on the target.' % self.filename)
        LOG.info('Processing...')

        with self.api.sftp().open(self.filename) as f:
            result = parser(f.read().decode())
            shell = self.api.interactive()
            shell.expect_exact(PROMPT)
            shell.sendline('tmsh')
            shell.expect_exact(PROMPT)
            leftovers = set()

            for path in reversed(list(result.keys())):
                if path.startswith('ltm pool'):
                    for member in list(result[path]['members'].keys()):
                        if member.count('.') == 1:  # 2002::1.http
                            leftovers.add('ltm node {}'.format(member.split('.')[0]))
                        elif member.count(':') == 1:  # 1.1.1.1:21
                            leftovers.add('ltm node {}'.format(member.split(':')[0]))
                        else:
                            raise ValueError(member)
                shell.sendline(TMSH_DELETE.format(path))
                shell.expect_exact(PROMPT)
                LOG.info(shell.before)

            for path in leftovers:
                shell.sendline(TMSH_DELETE.format(path))
                shell.expect_exact(PROMPT)
                LOG.info(shell.before)

        LOG.info('Done.')


def main():
    import optparse
    import sys

    usage = """%prog [options] <address> [scf]...""" \
        """
  A tool that attempts to "unmerge" a SCF file.

  Examples:
  %prog 10.1.2.3 /tmp/test.scf
"""

    formatter = optparse.TitledHelpFormatter(indent_increment=2,
                                             max_help_position=60)
    p = optparse.OptionParser(usage=usage, formatter=formatter,
                              version="SCF unmerger %s" % __version__)
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

    tool = Tool(options=options, address=args[0], filename=args[1])
    tool.run()


if __name__ == '__main__':
    main()
