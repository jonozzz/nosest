'''
Created on Oct 1, 2015

Monkey patches for restkit (which seems to be abandoned as of Aug 2013).

@author: jono
'''
import urllib.request, urllib.parse, urllib.error

import restkit
from restkit.util import encode, url_quote


def url_encode(obj, charset="utf8", encode_keys=False, safe='/:'):
    items = []
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            items.append((k, v))
    else:
        items = list(items)

    tmp = []
    for k, v in items:
        if encode_keys:
            k = encode(k, charset)

        if not isinstance(v, (tuple, list)):
            v = [v]

        for v1 in v:
            if v1 is None:
                v1 = ''
            elif callable(v1):
                v1 = encode(v1(), charset)
            else:
                v1 = encode(v1, charset)
            tmp.append('%s=%s' % (urllib.parse.quote(k, safe),
                                  urllib.parse.quote_plus(v1, safe)))
    return '&'.join(tmp)


def make_uri(base, *args, **kwargs):
    """Assemble a uri based on a base, any number of path segments,
    and query string parameters.

    """

    # get encoding parameters
    charset = kwargs.pop("charset", "utf-8")
    safe = kwargs.pop("safe", "/:")
    encode_keys = kwargs.pop("encode_keys", True)

    base_trailing_slash = False
    if base and base.endswith("/"):
        base_trailing_slash = True
        base = base[:-1]
    retval = [base]

    # build the path
    _path = []
    trailing_slash = False
    for s in args:
        if s is not None and isinstance(s, str):
            if len(s) > 1 and s.endswith('/'):
                trailing_slash = True
            else:
                trailing_slash = False
            _path.append(url_quote(s.strip('/'), charset, safe))

    path_str = ""
    if _path:
        path_str = "/".join([''] + _path)
        if trailing_slash:
            path_str = path_str + "/"
    elif base_trailing_slash:
        path_str = path_str + "/"

    if path_str:
        retval.append(path_str)

    params_str = url_encode(kwargs, charset, encode_keys, safe)
    if params_str:
        retval.extend(['?', params_str])

    return ''.join(retval)

# #1. Monkey patch these two functions to allow safe characters in query params.
restkit.util.url_encode = url_encode
restkit.util.make_uri = make_uri
