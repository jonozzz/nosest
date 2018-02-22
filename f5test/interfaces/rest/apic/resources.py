'''
Created on Mar 9, 2015

@author: jwong (Based off of rest/netx/resources.py)
'''
from ..core import RestInterface, AUTH
from ..driver import BaseRestResource, WrappedResponse
from ...config import ADMIN_ROLE
from f5test.interfaces.rest.apic.objects.system import (aaaLogin, aaaLogout,
                                                        aaaRefresh)
from restkit import ResourceError
from threading import Event, Thread
from f5test.base import AttrDict
import urlparse
import logging
import datetime

LOG = logging.getLogger(__name__)
STDOUT = logging.getLogger('stdout')
CURL_LOG = "curl -sk {credentials} {headers} -X {method} {payload} '{url}'"
MAX_LINE_LENGTH = 65536


class ApicResourceError(ResourceError):
    """Includes a parsed traceback as returned by the server."""

    def __init__(self, e):
        response = WrappedResponse(e.response, e.msg)
        super(ApicResourceError, self).__init__(msg=e.msg,
                                                http_code=e.status_int,
                                                response=response)

    def __str__(self):
        MAX_BODY_LENGTH = 1024
        if self.response.data and isinstance(self.response.data, dict):
            return ("{response.request.method} {response.final_url} failed:\n"
                    "Code: {data.imdata.error.@code}\n"
                    "Message: {data.imdata.error.@text}\n"
                    "".format(data=self.response.data,
                              response=self.response.response))
        else:
            return ("{response.request.method} {response.final_url} failed:\n"
                    "{body}\n"
                    "Status: {response.status}\n"
                    "".format(response=self.response.response,
                              body=self.response.body[:MAX_BODY_LENGTH]))


class ApicRestResource(BaseRestResource):
    api_version = 1

    def request(self, method, path=None, payload=None, headers=None,
                params_dict=None, odata_dict=None, **params):
        """Perform HTTP request.

        Returns a parsed JSON object (dict).

        :param method: The HTTP method
        :param path: string additional path to the uri
        :param payload: string or File object passed to the body of the request
        :param headers: dict, optional headers that will be added to HTTP
                        request.
        :param params_dict: Options parameters added to the request as a dict
        :param odata_dict: Similar to params_dict but keys will have a '$' sign
                           automatically prepended.
        :param params: Optional parameters added to the request
        """

        if odata_dict:
            dollar_keys = dict(('$%s' % x, y) for x, y in odata_dict.iteritems())
            if params_dict is None:
                params_dict = {}
            params_dict.update(dollar_keys)

        # Strip the schema and hostname part.
        path = urlparse.urlparse(path).path

        # Default ending path to .xml if it is not already there.
        if not path.endswith('.xml') and not path.endswith('.json'):
            path += '.xml'

        if path.endswith('.json'):
            self.default_content_type = 'application/json'
        elif self.element_tree and path.endswith('.xml'):
            self.default_content_type = 'application/xml; x-codec="et"'
        else:
            self.default_content_type = 'application/xml'

        try:
            wrapped_response = super(ApicRestResource, self).request(method, path=path,
                                                                     payload=payload,
                                                                     headers=headers,
                                                                     params_dict=params_dict,
                                                                     **params)
        except ResourceError, e:
            raise ApicResourceError(e)

        return wrapped_response.data


class ApicInterface(RestInterface):
    api_class = ApicRestResource
    creds_role = ADMIN_ROLE
    verbose = False

    class CookieHeaderFilter(object):
        """ Simple filter to manage cookie authentication"""

        def __init__(self, token):
            self.token = token

        def on_request(self, request):
            request.headers['Cookie'] = "APIC-Cookie=%s" % self.token

    class OnRequestLogFilter(object):
        """ Simple filter to log requests as they are sent out"""

        def __init__(self):
            self.log = STDOUT if ApicInterface.verbose else LOG

        def on_request(self, request):
            # We won't log multi-part requests.
            if isinstance(request.body, (type(None), basestring)):
                payload = credentials = ''
                if request.body:
                    payload = "-d '{}'".format(request.body.replace("'", "\\'")[:MAX_LINE_LENGTH])
                headers = []
                for name, value in request.headers.items():
                    # curl calculates content-length automatically
                    if name == 'Content-Length':
                        pass
                    else:
                        headers.append('-H "{}: {}"'.format(name, value))
                self.log.debug(CURL_LOG.format(method=request.method,
                                               path=request.path,
                                               url=request.url,
                                               headers=' '.join(headers),
                                               credentials=credentials,
                                               payload=payload))

    class OnResponseLogFilter(object):
        """ Simple filter to log responses as they come in"""

        def __init__(self):
            self.log = STDOUT if ApicInterface.verbose else LOG

        def on_response(self, resp, request):
            self.log.debug(resp._body.peek()[:MAX_LINE_LENGTH])

    def __init__(self, device=None, address=None, username=None, password=None,
                 port=None, proto='https', timeout=90, url=None, token=None,
                 *args, **kwargs):
        super(ApicInterface, self).__init__(device, address, username, password,
                                            port, proto, timeout, AUTH.TOKEN,
                                            url)
        self.token = token
        self.refresh = None

    class ApicRefresh(object):
        '''
        So this refresh for APIC is pretty whacky (seems different than how
        I would envisiion this working)...

        APIC has a timeout for its REST API calls. Because of this, we need
        to refresh the token for this interface. This will check if refresh
        needs to happen every 30 seconds. Below is how this will be used:
            t = ApicRefresh(self.api)
            t.start(<some timeout period in seconds>)
            .
            .
            .
            t.stop()

        When it is time to refresh, aaaRefresh will create a new token for us.
        Update the current token in this interface with the refreshed one. I
        thought one could make a GET call to aaaRefresh and the current token's
        timeout will get extended.
        '''
        PAUSE = 30

        def __init__(self, api=None, *args, **kwargs):
            self.api = api
            self.t_stop = None

        def start(self, timeout_interval):
            LOG.info("Starting refresh thread..")

            interval = int(timeout_interval) - self.PAUSE
            pause = self.PAUSE
            if interval < 0:
                interval = timeout_interval
                pause = interval - 0.5

            self.t_stop = Event()
            LOG.info("APIC timeout: {0}, pause: {1}".format(interval, pause))
            t = Thread(target=self.refresh, args=(interval, pause, self.t_stop))
            t.daemon = True
            t.start()

        def stop(self):
            if self.t_stop:
                LOG.info("Stopping refresh thread..")
                self.t_stop.set()

        def refresh(self, interval, pause, stop_event):
            initial_time = datetime.datetime.now()
            while not stop_event.is_set():
                current_time = datetime.datetime.now()
                if (current_time - initial_time) >= datetime.timedelta(seconds=interval):
                    LOG.info("Refreshing token for APIC REST Interface...")
                    # Get refreshed token
                    resp = self.api.get(aaaRefresh.URI)
                    if isinstance(resp, AttrDict):
                        token = resp.imdata.aaaLogin['@token']
                    else:
                        token = resp.find('aaaLogin').get('token')

                    # Update token in header
                    for x in self.api.client.request_filters:
                        if isinstance(x, ApicInterface.CookieHeaderFilter):
                            x.token = token

                    # Update time when token got updated
                    initial_time = current_time
                stop_event.wait(pause)

    def open(self):  # @ReservedAssignment
        url = "{0[proto]}://{0[address]}:{0[port]}".format(self.__dict__)
        api = self.api_class(url, timeout=self.timeout)
        api.element_tree = False
        if not self.token:
            payload = aaaLogin()
            payload.aaaUser['@name'] = self.username
            payload.aaaUser['@pwd'] = self.password
            ret = api.post(aaaLogin.URI, payload)
            self.token = ret.imdata.aaaLogin['@token']
        api.client.request_filters.append(self.CookieHeaderFilter(self.token))
        self.api = api
        self.api.client.request_filters.append(self.OnRequestLogFilter())
        self.api.client.response_filters.append(self.OnResponseLogFilter())

        refresh_timeout = ret.imdata.aaaLogin['@refreshTimeoutSeconds']
        self.refresh = ApicInterface.ApicRefresh(self.api)
        self.refresh.start(refresh_timeout)

    @property
    def version(self):
        from ....utils.version import Version

        # I do not know if there is a better URI yet. This one is pretty
        # hard-coded.
        uri = '/api/node/class/topology/pod-1/node-1/firmwareCtrlrRunning.xml'
        version = self.api.get(uri).imdata.firmwareCtrlrRunning['@version']
        return Version("{0}".format(version))

    def close(self):  # @ReservedAssignment
        try:
            if self.refresh:
                LOG.info("Stopping refresh thread..")
                self.refresh.stop()

            if self.token:
                self.api.element_tree = False
                payload = aaaLogout()
                payload.aaaUser['@name'] = self.username
                self.api.post(aaaLogout.URI, payload)
        finally:
            self.token = None
            return super(ApicInterface, self).close()
