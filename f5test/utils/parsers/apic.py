from pyparsing import (Literal, Word, dictOf, restOfLine, alphas, ParseException)
from ..decorators import synchronized_with
from . import PYPARSING_LOCK


class OutputParseException(Exception):
    pass


@synchronized_with(PYPARSING_LOCK)
def colon_pairs_list(string):
    toplevel = dictOf(Word(alphas + "_") + Literal(": ").suppress(),
                      restOfLine)
    strings = string.strip().split('\n\n')
    ret = []
    try:
        for substring in strings:
            subdict = toplevel.parseString(substring).asDict()
            ret.append(dict(zip(map(lambda x: x.lower(), subdict.keys()),
                       subdict.values())))

        return ret

    except ParseException:
        raise OutputParseException(string)
