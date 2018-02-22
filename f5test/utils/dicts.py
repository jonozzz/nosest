'''
Created on Jun 11, 2011

@author: jono
'''
import types
import collections


def merge(dst, src, skip_prefix='$', modifier=None):
    if isinstance(dst, dict) and isinstance(src, dict):
        for k, v in src.iteritems():
            if skip_prefix and isinstance(k, basestring) and k.startswith(skip_prefix):
                continue
            if callable(modifier):
                k, v = modifier(k, v)
            # Custom assignment
            if isinstance(v, types.LambdaType):
                v(k, dst)
            elif k not in dst:
                dst[k] = v
            else:
                dst[k] = merge(dst[k], v, skip_prefix, modifier)
    else:
        return src
    return dst


def flatten(*dict_args):
    '''
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    '''
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


def inverse(src, keys=None):
    """
    Reverts a dict of key:value into value:key.

    >>> src = dict(key1='val1', key2=['val2', 'val3'], key3='val3')
    >>> trans = dict(val3='gaga', val2='gaga')
    >>> invert_dict(src)
    {'val3': set(['key3', 'key2']), 'val2': set(['key2']), 'val1': set(['key1'])}
    >>> invert_dict(src, trans)
    {'val1': set(['key1']), 'gaga': set(['key3', 'key2'])}

    @param src: Source dict
    @type src: dict
    @param keys: Key transform dict
    @type keys: dict
    """
    outdict = {}
    if keys is None:
        keys = {}

    for k, lst in src.items():
        if type(lst) not in (types.TupleType, types.ListType, set,
                             types.DictType):
            lst = [lst]
        for entry in lst:
            entry = keys.get(entry, entry)
            outdict.setdefault(entry, set())
            outdict[entry].add(k)

    return outdict


def tuple2dict(data):
    """
    Converts nested lists into nested dicts.

    >>> tuple2dict([(1, [(2, {3:4}), (2,{4:1})])])
    {1: {2: {3: 4, 4: 1}}}

    @param data: Source nested list
    @type src: list
    """
    d = {}
    for item in data:
        key = item[0]
        value = item[1]
        if isinstance(value, list):
            value = tuple2dict(value)
        old = d.get(key)
        if not isinstance(old, dict):
            d[key] = value
        else:
            old.update(value)

    return d


def replace(dic, maxdepth=10, **params):
    """Replaces keys or values recursively in a dictionary.
    The params should contain the old and new value.

    Example:
    In [3]: replace({'a':{3: 'b'}}, old='b', new='x')
    Out[3]: {'a': {3: 'x'}}
    """
    assert 'old' in params
    assert 'new' in params

    def traverse(obj, curdepth, maxdepth):
        if curdepth >= maxdepth:
            return obj
        curdepth += 1
        T = type(obj)
        if isinstance(obj, collections.Mapping):
            return T((params['new'] if k == params['old'] else k,
                      traverse(v, curdepth, maxdepth))
                     for k, v in obj.iteritems())
        elif isinstance(obj, (list, tuple, collections.Set)):
            return T((traverse(elem, curdepth, maxdepth) for elem in obj))
        else:
            if obj == params['old']:
                obj = params['new']
            return obj
    return traverse(dic, 0, maxdepth)
