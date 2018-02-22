'''
Created on Feb 26, 2012

@author: jono
'''
from ..core import RestInterface, AUTH
from .objects.system import AuthnLogin, AuthnExchange
from .objects.shared import DeviceInfo
from ..driver import BaseRestResource, WrappedResponse
from ...config import ADMIN_ROLE
from ....defaults import ADMIN_PASSWORD, ADMIN_USERNAME
from ....utils.querydict import QueryDict
from restkit import ResourceError, RequestError
from f5test.utils.wait import wait, wait_args
from threading import Event, Thread
import urlparse
import logging
import urllib
import base64
import datetime

LOG = logging.getLogger(__name__)
STDOUT = logging.getLogger('stdout')
LOCALHOST_URL_PREFIX = 'http://localhost:8100'
CURL_LOG = "curl -X {method} {payload} '{url}' -sk {credentials} {headers}"
MAX_LINE_LENGTH = 65536


def localize_uri(uri):
    if hasattr(uri, 'selfLink'):
        uri = uri.selfLink
    return urlparse.urljoin(LOCALHOST_URL_PREFIX, uri)


class EmapiResourceError(ResourceError):
    """Includes a parsed java traceback as returned by the server."""

    def __init__(self, e):
        response = WrappedResponse(e.response, e.msg)
        super(EmapiResourceError, self).__init__(msg=e.msg,
                                                 http_code=e.status_int,
                                                 response=response)

    def __str__(self):
        MAX_BODY_LENGTH = 1024
        if self.response.data and isinstance(self.response.data, dict):
            tb = self.response.data.errorStack \
                if isinstance(self.response.data.errorStack, list) else []
            return ("{response.request.method} {response.final_url} failed:\n"
                    "{tb}\n"
                    "Operation ID: {data.restOperationId}\n"
                    "Code: {data.code}\n"
                    "Message: {data.message}\n"
                    "".format(tb='  \n'.join(map(lambda x: "  " + x, tb)),
                              data=self.response.data,
                              response=self.response.response))
        else:
            return ("{response.request.method} {response.final_url} failed:\n"
                    "{body}\n"
                    "Status: {response.status}\n"
                    "".format(response=self.response.response,
                              body=self.response.body[:MAX_BODY_LENGTH]))

    def __repr__(self):
        return ("{name}({response.request.method} {response.final_url}) {response.status}"
                .format(response=self.response.response,
                        name=type(self).__name__))


class EmapiRestResource(BaseRestResource):
    api_version = 1
    verbose = False

    def request(self, method, path=None, payload=None, headers=None,
                params_dict=None, odata_dict=None, **params):
        """Perform HTTP request.

        Returns a parsed JSON object (dict).

        :param method: The HTTP method
        :param path: string additionnal path to the uri
        :param payload: string or File object passed to the body of the request
        :param headers: dict, optionnal headers that will be added to HTTP
                        request.
        :param params_dict: Options parameters added to the request as a dict
        :param odata_dict: Similar to params_dict but keys will have a '$' sign
                           automatically prepended.
        :param params: Optionnal parameterss added to the request
        """
        FAILED_AUTHENTICATION = "java.security.GeneralSecurityException: Invalid registered claims."

        if odata_dict:
            dollar_keys = dict(('$%s' % x, y) for x, y in odata_dict.iteritems())
            if params_dict is None:
                params_dict = {}
            params_dict.update(dollar_keys)

        if path is not None:
            path = str(path)
            bits = path.split('?', 1)
            if len(bits) > 1:
                path = bits[0]
                query_dict = QueryDict(bits[1])
                if not params_dict:
                    params_dict = {}
                params_dict.update(query_dict)

        # Strip the schema and hostname part.
        path = urlparse.urlparse(path).path
        try:
            wrapped_response = super(EmapiRestResource, self).request(method, path=path,
                                                                      payload=payload,
                                                                      headers=headers,
                                                                      params_dict=params_dict,
                                                                      **params)
        except ResourceError, e:
            if e.status_int == 401 and FAILED_AUTHENTICATION in e.msg:
                LOG.error("Authentication Token Expired! Was there a restart?")
            raise EmapiResourceError(e)

        return wrapped_response.data


class EmapiInterface(RestInterface):
    """
    @param login_ref: Reference to auth provider
      Ex: {"link": "https://localhost/mgmt/cm/system/authn/providers/radius/5fb32248-722c-4ab4-8e6b-e223027e9d22/login"}
    """
    api_class = EmapiRestResource
    creds_role = ADMIN_ROLE
    verbose = False
    EmapiResourceError = EmapiResourceError

    class TokenHeaderFilter(object):
        """ Simple filter to manage iControl REST token authentication"""

        def __init__(self, token):
            self.token = token

        def on_request(self, request):
            request.headers['X-F5-Auth-Token'] = self.token.token

    class OnRequestLogFilter(object):
        """ Simple filter to log requests as they are sent out"""

        def __init__(self):
            self.log = STDOUT if EmapiInterface.verbose else LOG

        def on_request(self, request):
            # We won't log multi-part requests.
            # We want to trim F5 Authentication headers to their begin/end
            if isinstance(request.body, (type(None), basestring)):
                payload = credentials = ''
                if request.body:
                    payload = "-d '{}'".format(request.body.replace("'", "\\'")[:MAX_LINE_LENGTH])
                headers = []
                for name, value in request.headers.items():
                    # Recover credentials from Basic auth header
                    if name == 'Authorization':
                        type_, auth = value.split()
                        if type_ == 'Basic':
                            credentials = "-u " + base64.b64decode(auth.decode())
                    # curl calculates content-length automatically
                    elif name == 'Content-Length':
                        pass
                    else:
                        if 'X-F5-Auth-Token' in name and value and len(value) > 70:
                            # trim the auth token to free logs
                            value = "{}[...]{}".format(value[:25], value[-35:])
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
            self.log = STDOUT if EmapiInterface.verbose else LOG

        def on_response(self, resp, request):
            self.log.debug(resp._body.peek()[:MAX_LINE_LENGTH])

    class RestIfcRefresh(object):
        '''
        (BQ 5.0 and beyond only)
        '''
        PAUSE = 270  # check every 4'30"

        def __init__(self, api=None, *args, **kwargs):
            self.api = api
            self.t_stop = None
            self.token = None

        def start(self, timeout_interval, refreshtoken):
            LOG.debug("rstifc: Authn Token: starting new refresh thread...")
            pause = self.PAUSE
            interval = int(timeout_interval) - pause
            if interval < 0:
                interval = timeout_interval
                pause = interval - 0.5

            self.t_stop = Event()
            LOG.debug("rstifc: Authn Token: retry at {0}s before every expiration, "
                      "pausing: {1}s".format(interval, pause))
            t = Thread(target=self.refresh, args=(interval, pause, self.t_stop, refreshtoken))
            t.daemon = True
            t.start()

        def stop(self):
            if self.t_stop:
                LOG.debug("rstifc: Authn Token: Stopping refresh thread..")
                self.t_stop.set()
            return self.token

        def refresh(self, interval, pause, stop_event, refreshtoken):
            initial_time = datetime.datetime.now()
            while not stop_event.is_set():
                current_time = datetime.datetime.now()
                if (current_time - initial_time) >= datetime.timedelta(seconds=interval):
                    LOG.debug("rstifc: Authn Token: Refreshing token...")
                    payload = AuthnExchange()
                    payload.refreshToken.token = refreshtoken
                    ret = self.api.post(AuthnExchange.URI, payload)
                    self.token = ret.token
                    # Update token in header
                    LOG.debug("rstifc: Authn Token: Updating Token Now.")
                    self.api.client.request_filters.append(EmapiInterface.TokenHeaderFilter(self.token))
                    # Update time when token got updated
                    initial_time = current_time
                stop_event.wait(pause)

    def __init__(self, device=None, address=None, username=None, password=None,
                 port=None, proto='https', timeout=90, auth=None, url=None,
                 login_ref=None, token=None, *args, **kwargs):
        username = username or ADMIN_USERNAME
        password = password or ADMIN_PASSWORD
        super(EmapiInterface, self).__init__(device, address, username, password,
                                             port, proto, timeout, auth, url)
        self.login_ref = login_ref
        self.token = token
        self.refresh_token = None
        self.token_timeout = None
        self.refresh = None
        self.auth = auth

    @property
    def version(self):
        from ....utils.version import Version
        tmp = self.api.default_params
        self.api.default_params = None
        try:
            ret = self.api.get(DeviceInfo.URI)
        finally:
            self.api.default_params = tmp
        return Version("{0.product} {0.version} {0.build}".format(ret))

    def open(self):  # @ReservedAssignment
        if self.is_opened():
            return self.api

        if self.auth is None:
            self.auth = AUTH.BASIC
            # Attempt to open a temporary interface with admin credentials
            try:
                with RestInterface(device=self.device, address=self.address) as ifc:
                    v = ifc.version
                    # Prefer TOKEN auth in 5.0+
                    if v >= 'bigiq 5.0':
                        self.auth = AUTH.TOKEN
            except:  # hales
                #self.auth = AUTH.TOKEN
                pass

        if self.auth == AUTH.BASIC:
            super(EmapiInterface, self).open()
        elif self.auth == AUTH.TOKEN:
            quoted = dict(map(lambda (k, v): (k, urllib.quote_plus(str(v))),
                              self.__dict__.iteritems()))
            url = "{0[proto]}://{0[username]}:{0[password]}@{0[address]}:{0[port]}".format(quoted)
            api = self.api_class(url, timeout=self.timeout)
            if not self.token:
                payload = AuthnLogin()
                payload.username = self.username
                payload.password = self.password
                payload.loginReference = self.login_ref
                ret = api.post(AuthnLogin.URI, payload)
                try:
                    self.token = ret.token
                    self.token_timeout = self.token.timeout
                    self.refresh_token = ret.refreshToken and ret.refreshToken.token
                except:
                    raise
            if self.token:
                api.client.request_filters.append(self.TokenHeaderFilter(self.token))
            else:  # default to basic auth in case token can't be retrieved
                LOG.warning("Requested rstifc with Token Auth didn't yield a token for device {0}. "
                            "Defaulting to Basic...".format(self.device))
                super(EmapiInterface, self).open()
            self.api = api
            if self.refresh_token:
                self.refresh = EmapiInterface.RestIfcRefresh(self.api)
                self.refresh.start(self.token_timeout, self.refresh_token)
        else:
            raise NotImplementedError(self.auth)

        self.api.client.request_filters.append(self.OnRequestLogFilter())
        self.api.client.response_filters.append(self.OnResponseLogFilter())
        return self.api

    def close(self, *args, **kwargs):  # @ReservedAssignment
        try:
            if self.refresh:
                LOG.debug("rstifc: Attempt stopping refresh thread..")
                self.token = self.refresh.stop()
                LOG.debug("rstifc: Refresh thread Stopped...")
            # BZ650017 - no need to delete access token
            # if self.token:
            #     self.api.delete(self.token.selfLink)
        except (RequestError, EmapiResourceError), e:
            LOG.error('Failed to stop refresh token thread or delete token on rstifc close: %s', e)
        finally:
            self.token = None
            return super(EmapiInterface, self).close()
