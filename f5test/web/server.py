#!/usr/bin/env python
from __future__ import absolute_import

""" Mainline processing for the Shiraz Web Server.  Displays UI pages,
    initiates NOSE test runs, and displays status of those runs on the
    web page.
"""

import os
import yaml

import bottle
from f5test.base import AttrDict
from f5test.web.tasks import MyAsyncResult
from f5test.web.validators import validators
import logging

from f5test.web.modules.common import CONFIG, app as common_app
from f5test.web.modules.ictester import app as ictester_app
from f5test.web.modules.install import app as install_app
from f5test.web.modules.config import app as config_app
from f5test.web.modules.demo import app as demo_app
from f5test.web.modules.bvt import app as bvt_app
from f5test.web.modules.deviso import app as deviso_app
from f5test.web.modules.emdeviso import app as emdeviso_app
from f5test.web.modules.bigiq import app as bigiq_app

app = bottle.Bottle()
DEBUG = True
PORT = 8081

# Setup a logger to log basic info of incoming Shiraz requests for debugging.
LOG = logging.getLogger(__name__)


def read_config(config, filename):
    config.update(yaml.load(open(filename).read()))
    # Replacing iRack reservation lookup with a round-robin.
    config.filename = os.path.abspath(filename)
    config.dir = os.path.dirname(config.filename)
    config.web._MC_KEY = 'MC-5d5f8cb6-2e8d-4462-a1e8-12f5d6c35334'


class ReloadConfigPlugin(object):
    ''' This plugin reloads the web.yaml config before every POST. '''
    name = 'reload'
    api = 2

    def __init__(self, config):
        self.config = config

    def apply(self, callback, route):
        def wrapper(*a, **ka):
            if bottle.request.method == 'POST':
                read_config(self.config, self.config.filename)
            rv = callback(*a, **ka)
            return rv

        return wrapper


# Serves static files
@app.route('/media/:path#.+#')
def media(path):
    root = os.path.join(os.path.dirname(__file__), 'media')
    return bottle.static_file(path, root=root)


@app.route('/revoke/<task_id>', name='revoke')
def revoke_handler(task_id):
    """ Use this API to cancel a pending/running Shiraz job.

        Usage:
        http://shiraz/revoke/89a118cb-563b-4f7c-b548-d947f7069615
        (where 89a118cb-563b-4f7c-b548-d947f7069615 is the Shiraz task ID,
        which you can get from the celery inspect active output, second to
        last field)
    """
    LOG.info("REVOKE: called with task id: " + str(task_id))
    task = MyAsyncResult(task_id)  # @UndefinedVariable
    task.revoke(terminate=True)
    task.revoke(terminate=True)  # XXX: why?!
    bottle.response.add_header('Cache-Control', 'no-cache')
    result = dict(status=task.status)
    LOG.info("REVOKE: Result: " + str(result))
    return result


@app.post('/validate')
def validate():
    LOG.info("VALIDATE: called")
    data = AttrDict(bottle.request.json)
    LOG.info("VALIDATE: POST Request: " + str(data))
    bottle.response.add_header('Cache-Control', 'no-cache')

#    print data
    is_valid = validators[data.type](**data)
    if is_valid is not True:
        bottle.response.status = 406
        result = dict(message=is_valid)
        LOG.info("VALIDATE: Result: " + str(result))
        return result
    # Nothing to do if it is valid, all is okay
    else:
        LOG.info("VALIDATE: Successful, no error.")


def main():
    import optparse
    import sys

    usage = """%prog [options] <config>...""" \
    u"""

  Examples:
  %prog 10.1.2.3 webb.yaml"""

    formatter = optparse.TitledHelpFormatter(indent_increment=2,
                                             max_help_position=60)
    p = optparse.OptionParser(usage=usage, formatter=formatter,
                              version="Web Server %s" % 1.0
                              )
    p.add_option("-v", "--verbose", action="store_true",
                 help="Debug logging")
    p.add_option("-p", "--port", metavar="NUMBER",
                 default=8081, type="int",
                 help="What port to listen to. (default: %d)" % 8081)

    options, args = p.parse_args()

    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
        logging.getLogger('f5test').setLevel(logging.INFO)
        logging.getLogger('f5test.macros').setLevel(logging.INFO)

    LOG.setLevel(level)
    logging.basicConfig(level=level)

    if len(args) < 1:
        p.print_version()
        p.print_help()
        sys.exit(2)

    read_config(CONFIG, args[0])

    app.merge(common_app)
    app.merge(config_app)
    app.merge(install_app)
    app.merge(ictester_app)
    app.merge(demo_app)
    app.merge(bvt_app)
    app.merge(deviso_app)
    app.merge(emdeviso_app)
    app.merge(bigiq_app)

    app.install(ReloadConfigPlugin(CONFIG))
    app.run(host='0.0.0.0', port=options.port, debug=DEBUG)

if __name__ == '__main__':
    # app.run(host='0.0.0.0', server='gevent', port=PORT, debug=DEBUG)
    # app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
    main()
