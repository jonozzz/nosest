'''
Created on Mar 15, 2017

@author: jono
'''
import BaseHTTPServer
import json
import logging
import requests
import socket
from threading import Thread
import time
import urlparse


WAIT_TIME = 10
LOG = logging.getLogger(__name__)
URL = 'http://127.0.0.1:8893/bvt_test'


def get_local_ip(peer):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((peer.split(':', 1)[0], 0))
    ip = s.getsockname()[0]
    s.close()
    return ip


class HttpListener(Thread):
    """
    @var handler_class: A HTTP request handler subclass that will implement do_*() methods.
    @var timeout: How long should the server run for? (in seconds)
    @var port: The port that's listening on. By default it'll listen on all
            interfaces.
    """

    def __init__(self, handler_class, port=80, debug=False):
        super(HttpListener, self).__init__(name='HttpListener')
        self.handler_class = handler_class
        self.port = port
        self.debug = debug
        self.server = None

    def run(self):
        server_address = ('', self.port)

        server = BaseHTTPServer.HTTPServer(server_address, self.handler_class)
        self.server = server
        server.running = True
        server.serve_forever()


if __name__ == '__main__':
    import optparse

    usage = """%prog [options] <config>...""" \
    u"""
    Usage:
    %prog [URL]

  Examples:
  %prog http://localhost:8888/bvt_test"""

    formatter = optparse.TitledHelpFormatter(indent_increment=2,
                                             max_help_position=60)
    p = optparse.OptionParser(usage=usage, formatter=formatter,
                              version="Web Server %s" % 1.0
                              )
    p.add_option("-v", "--verbose", action="store_true",
                 help="Debug logging")

    options, args = p.parse_args()

    if args:
        URL = args[0]

    if options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
        logging.getLogger('f5test').setLevel(logging.INFO)
        logging.getLogger('f5test.macros').setLevel(logging.INFO)

    LOG.setLevel(level)
    logging.basicConfig(level=level)

    class HandlePost(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            if self.path != '/receiver':
                LOG.warning("Ignoring POST to %s.", self.path)
                return
            LOG.info('Got a POST! %s', json.dumps(json.loads(post_data), indent=4))
            self.send_response(200)
            # Quit after one request
            self.server.running = False

    t = HttpListener(HandlePost, port=0)
    LOG.info("Starting...")
    t.start()

    while t.server is None:
        time.sleep(.1)

    local_port = t.server.server_port
    local_ip = get_local_ip('172.27.1.1')
    LOG.info("Listening on %s:%d" % (local_ip, local_port))
    payload = {"submitted_by": "user@host.com",
               "endpoint": "http://%s:%d/receiver" % (local_ip, local_port),
               "tests": [
                   'tests/cascade/test_template.py'],
               "devices": {
                   'bigiq-1':
                   {'kind': 'tmos:bigiq',
                    'default': True,
                    'address': '1.1.1.1',
                    'admin password': '',
                    'root password': ''},
                   'bigip-1':
                   {'kind': 'tmos:bigip',
                    'address': '1.1.1.2',
                    'admin password': '',
                    'root password': ''},
                   'bigip-2':
                   {'kind': 'tmos:bigip',
                    'address': '1.1.1.3',
                    'admin password': '',
                    'root password': ''},
               },
               "project": "tmos-tier2",
               "build": "945.0"}
    headers = {'Content-Type': 'application/json'}

    ret = requests.post(URL, headers=headers, json=payload)
    if ret.status_code != 200:
        t.server.running = False
        t.server.shutdown()
    status_url = urlparse.urljoin(ret.url, ret.json()['link'])

    end = time.time() + WAIT_TIME
    while time.time() < end and t.server.running:
        ret = requests.get(status_url)
        status = ret.json()['status']
        LOG.info('Task status %s...' % status)
        if status not in ('STARTED', 'PENDING'):
            t.server.running = False
        time.sleep(1)

    t.server.shutdown()
    t.join()
    LOG.info('done!')
