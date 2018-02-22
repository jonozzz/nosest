'''
Created on Mar 15, 2017

@author: jono
'''
import BaseHTTPServer
from threading import Thread
import time
import json
import socket
import requests
import urlparse


WAIT_TIME = 10
URL = 'http://192.168.42.165:8893/bvt_test'
# URL = 'http://10.145.196.102:8890/bvt_test'
# URL = 'http://192.168.42.165:8081/bvt_test'


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
    class HandlePost(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            if self.path != '/receiver':
                print "Ignoring POST to %s." % self.path
                return
            print 'Got a post!', json.loads(post_data)
            self.send_response(200)
            # Quit after one request
            self.server.running = False

    t = HttpListener(HandlePost, port=0)
    print "Starting..."
    t.start()

    while t.server is None:
        time.sleep(.1)

    local_port = t.server.server_port
    local_ip = get_local_ip('172.27.1.1')
    print "Listening on %s:%d" % (local_ip, local_port)
    payload = {"submitted_by": "i.turturica@f5.com",
               "endpoint": "http://%s:%d/receiver" % (local_ip, local_port),
               "tests": [
                   #'tests/cascade/system/standalone/bigiq/discovery.py',
                   'tests/cascade/test_skel.py:Tests.test_hello_world_02'],
               "devices": {
                   'bigiq-1':
                   {'kind': 'tmos:bigiq',
                    'default': True,
                    'address': '10.145.194.29',
                    'admin password': 'admin',
                    'root password': 'default'},
                   'bigip-1':
                   {'kind': 'tmos:bigip',
                    'address': '10.144.10.196',
                    'admin password': 'admin',
                    'root password': 'default'},
                   'bigip-2':
                   {'kind': 'tmos:bigip',
                    'address': '10.144.10.197',
                    'admin password': 'admin',
                    'root password': 'default'},
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
        print 'Task status %s...' % status
        if status not in ('STARTED', 'PENDING'):
            t.server.running = False
        time.sleep(1)

    t.server.shutdown()
    t.join()
    print 'done!'
