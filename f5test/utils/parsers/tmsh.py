'''
Created on Apr 03, 2013

Tested on tmsh scf output (or bigip.conf content) starting with 11.0.0.
Bigpipe format are partially supported. See caveats below.

Caveats:
- tmsh one-line output is not supported by the parser
- Comments are not supported by the encoder
- Constructs like following are not supported by the parser:
    order-by {
        {
            measure events_count
            sort-type desc
        }
    }
- Constructs like this are not parsed correctly (workaround: concatenate lines)
   key {
       options
          dont insert empty fragments
       profiles
          clientssl
              clientside

   }

@author: jono
'''
import collections
from fnmatch import fnmatch
import json
import re

from pyparsing import (Literal, Word, Group, ZeroOrMore, printables, OneOrMore,
                       Forward, Optional, removeQuotes, Suppress, QuotedString, ParserElement,
                       White, LineEnd, quotedString, delimitedList, nestedExpr,
                       pythonStyleComment, Combine, FollowedBy, SkipTo, Or,
                       originalTextFor)

from f5test.utils.decorators import synchronized_with
from f5test.utils.parsers import PYPARSING_LOCK
from f5test.utils.parsers.tcl import parse as tcl_parse
#from ..decorators import synchronized_with
#from . import PYPARSING_LOCK

# This is to support legacy bigpipe output and it should remain disabled.
OLD_STYLE_KEYS = False
BLOB_OPENER = '[BEGIN]'
BLOB_CLOSER = '[END]'


class RawString(str):
    pass


class RawDict(dict):
    pass


class Meta(type):
    def __repr__(self):
        return '<EOL>'


class RawEOL(object, metaclass=Meta):
    pass


class GlobDict(collections.OrderedDict):

    def set_key(self, key, value):
        self[RawString(key)] = value

    def rename_key(self, old, **kwargs):
        """Not optimum, but it should work fine for small dictionaries"""
        value = self[old]
        items = [(RawString(k % kwargs), v) if k == old else (RawString(k), v)
                 for k, v in self.items()]
        self.clear()
        self.update(items)
        return value

    def glob(self, match):
        """@match should be a glob style pattern match (e.g. '*.txt')"""
        return GlobDict([(k, v) for k, v in list(self.items()) if fnmatch(k, match)])

    def match(self, pattern):
        """@pattern should be a re style pattern match (e.g. VS\d+)"""
        return GlobDict([(k, v) for k, v in list(self.items()) if re.match(pattern, k)])

    def dumps(self):
        return dumps(self)

    def glob_keys(self, match):
        return [k.split(' ')[-1] for k in list(self.keys()) if fnmatch(k, match)]

    def format(self, _maxdepth=10, **fmt):
        def traverse(obj, curdepth, maxdepth):
            if curdepth >= maxdepth:
                return obj
            curdepth += 1
            T = type(obj)
            if isinstance(obj, collections.Mapping):
                return T((type(k)(k % fmt), traverse(v, curdepth, maxdepth))
                         for k, v in obj.items())
            elif isinstance(obj, (list, tuple, collections.Set)):
                return T((traverse(elem, curdepth, maxdepth) for elem in obj))
            else:
                if isinstance(obj, str):
                    obj = T(obj % fmt)
                return obj
        return traverse(self, 0, _maxdepth)


@synchronized_with(PYPARSING_LOCK)
def braces_parser(text, opener=BLOB_OPENER, closer=BLOB_CLOSER):
    cvtTuple = lambda toks: tuple(toks.asList())  # @IgnorePep8
    cvtRaw = lambda toks: RawString(' '.join(map(str, toks.asList())))  # @IgnorePep8
    cvtStr = lambda toks: str(' '.join(map(str, toks.asList())))  # @IgnorePep8
    cvtDict = lambda toks: GlobDict(toks.asList())  # @IgnorePep8
    extractText = lambda s, l, t: RawString(s[t._original_start:t._original_end])  # @IgnorePep8

    def pythonize(toks):
        s = toks[0]
        if s == 'true':
            return True
        elif s == 'false':
            return False
        elif s == 'none':
            return [None]
        elif s.isdigit():
            return int(s)
        elif re.match('(?i)^-?(\d+\.?e\d+|\d+\.\d*|\.\d+)$', s):
            return float(s)
        return toks[0]

    def noneDefault(s, loc, t):
        return t if len(t) else [RawEOL]

    # define punctuation as suppressed literals
    lbrace, rbrace = list(map(Suppress, "{}"))

    identifier = Word(printables, excludeChars='{}"\'')
    quotedStr = QuotedString('"', escChar='\\', multiline=True) | \
        QuotedString('\'', escChar='\\', multiline=True)
    quotedIdentifier = QuotedString('"', escChar='\\', unquoteResults=True) | \
        QuotedString('\'', escChar='\\', unquoteResults=True)
    dictStr = Forward()
    setStr = Forward()
    objStr = Forward()

    oddIdentifier = identifier + quotedIdentifier
    dictKey = quotedIdentifier | \
        Combine(oddIdentifier).setParseAction(cvtRaw)
    dictKey.setParseAction(cvtStr)

    dictValue = quotedStr | dictStr | setStr | \
        Combine(oddIdentifier).setParseAction(cvtRaw)

    if OLD_STYLE_KEYS:
        dictKey |= Combine(identifier + ZeroOrMore(White(' ') + (identifier + ~FollowedBy(Optional(White(' ')) + LineEnd()))))
        dictValue |= identifier.setParseAction(pythonize)
    else:
        dictKey |= identifier
        dictValue |= Or([delimitedList(identifier | quotedIdentifier, delim=White(' '), combine=True),
                         Combine(delimitedList(identifier | quotedIdentifier, delim=White(' '), combine=True) +
                                 Optional(White(' ') + originalTextFor(nestedExpr('{', '}')).setParseAction(
                                  extractText))
                                 ).setParseAction(cvtRaw)
                         ])

    ParserElement.setDefaultWhitespaceChars(' \t')
    dictEntry = Group(dictKey +
                      Optional(White(' ').suppress() + dictValue).setParseAction(noneDefault) +
                      Optional(White(' ').suppress()) +
                      LineEnd().suppress())
    dictStr << (lbrace + ZeroOrMore(dictEntry) + rbrace)
    dictStr.setParseAction(cvtDict)
    ParserElement.setDefaultWhitespaceChars(' \t\r\n')

    setEntry = identifier.setParseAction(pythonize) | quotedString.setParseAction(removeQuotes) | dictStr
    setStr << (lbrace + delimitedList(setEntry, delim=White()) + rbrace)
    setStr.setParseAction(cvtTuple)

    objEntry = dictStr.ignore(pythonStyleComment)
    objStr << delimitedList(objEntry, delim=LineEnd())

    return objStr.parseString(text)[0]


def dumps(obj):
    return TMSHEncoder(indent=4).encode(obj)


def parser(text):
    ret = tcl_parse(text)
    blacklist = ['ltm rule',
                 'gtm rule',
                 'cli script',
                 'sys application',
                 'rule',
                 'sys icall',
    ]

    #from pprint import pprint
    #pprint(ret)
    #return ret

    d = GlobDict()
    for command in ret[2]:
        if command[0] == 'Command':
            start = command[1][0]
            for bit in command[2]:
                if bit[0] == 'BracedLiteral':
                    stop = bit[1][0] - 1
                    content = bit[1]
                    break
            else:
                continue
            key = RawString(text[start:stop])
            value = text[content[0]:content[1]]
            if any(key.startswith(x) for x in blacklist):
                d[key] = RawString(value)
            else:
                d[key] = braces_parser(value)
    return d


ESCAPE_DCT = {
    '\\': '\\\\',
    '"': '\\"',
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\n',
    '\r': '\\r',
    '\t': '\t',
}


class TMSHEncoder(json.JSONEncoder):
    item_separator = ''
    key_separator = ' '

    def default(self, o):
        """By default use the string representation of the object."""
        return str(o)

    def iterencode(self, o, _one_shot=False):
        """Encode the given object and yield each string
        representation as available.

        For example::

            for chunk in JSONEncoder().iterencode(bigobject):
                mysocket.write(chunk)

        """
        if self.check_circular:
            markers = {}
        else:
            markers = None

        def _encoder(s):
            """Return a JSON representation of a Python string

            """
            def replace(match):
                return ESCAPE_DCT[match.group(0)]
            if not isinstance(s, RawString) and re.search('[\s%]', s):
                return '"' + json.encoder.ESCAPE.sub(replace, s) + '"'
            else:
                # return json.encoder.ESCAPE.sub(replace, s)
                return s

        def floatstr(o, allow_nan=self.allow_nan,
                     _repr=lambda o: format(o, '.2f'), _inf=json.encoder.INFINITY,
                     _neginf=-json.encoder.INFINITY):
            # Check for specials.  Note that this type of test is processor
            # and/or platform-specific, so do tests which don't depend on the
            # internals.

            if o != o:
                text = 'NaN'
            elif o == _inf:
                text = 'Infinity'
            elif o == _neginf:
                text = '-Infinity'
            else:
                return _repr(o)

            if not allow_nan:
                raise ValueError(
                    "Out of range float values are not JSON compliant: " +
                    repr(o))

            return text

        _iterencode = _make_iterencode(
            markers, self.default, _encoder, self.indent, floatstr,
            TMSHEncoder.key_separator, TMSHEncoder.item_separator, self.sort_keys,
            self.skipkeys, _one_shot)
        return _iterencode(o, -1)


def _make_iterencode(markers, _default, _encoder, _indent, _floatstr,
        _key_separator, _item_separator, _sort_keys, _skipkeys, _one_shot,
        ## HACK: hand-optimized bytecode; turn globals into locals
        ValueError=ValueError,  # @ReservedAssignment
        dict=dict,  # @ReservedAssignment
        float=float,  # @ReservedAssignment
        id=id,  # @ReservedAssignment
        int=int,  # @ReservedAssignment
        isinstance=isinstance,  # @ReservedAssignment
        list=list,  # @ReservedAssignment
        long=int,  # @ReservedAssignment
        str=str,  # @ReservedAssignment
        tuple=tuple,  # @ReservedAssignment
    ):

    def _iterencode_list(lst, _current_indent_level):
        if not lst:
            yield '{}'
            return
        if markers is not None:
            markerid = id(lst)
            if markerid in markers:
                raise ValueError("Circular reference detected")
            markers[markerid] = lst
        buf = '{'
        if _indent is not None:
            _current_indent_level += 1
            # newline_indent = '\n' + (' ' * (_indent * _current_indent_level))
            newline_indent = ' '
            separator = _item_separator + newline_indent
            buf += newline_indent
        else:
            newline_indent = None
            separator = _item_separator
        first = True
        for value in lst:
            if first:
                first = False
            else:
                buf = separator
            if isinstance(value, str):
                yield buf + _encoder(value)
            elif value is None:
                yield buf
            elif value is True:
                yield buf + 'true'
            elif value is False:
                yield buf + 'false'
            elif isinstance(value, int):
                yield buf + str(value)
            elif isinstance(value, float):
                yield buf + _floatstr(value)
            else:
                yield buf
                if isinstance(value, (list, tuple)):
                    chunks = _iterencode_list(value, _current_indent_level)
                elif isinstance(value, dict):
                    chunks = _iterencode_dict(value, _current_indent_level)
                else:
                    chunks = _iterencode(value, _current_indent_level)
                for chunk in chunks:
                    yield chunk
        if newline_indent is not None:
            _current_indent_level -= 1
            # yield '\n' + (' ' * (_indent * _current_indent_level))
            yield ' '
        yield '}'
        if markers is not None:
            del markers[markerid]

    def _iterencode_dict(dct, _current_indent_level):
        if not dct:
            yield '{}'
            return
        if markers is not None:
            markerid = id(dct)
            if markerid in markers:
                raise ValueError("Circular reference detected")
            markers[markerid] = dct
        if _current_indent_level >= 0:
            if not isinstance(dct, RawDict):
                yield '{'
        if _indent is not None:
            _current_indent_level += 1
            newline_indent = '\n' + (' ' * (_indent * _current_indent_level))
            item_separator = _item_separator + newline_indent
            if _current_indent_level:
                yield newline_indent
        else:
            newline_indent = None
            item_separator = _item_separator
        first = True
        if _sort_keys:
            items = sorted(list(dct.items()), key=lambda kv: kv[0])
        else:
            items = iter(dct.items())
        for key, value in items:
            if isinstance(key, str):
                pass
            # JavaScript is weakly typed for these, so it makes sense to
            # also allow them.  Many encoders seem to do something like this.
            elif isinstance(key, float):
                key = _floatstr(key)
            elif key is True:
                key = 'true'
            elif key is False:
                key = 'false'
            elif key is None:
                key = 'null'
            elif isinstance(key, int):
                key = str(key)
            elif _skipkeys:
                continue
            else:
                raise TypeError("key " + repr(key) + " is not a string")
            if first:
                first = False
            else:
                yield item_separator
            yield _encoder(key)
            if value is not RawEOL:
                yield _key_separator
            if isinstance(value, str):
                yield _encoder(value)
            elif value is None:
                yield 'none'
            elif value is RawEOL:
                yield ''
            elif value is True:
                yield 'true'
            elif value is False:
                yield 'false'
            elif isinstance(value, int):
                yield str(value)
            elif isinstance(value, float):
                yield _floatstr(value)
            else:
                if isinstance(value, (list, tuple)):
                    chunks = _iterencode_list(value, _current_indent_level)
                elif isinstance(value, dict):
                    chunks = _iterencode_dict(value, _current_indent_level)
                else:
                    chunks = _iterencode(value, _current_indent_level)
                for chunk in chunks:
                    yield chunk
        if newline_indent is not None:
            _current_indent_level -= 1
            yield '\n' + (' ' * (_indent * _current_indent_level))
        if _current_indent_level >= 0:
            if not isinstance(dct, RawDict):
                yield '}'
        if markers is not None:
            del markers[markerid]

    def _iterencode(o, _current_indent_level):
        if isinstance(o, str):
            yield _encoder(o)
        elif o is None:
            yield 'null'
        elif o is True:
            yield 'true'
        elif o is False:
            yield 'false'
        elif isinstance(o, int):
            yield str(o)
        elif isinstance(o, float):
            yield _floatstr(o)
        elif isinstance(o, (list, tuple, set)):
            for chunk in _iterencode_list(o, _current_indent_level):
                yield chunk
        elif isinstance(o, dict):
            for chunk in _iterencode_dict(o, _current_indent_level):
                yield chunk
        else:
            if markers is not None:
                markerid = id(o)
                if markerid in markers:
                    raise ValueError("Circular reference detected")
                markers[markerid] = o
            o = _default(o)
            for chunk in _iterencode(o, _current_indent_level):
                yield chunk
            if markers is not None:
                del markers[markerid]

    return _iterencode


if __name__ == '__main__':
    import pprint

    test = r"""
    # TMOS version: blab

    "/Common/address 2" {
    # test
        a-set {
            a1
            b1
            c2
            d2
            TCP::UDP
        }
        q-string "Multiline \"
        quoted string"
        single-line 'foo \' baz bar'
        subkey value
        a-none none
        number 100
        enabled 1
        ipv4 201.2.33.1
        ipv4-mask 10.10.2.3/24
        ipv6 2002:89f5::1
        number-alpha 1a
        one-line-set { a b c 1.1 2.3.4 600 none }
        ssl-ciphersuite ALL:!ADH:!EXPORT:!eNULL:!MD5:!DES:RC4+RSA:+HIGH:+MEDIUM:+LOW:+SSLv2
        subsub {
            boom blah
            alpha beta
            underscore in_value
            space after-value 
            another value
            gah
              test 123
            enabled
            child {
                okay
            }
        }
        "spaced key" {
            a value
        }
        just-one {
            key some-value
        }
        special:"key space" {}
        bool true
        empty { }
    }
    bigpipe keys {
        this is a long whitespaced key-value "with quotes"
        this is another long whitespaced key-value
    }
    ltm node node1 {}
    ltm node node2 {}

    ltm pool /exchange/gbb_exchange.app/gbb_exchange_ad_pool7 {
        app-service /exchange/gbb_exchange.app/gbb_exchange
        load-balancing-mode least-connections-member
        members {
            /exchange/10.75.2.16%1:443 {
                address 10.75.2.16%1
                app-service /exchange/gbb_exchange.app/gbb_exchange
            }
        }
        monitor min 1 of { /exchange/gbb_exchange.app/gbb_exchange_ad_https_monitor }
        service-down-action reset
        slow-ramp-time 300
    }

    #  -----
    cli script blah {
        monitor min 1 of { /exchange/gbb_exchange.app/gbb_exchange_ad_https_monitor }
    }

    ltm rule my-irule {
        # My irule
        partition Common
        if {not [info exists tmm_auth_http_collect_count]} {
            HTTP::collect
            set tmm_auth_http_successes 0
            set tmm_auth_http_collect_count 1
        } else {
            incr tmm_auth_http_collect_count
        }
    }

    sys management-ip 6.0.1.208/16 { }

    mgmt 172.27.66.162 {
       netmask 255.255.255.128
    }
    """

    #test = file('/tmp/profile_base.conf').read()
    #test = file('/tmp/wam_base.conf').read()
    #test = file('/tmp/bp946.conf').read()
    #test = file('/tmp/pme.conf').read()
    #test = file('/tmp/a.conf').read()
    #print "Input:", test.strip()
    result = parser(test)
    print("Result:")
    pprint.pprint(dict(result))

    print("Encoded:")
    #print dumps(result)

    print("Filter:")
    print(dumps(result.glob('cli script *')))
    print(dumps(result))
