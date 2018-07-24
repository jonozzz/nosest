from pyparsing import (Literal, Word, dictOf, restOfLine, alphas, ParseException)
from ..decorators import synchronized_with
from . import PYPARSING_LOCK


class VersionFileParseException(Exception):
    pass


@synchronized_with(PYPARSING_LOCK)
def colon_pairs_dict(string):
    toplevel = dictOf(Word(alphas + "_") + Literal(": ").suppress(),
                      restOfLine)
    try:
        ret = toplevel.parseString(string).asDict()
        return dict(list(zip([x.lower() for x in list(ret.keys())], list(ret.values()))))

    except ParseException:
        raise VersionFileParseException(string)


@synchronized_with(PYPARSING_LOCK)
def equals_pairs_dict(string):
    toplevel = dictOf(Word(alphas + "_") + Literal("=").suppress(),
                      restOfLine)
    try:
        ret = toplevel.parseString(string).asDict()
        return dict(list(zip([x.lower() for x in list(ret.keys())], list(ret.values()))))

    except ParseException:
        raise VersionFileParseException(string)
