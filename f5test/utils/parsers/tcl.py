import string


class ParseError(Exception):
    def __init__(self, msg, script, cursor):
        self.msg = msg
        self.script = script
        self.cursor = cursor

    def __str__(self):
        row, col = self.script.row_col(self.cursor)
        self.location = "At (%d, %d): " % (row, col)
        self.text = self.location + self.msg

        return repr(self.text)


def parse_whitespace(script, cursor, len_script, in_command_subst):
    while cursor < len_script:
        if script[cursor] in [' ', '\t']:
            cursor += 1

        else:
            break

    return ('Whitespace', cursor, [])


def parse_comment(script, cursor, len_script, in_command_subst):
    while cursor < len_script:
        if script[cursor] not in ['\r', '\n']:
            cursor += 1

        else:
            break

    while cursor < len_script:
        if script[cursor] in ['\r', '\n']:
            cursor += 1

        else:
            break

    return ('Comment', cursor, [])


def parse_separator(script, cursor, len_script, in_command_subst):
    return ('Separator', cursor + 1, [])


def parse_raw_word(script, cursor, len_script, in_command_subst):
    portions = []
    if in_command_subst:
        terminators = [' ', '\t', ';', '\r', '\n', ']']

    else:
        terminators = [' ', '\t', ';', '\r', '\n']

    start = cursor
    while cursor < len_script:
        c = script[cursor]

        if c in terminators:
            break

        elif c == '\\':
            if cursor > start:
                portions.append(('RawLiteral', (start, cursor), []))

            start = cursor

            type, cursor, sub_tree = parse_backslash_subst(
                                       script, cursor, len_script,
                                       in_command_subst)
            portions.append((type, (start, cursor), sub_tree))
            start = cursor

        elif c == '$':
            # this is tricky: if the $ is not followed by alphanum, underscore,
            # colons then it is treated as literal so must first try to parse
            # it as variable substitution and if it fails then pretend
            # nothing happens
            possible_start = cursor

            type, possible_cursor, sub_tree = parse_variable_subst(
                                                   script, cursor, len_script,
                                                   in_command_subst)

            if ((type == 'RawLiteral') and
                (script[possible_start:possible_cursor] == '$')):
                # I find it more consistent to let the '$' fuse with possibly
                # previously parsed 'RawLiteral' tokens
                cursor += 1

            else:
                # so it was a valid variable substitution after all ...
                if cursor > start:
                    portions.append(('RawLiteral', (start, cursor), []))

                portions.append((type,
                                 (possible_start, possible_cursor), sub_tree))
                start = cursor = possible_cursor

        elif c == '[':
            if cursor > start:
                portions.append(('RawLiteral', (start, cursor), []))

            start = cursor

            type, cursor, sub_tree = parse_command_subst(
                                          script, cursor, len_script,
                                          in_command_subst=True)
            portions.append((type, (start, cursor), sub_tree))
            start = cursor

        else:
            cursor += 1

    if cursor > start:
        portions.append(('RawLiteral', (start, cursor), []))

    if len(portions) == 1:
        type, (_, cursor), sub_tree = portions[0]

        return (type, cursor, sub_tree)

    else:
        return ('RawMixOf', cursor, portions)


def parse_quoted_word(script, cursor, len_script, in_command_subst):
    return parse_enclosed_word(
                 script, cursor, len_script, in_command_subst, '"',
                 only_whitespace_chars_after_end_char=True)


def parse_enclosed_word(script, cursor, len_script, in_command_subst,
                        end_character, only_whitespace_chars_after_end_char):
    portions = []
    if in_command_subst:
        separators = [';', '\r', '\n', ']']

    else:
        separators = [';', '\r', '\n']

    cursor += 1
    start = cursor
    while cursor < len_script:
        c = script[cursor]

        if c == end_character:
            break

        elif c == '[':
            if cursor > start:
                portions.append(('RawLiteral', (start, cursor), []))

            start = cursor

            type, cursor, sub_tree = parse_command_subst(
                                            script, cursor, len_script,
                                            in_command_subst=True)
            portions.append((type, (start, cursor), sub_tree))
            start = cursor

        elif c == '\\':
            if cursor > start:
                portions.append(('RawLiteral', (start, cursor), []))

            start = cursor

            type, cursor, sub_tree = parse_backslash_subst(
                                           script, cursor, len_script,
                                           in_command_subst)
            portions.append((type, (start, cursor), sub_tree))
            start = cursor

        elif c == '$':
            # for explanation about the solution here
            # see the comments in parse_raw_word
            possible_start = cursor

            type, possible_cursor, sub_tree = parse_variable_subst(
                                                   script, cursor, len_script,
                                                   in_command_subst)

            if ((type == 'RawLiteral') and
                (script[possible_start:possible_cursor] == '$')):
                cursor += 1

            else:
                if cursor > start:
                    portions.append(('RawLiteral', (start, cursor), []))

                portions.append((type,
                                 (possible_start, possible_cursor), sub_tree))
                start = cursor = possible_cursor

        else:
            cursor += 1

    if ((cursor < len_script) and
        (script[cursor] == end_character)):
        if only_whitespace_chars_after_end_char:
            # closing double quote ends the word, next must be
            # a whitespace or terminator
            if ((cursor + 1 < len_script) and
                (script[cursor + 1] not in (separators + [' ', '\t']))):

                raise ParseError('Extra characters after closing '
                                 + end_character + '.', script, cursor + 1)

        if cursor > start:
            portions.append(('RawLiteral', (start, cursor), []))

        if len(portions) == 0:
            return ('QuotedLiteral', cursor + 1, [])

        if len(portions) == 1:
            type, _, _ = portions[0]

            if type == 'RawLiteral':
                return ('QuotedLiteral', cursor + 1, [])

        return ('QuotedMixOf', cursor + 1, portions)

    else:
        raise ParseError('Missing closing '
                          + end_character + '.', script, cursor)


def parse_command_subst(script, cursor, len_script, in_command_subst):
    _, cursor, commands = parse_script(
                                 script, cursor + 1, len_script,
                                 in_command_subst=True)

    # check if command substitution properly closed by bracket ']'
    if script[cursor - 1] == ']':

        # and get rid of that ']' token because we also don't store
        # the opening '['
        type_last_command, (start_last_command, end_last_command), \
        content_last_command = commands.pop()

        del content_last_command[-1]
        end_last_command -= 1

        if content_last_command:
            commands.append(
               (type_last_command, (start_last_command, end_last_command),
                content_last_command))

        return ('SubstitutionCommand', cursor, commands)

    else:
        raise ParseError('Missing: ].', script, cursor)


def parse_braced_word(script, cursor, len_script, in_command_subst):
    portions = []
    brace_level = 1
    cursor += 1
    start = cursor

    while cursor < len_script:
        c = script[cursor]

        if c == '{':
            brace_level += 1
            cursor += 1

        elif c == '}':
            brace_level -= 1
            cursor += 1

        elif c == '\\':
            if script[cursor + 1] in ['\r', '\n']:
                start = cursor
                cursor += 1

                while cursor < len_script:
                    if script[cursor] in ['\r', '\n', ' ', '\t']:
                        cursor += 1

                    else:
                        break

                portions.append(('BackslashSubstitutionEOL',
                                (start, cursor), []))
                start = cursor

            else:
                cursor += 2

        else:
            cursor += 1

        if brace_level == 0:
            break

    if brace_level == 0:
        return ('BracedLiteral', cursor, portions)

    else:
        raise ParseError('Missing: }.', script, cursor)


def parse_word(script, cursor, len_script, in_command_subst):
    c = script[cursor]

    if c == '"':
        return parse_quoted_word(script, cursor, len_script, in_command_subst)

    elif c == '{':
        return parse_braced_word(script, cursor, len_script, in_command_subst)

    else:
        return parse_raw_word(script, cursor, len_script, in_command_subst)


def parse_backslash_subst(script, cursor, len_script, in_command_subst):
    control_chars = 'abfnrtv'

    cursor += 1

    if cursor < len_script:
        c = script[cursor]

    else:
        raise ParseError('Incomplete backslash substitution at end of script.',
                          script, cursor)

    if c in control_chars:
        return ('BackslashSubstitutionCONTROLCHAR', cursor + 1, [])

    elif c in ['\r', '\n']:
        while cursor < len_script:
            if script[cursor] in ['\r', '\n', ' ', '\t']:
                cursor += 1

            else:
                break

        return ('BackslashSubstitutionEOL', cursor, [])

    elif c in string.octdigits:
        cursor += 1
        counter = 1

        while cursor < len_script:
            if script[cursor] in string.octdigits:
                counter += 1
                cursor += 1

            else:
                break

            if counter == 3:
                break

        return ('BackslashSubstitutionOCTAL', cursor, [])

    elif c == 'x':
        cursor += 1
        counter = 0

        while cursor < len_script:
            if script[cursor] in string.hexdigits:
                counter += 1
                cursor += 1

            else:
                break

        if counter == 0:
            return ('BackslashSubstitutionCHAR', cursor, [])

        elif counter == 1:
            return ('BackslashSubstitutionHEX1', cursor, [])

        elif counter == 2:
            return ('BackslashSubstitutionHEX2', cursor, [])

        else:
            return ('BackslashSubstitutionHEXLAST2', cursor, [])

    elif c == 'u':
        cursor += 1
        counter = 0

        while cursor < len_script:
            if script[cursor] in string.hexdigits:
                counter += 1
                cursor += 1

            else:
                break

            if counter == 4:
                break

        if counter == 0:
            return ('BackslashSubstitutionCHAR', cursor, [])

        return ('BackslashSubstitutionUNICODECHAR', cursor, [])

    else:
        return ('BackslashSubstitutionCHAR', cursor + 1, [])


def parse_variable_subst(script, cursor, len_script, in_command_subst):
    start = cursor
    cursor += 1

    while cursor < len_script:
        c = script[cursor]

        if c in (string.letters + string.digits + "_"):
            cursor += 1

        elif c == ':':
            if ((cursor + 1 < len_script) and (script[cursor + 1] == ':')):
                cursor += 2
                # two or more adjacent colons are treated as
                # one namespace separator
                while cursor < len_script:
                    if script[cursor] != ':':
                        break

                    else:
                        cursor += 1

            else:
                break

        elif c == '{':
            while cursor < len_script:
                if script[cursor] == '}':
                    break

                cursor += 1

            if cursor < len_script:
                return ('SubstitutionScalarVariable', cursor + 1,
                        [('BracedLiteral', (start + 1, cursor + 1), [])])

            else:
                raise ParseError(
                         "Missing close brace in variable substitution.",
                         script, cursor)

        elif c == '(':
            array_name = ('RawLiteral', (start + 1, cursor), [])
            start = cursor
            type, cursor, \
            sub_tree = parse_enclosed_word(
                                   script, cursor, len_script,
                                   in_command_subst, ')',
                                   only_whitespace_chars_after_end_char=False)
            array_index = (type, (start, cursor), sub_tree)

            return ('SubstitutionArray', cursor, [array_name, array_index])

        else:
            break

    if cursor > start + 1:
        return ('SubstitutionScalarVariable', cursor, [])

    else:
        return ('RawLiteral', cursor, [])


def parse_command(script, cursor, len_script, in_command_subst):
    portions = []
    command_complete = False

    if in_command_subst:
        separators = [';', '\r', '\n', ']']

    else:
        separators = [';', '\r', '\n']

    while cursor < len_script:
        start = cursor
        c = script[cursor]

        if c in [' ', '\t']:
            fn = parse_whitespace

        elif c in separators:
            fn = parse_separator
            command_complete = True

        else:
            fn = parse_word

        type, cursor, sub_tree = fn(script, cursor, len_script,
                                    in_command_subst)
        portions.append((type, (start, cursor), sub_tree))

        if command_complete:
            break

    return ('Command', cursor, portions)


def parse_script(script, cursor, len_script, in_command_subst):
    portions = []

    while cursor < len_script:
        if script[cursor] == '#':
            fn = parse_comment

        elif script[cursor] in [' ', '\t']:
            fn = parse_whitespace

        else:
            fn = parse_command

        start = cursor
        type, cursor, sub_tree = fn(script, cursor, len_script,
                                    in_command_subst)

        portions.append((type, (start, cursor), sub_tree))

        if (in_command_subst and (script[cursor - 1] == ']')):
            break

    return ('Script', cursor, portions)


class ParseString(str):
    """
    Like regular Python string but with easy mapping from
    cursor position to line/column numbers, EOLs recognized
    according to host OS
    """
    def __init__(self, text):
        str.__init__(text)
        import os
        eol = os.linesep

        self.line_breaks = []
        while True:
            try:
                if self.line_breaks:
                    self.line_breaks.append(
                        text.index(eol,
                                    self.line_breaks[-1]
                                    + len(eol)) + len(eol) - 1)

                else:
                    self.line_breaks = [text.index(eol) + len(eol) - 1]

            except ValueError:
                break

    def row_col(self, cursor):
        # we allow the cursor to be past the end of the string
        # because due to nature of parsing we might encounter
        # situations where we exhausted all input but eg. missing
        # a closing brace etc.
        if cursor < 0:
            raise IndexError("string index out of range")

        row = 1
        previous_line_break = 0
        line_break = None

        for line_break in self.line_breaks:
            if line_break >= cursor:
                break

            else:
                row += 1
                previous_line_break = line_break

        if ((line_break is None) or (row == 1)):
            return (1, cursor)

        else:
            return (row, cursor - (previous_line_break + 1))


def ParseString_tests():  # pragma: nocover
    r'''
    >>> import os; eol = os.linesep

    >>> p = ParseString("")
    >>> p.row_col(-1)
    Traceback (most recent call last):
    ...
    IndexError: string index out of range
    >>> p.row_col(0)
    (1, 0)
    >>> p.row_col(1)
    (1, 1)

    >>> p = ParseString(eol)
    >>> p.row_col(0)
    (1, 0)
    >>> p.row_col(len(eol))
    (2, 0)

    >>> p = ParseString("a")
    >>> p.row_col(0)
    (1, 0)

    >>> p = ParseString("a" + eol)
    >>> p.row_col(0)
    (1, 0)
    >>> p.row_col(p.index(eol))
    (1, 1)
    >>> p.row_col(p.index(eol) + len(eol))
    (2, 0)

    >>> p = ParseString("a" + eol + "b")
    >>> p.row_col(0)
    (1, 0)
    >>> p.row_col(p.index("b"))
    (2, 0)
    '''


def parse(script, start=0):
    type, cursor, sub_tree = parse_script(ParseString(script),
                                          start, len(script),
                                          in_command_subst=False)

    return (type, (start, cursor), sub_tree)


def dodekalogue():  # pragma: nocover
    r'''
    Rules

    The following rules define the syntax and semantics of the Tcl language:

    [1] Commands.
        A Tcl script is a string containing one or more commands.

        >>> parse("")
        ('Script', (0, 0), [])

        Semicolons
        >>> parse("a;")
        ('Script', (0, 2), [('Command', (0, 2), [('RawLiteral', (0, 1), []), ('Separator', (1, 2), [])])])

        >>> parse("a;b")
        ('Script', (0, 3), [('Command', (0, 2), [('RawLiteral', (0, 1), []), ('Separator', (1, 2), [])]), ('Command', (2, 3), [('RawLiteral', (2, 3), [])])])

        and newlines are command separators

        >>> parse("a\nb")
        ('Script', (0, 3), [('Command', (0, 2), [('RawLiteral', (0, 1), []), ('Separator', (1, 2), [])]), ('Command', (2, 3), [('RawLiteral', (2, 3), [])])])

        >>> parse("\nb")
        ('Script', (0, 2), [('Command', (0, 1), [('Separator', (0, 1), [])]), ('Command', (1, 2), [('RawLiteral', (1, 2), [])])])

        unless quoted

        >>> parse("a\;b")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('RawLiteral', (0, 1), []), ('BackslashSubstitutionCHAR', (1, 3), []), ('RawLiteral', (3, 4), [])])])])

        as described below. Close brackets are command terminators
        during command substitution (see below) unless quoted.

        >>> parse("[a\]b]")
        ('Script', (0, 6), [('Command', (0, 6), [('SubstitutionCommand', (0, 6), [('Command', (1, 5), [('RawMixOf', (1, 5), [('RawLiteral', (1, 2), []), ('BackslashSubstitutionCHAR', (2, 4), []), ('RawLiteral', (4, 5), [])])])])])])

    [2] Evaluation.
        A command is evaluated in two steps. First, the Tcl
        interpreter breaks the command into words and performs
        substitutions as described below. These substitutions are
        performed in the same way for all commands. The first word
        is used to locate a command procedure to carry out the
        command, then all of the words of the command are passed to the
        command procedure. The command procedure is free to
        interpret each of its words in any way it likes, such as an
        integer, variable name, list, or Tcl script.  Different
        commands interpret their words differently.

    [3] Words.
        Words of a command are separated by white space (except for
        newlines, which are command separators).

        >>> parse("a b")
        ('Script', (0, 3), [('Command', (0, 3), [('RawLiteral', (0, 1), []), ('Whitespace', (1, 2), []), ('RawLiteral', (2, 3), [])])])

    [4] Double quotes.
        If the first character of a word is double quote (") then
        the word is terminated by the next double quote character.

        >>> parse("\"\"")
        ('Script', (0, 2), [('Command', (0, 2), [('QuotedLiteral', (0, 2), [])])])

        >>> parse("\"ab\"")
        ('Script', (0, 4), [('Command', (0, 4), [('QuotedLiteral', (0, 4), [])])])

        >>> parse("a\"b")
        ('Script', (0, 3), [('Command', (0, 3), [('RawLiteral', (0, 3), [])])])

        >>> parse("\"")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 1): Missing closing ".'

        If semicolons, close brackets, or white space characters
        (including newlines) appear between the quotes then they are
        treated as ordinary characters and included in the word.

        >>> parse("\"a;] \"")
        ('Script', (0, 6), [('Command', (0, 6), [('QuotedLiteral', (0, 6), [])])])

        >>> parse("[\"a]\"]")
        ('Script', (0, 6), [('Command', (0, 6), [('SubstitutionCommand', (0, 6), [('Command', (1, 5), [('QuotedLiteral', (1, 5), [])])])])])

        Command substitution,

        >>> parse("\"[a]\"")
        ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('SubstitutionCommand', (1, 4), [('Command', (2, 3), [('RawLiteral', (2, 3), [])])])])])])

        >>> parse("\"[]\"")
        ('Script', (0, 4), [('Command', (0, 4), [('QuotedMixOf', (0, 4), [('SubstitutionCommand', (1, 3), [])])])])

        >>> parse("\"a[]\"")
        ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('RawLiteral', (1, 2), []), ('SubstitutionCommand', (2, 4), [])])])])

        >>> parse("\"[]a\"")
        ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('SubstitutionCommand', (1, 3), []), ('RawLiteral', (3, 4), [])])])])

        variable substitution,

        >>> parse("\"$\"")
        ('Script', (0, 3), [('Command', (0, 3), [('QuotedLiteral', (0, 3), [])])])

        >>> parse("\"$a\"")
        ('Script', (0, 4), [('Command', (0, 4), [('QuotedMixOf', (0, 4), [('SubstitutionScalarVariable', (1, 3), [])])])])

        >>> parse("\"${}\"")
        ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('SubstitutionScalarVariable', (1, 4), [('BracedLiteral', (2, 4), [])])])])])

        >>> parse("\"${ }\"")
        ('Script', (0, 6), [('Command', (0, 6), [('QuotedMixOf', (0, 6), [('SubstitutionScalarVariable', (1, 5), [('BracedLiteral', (2, 5), [])])])])])

        >>> parse("\"a$b\"")
        ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('RawLiteral', (1, 2), []), ('SubstitutionScalarVariable', (2, 4), [])])])])

        and backslash substitution

        >>> parse("\"\\a\"")
        ('Script', (0, 4), [('Command', (0, 4), [('QuotedMixOf', (0, 4), [('BackslashSubstitutionCONTROLCHAR', (1, 3), [])])])])

        are performed on the characters between the quotes as described below.

        The double quotes are not retained as part of the word.

        Added by Uwe:
        Since double quote starts and ends the word and
        words must be separated by whitespace the following
        is not legal TCL

        >>> parse("\"a\"b")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 3): Extra characters after closing ".'

        This will be parsed though
        >>> parse("\"a\" ")
        ('Script', (0, 4), [('Command', (0, 4), [('QuotedLiteral', (0, 3), []), ('Whitespace', (3, 4), [])])])

    [5] Argument expansion.
        If a word starts with the string {*} followed by
        a non-whitespace character, then the leading {*} is
        removed and the rest of the word is parsed and substituted as
        any other word. After substitution, the word is parsed
        again without substitutions, and its words are added to the
        command being substituted. For instance, cmd a {*}{b c}
        d {*}{e f} is equivalent to cmd a b c d e f.

        TODO: Not yet implemented.

    [6] Braces.
        If the first character of a word is an open brace ({) and
        rule [5] does not apply, then the word is terminated by the
        matching close brace (}).

        >>> parse("{a}")
        ('Script', (0, 3), [('Command', (0, 3), [('BracedLiteral', (0, 3), [])])])

        >>> parse("a{}")
        ('Script', (0, 3), [('Command', (0, 3), [('RawLiteral', (0, 3), [])])])

        >>> parse("a}")
        ('Script', (0, 2), [('Command', (0, 2), [('RawLiteral', (0, 2), [])])])

        Braces nest within the word:
        for each additional open brace there must be an additional
        close brace

        >>> parse("{{a}}")
        ('Script', (0, 5), [('Command', (0, 5), [('BracedLiteral', (0, 5), [])])])

        >>> parse("{{a}")
        Traceback (most recent call last):
            ...
        ParseError: 'At (1, 4): Missing: }.'

        (however, if an open brace or close brace within
        the word is quoted with a backslash then it is not counted in
        locating the matching close brace).

        >>> parse("{\{a}")
        ('Script', (0, 5), [('Command', (0, 5), [('BracedLiteral', (0, 5), [])])])

        >>> parse("{a\}}")
        ('Script', (0, 5), [('Command', (0, 5), [('BracedLiteral', (0, 5), [])])])

        No substitutions are
        performed on the characters between the braces except for
        backslash-newline substitutions described below, nor do
        semi-colons, newlines, close brackets, or white space receive
        any special interpretation.

        >>> parse("{\u; ]}")
        ('Script', (0, 7), [('Command', (0, 7), [('BracedLiteral', (0, 7), [])])])

        The word will consist of
        exactly the characters between the outer braces, not including
        the braces themselves.

    [7] Command substitution.
        If a word contains an open bracket ([) then Tcl performs
        command substitution.  To do this it invokes the Tcl
        interpreter recursively to process the characters following the
        open bracket as a Tcl script. The script may contain any
        number of commands and must be terminated by a close bracket
        (]).

        >>> parse("[a]")
        ('Script', (0, 3), [('Command', (0, 3), [('SubstitutionCommand', (0, 3), [('Command', (1, 2), [('RawLiteral', (1, 2), [])])])])])

        >>> parse("[a;]")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionCommand', (0, 4), [('Command', (1, 3), [('RawLiteral', (1, 2), []), ('Separator', (2, 3), [])])])])])

        >>> parse("a]")
        ('Script', (0, 2), [('Command', (0, 2), [('RawLiteral', (0, 2), [])])])

        >>> parse("[#a" + "\n" + "b]")
        ('Script', (0, 6), [('Command', (0, 6), [('SubstitutionCommand', (0, 6), [('Comment', (1, 4), []), ('Command', (4, 5), [('RawLiteral', (4, 5), [])])])])])

        >>> parse("[]")
        ('Script', (0, 2), [('Command', (0, 2), [('SubstitutionCommand', (0, 2), [])])])

        >>> parse("[;]")
        ('Script', (0, 3), [('Command', (0, 3), [('SubstitutionCommand', (0, 3), [('Command', (1, 2), [('Separator', (1, 2), [])])])])])

        >>> parse("[a;]")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionCommand', (0, 4), [('Command', (1, 3), [('RawLiteral', (1, 2), []), ('Separator', (2, 3), [])])])])])

        >>> parse("[a;b]")
        ('Script', (0, 5), [('Command', (0, 5), [('SubstitutionCommand', (0, 5), [('Command', (1, 3), [('RawLiteral', (1, 2), []), ('Separator', (2, 3), [])]), ('Command', (3, 4), [('RawLiteral', (3, 4), [])])])])])

        >>> parse("[]c")
        ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('SubstitutionCommand', (0, 2), []), ('RawLiteral', (2, 3), [])])])])

        >>> parse("[")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 1): Missing: ].'

        The result of the script (i.e., the result of its last
        command) is substituted into the word in place of the
        brackets and all of the characters between them. There may be
        any number of command substitutions in a single word.
        Command substitution is not performed on words enclosed in
        braces.

    [8] Variable substitution.
        If a word contains a dollar sign ($) then Tcl performs
        variable substitution: the dollar sign and the following
        characters are replaced in the word by the value of a
        variable. Variable substitution may take any of the following
        forms:

        $name	  Name is the name of a scalar variable; the name
                  is a sequence of one or more characters that
                  are a letter, digit, underscore, or namespace
                  separators (two or more colons).
        >>> parse("$")
        ('Script', (0, 1), [('Command', (0, 1), [('RawLiteral', (0, 1), [])])])

        >>> parse("a$")
        ('Script', (0, 2), [('Command', (0, 2), [('RawLiteral', (0, 2), [])])])

        >>> parse("a$=")
        ('Script', (0, 3), [('Command', (0, 3), [('RawLiteral', (0, 3), [])])])

        >>> parse("a$b")
        ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('RawLiteral', (0, 1), []), ('SubstitutionScalarVariable', (1, 3), [])])])])
        >>> parse("a$b/")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('RawLiteral', (0, 1), []), ('SubstitutionScalarVariable', (1, 3), []), ('RawLiteral', (3, 4), [])])])])

        >>> parse("$:")
        ('Script', (0, 2), [('Command', (0, 2), [('RawLiteral', (0, 2), [])])])

        >>> parse("$::")
        ('Script', (0, 3), [('Command', (0, 3), [('SubstitutionScalarVariable', (0, 3), [])])])

        >>> parse("$:::")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionScalarVariable', (0, 4), [])])])

        >>> parse("$::a")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionScalarVariable', (0, 4), [])])])

        $name(index)  Name gives the name of an array variable and index
                      gives the name of an element within that
                      array. Name must contain only letters, digits,
                      underscores, and namespace separators, and may
                      be an empty string. Command substitutions,
                      variable substitutions, and backslash
                      substitutions are performed on the characters
                      of index.

        >>> parse("$()")
        ('Script', (0, 3), [('Command', (0, 3), [('SubstitutionArray', (0, 3), [('RawLiteral', (1, 1), []), ('QuotedLiteral', (1, 3), [])])])])

        >>> parse("$a()")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionArray', (0, 4), [('RawLiteral', (1, 2), []), ('QuotedLiteral', (2, 4), [])])])])

        >>> parse("$a(b)")
        ('Script', (0, 5), [('Command', (0, 5), [('SubstitutionArray', (0, 5), [('RawLiteral', (1, 2), []), ('QuotedLiteral', (2, 5), [])])])])

        >>> parse("$a(b)c")
        ('Script', (0, 6), [('Command', (0, 6), [('RawMixOf', (0, 6), [('SubstitutionArray', (0, 5), [('RawLiteral', (1, 2), []), ('QuotedLiteral', (2, 5), [])]), ('RawLiteral', (5, 6), [])])])])

        >>> parse("a$b(c)")
        ('Script', (0, 6), [('Command', (0, 6), [('RawMixOf', (0, 6), [('RawLiteral', (0, 1), []), ('SubstitutionArray', (1, 6), [('RawLiteral', (2, 3), []), ('QuotedLiteral', (3, 6), [])])])])])

        >>> parse("a$b(c)d")
        ('Script', (0, 7), [('Command', (0, 7), [('RawMixOf', (0, 7), [('RawLiteral', (0, 1), []), ('SubstitutionArray', (1, 6), [('RawLiteral', (2, 3), []), ('QuotedLiteral', (3, 6), [])]), ('RawLiteral', (6, 7), [])])])])

        >>> parse("$+()")
        ('Script', (0, 4), [('Command', (0, 4), [('RawLiteral', (0, 4), [])])])

        >>> parse("$a($b)")
        ('Script', (0, 6), [('Command', (0, 6), [('SubstitutionArray', (0, 6), [('RawLiteral', (1, 2), []), ('QuotedMixOf', (2, 6), [('SubstitutionScalarVariable', (3, 5), [])])])])])

        >>> parse("$a([b])")
        ('Script', (0, 7), [('Command', (0, 7), [('SubstitutionArray', (0, 7), [('RawLiteral', (1, 2), []), ('QuotedMixOf', (2, 7), [('SubstitutionCommand', (3, 6), [('Command', (4, 5), [('RawLiteral', (4, 5), [])])])])])])])

        >>> parse("$a(\\b)")
        ('Script', (0, 6), [('Command', (0, 6), [('SubstitutionArray', (0, 6), [('RawLiteral', (1, 2), []), ('QuotedMixOf', (2, 6), [('BackslashSubstitutionCONTROLCHAR', (3, 5), [])])])])])

        >>> parse("$a(b")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 4): Missing closing ).'

        ${name}     Name is the name of a scalar variable. It may contain
                    any characters whatsoever except for close braces.
        >>> parse("${")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 2): Missing close brace in variable substitution.'

        >>> parse("${}")
        ('Script', (0, 3), [('Command', (0, 3), [('SubstitutionScalarVariable', (0, 3), [('BracedLiteral', (1, 3), [])])])])

        >>> parse("${ }")
        ('Script', (0, 4), [('Command', (0, 4), [('SubstitutionScalarVariable', (0, 4), [('BracedLiteral', (1, 4), [])])])])

        >>> parse("a${}")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('RawLiteral', (0, 1), []), ('SubstitutionScalarVariable', (1, 4), [('BracedLiteral', (2, 4), [])])])])])

        >>> parse("${}b")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('SubstitutionScalarVariable', (0, 3), [('BracedLiteral', (1, 3), [])]), ('RawLiteral', (3, 4), [])])])])

        >>> parse("a${}b")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('RawLiteral', (0, 1), []), ('SubstitutionScalarVariable', (1, 4), [('BracedLiteral', (2, 4), [])]), ('RawLiteral', (4, 5), [])])])])

        >>> parse("${\}}")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('SubstitutionScalarVariable', (0, 4), [('BracedLiteral', (1, 4), [])]), ('RawLiteral', (4, 5), [])])])])

        >>> parse("$$$")
        ('Script', (0, 3), [('Command', (0, 3), [('RawLiteral', (0, 3), [])])])

        There may be any number of variable substitutions in a single
        word. Variable substitution is not performed on words
        enclosed in braces.

    [9] Backslash substitution.
        If a backslash (\) appears within a word then
        backslash substitution occurs. In all cases but those
        described below the backslash is dropped and the following
        character is treated as an ordinary character and included in
        the word. This allows characters such as double quotes, close
        brackets, and dollar signs to be included in words without
        triggering special processing. The following table lists the
        backslash sequences that are handled specially, along with
        the value that replaces each sequence.

        \a   Audible alert (bell) (0x7).
        >>> parse("\\a")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \b   Backspace (0x8).
        >>> parse("\\b")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \f   Form feed (0xc).
        >>> parse("\\f")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \n   Newline (0xa).
        >>> parse("\\n")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \r   Carriage-return (0xd).
        >>> parse("\\r")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \t   Tab (0x9).
        >>> parse("\\t")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \v   Vertical tab (0xb).
        >>> parse("\\v")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCONTROLCHAR', (0, 2), [])])])

        \<newline>whiteSpace
           A single space character replaces the backslash, newline,
           and all spaces and tabs after the newline. This
           backslash sequence is unique in that it is replaced
           in a separate pre-pass before the command is actually
           parsed. This means that it will be replaced even when it
           occurs between braces, and the resulting space will be
           treated as a word separator if it isn\'t in braces or
           quotes.
        >>> parse("\\" + "\n\t ")
        ('Script', (0, 4), [('Command', (0, 4), [('BackslashSubstitutionEOL', (0, 4), [])])])

        \\   Backslash (\).
        >>> parse("\\\\")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCHAR', (0, 2), [])])])

        \ooo  The digits ooo (one, two, or three of them) give an
              eight-bit octal value for the Unicode character that
              will be inserted. The upper bits of the Unicode
              character will be 0.
        >>> parse("\\0")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionOCTAL', (0, 2), [])])])

        >>> parse("\\01")
        ('Script', (0, 3), [('Command', (0, 3), [('BackslashSubstitutionOCTAL', (0, 3), [])])])

        >>> parse("\\012")
        ('Script', (0, 4), [('Command', (0, 4), [('BackslashSubstitutionOCTAL', (0, 4), [])])])

        >>> parse("\\0123")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('BackslashSubstitutionOCTAL', (0, 4), []), ('RawLiteral', (4, 5), [])])])])

        >>> parse("\\8")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCHAR', (0, 2), [])])])

        >>> parse("\\08")
        ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('BackslashSubstitutionOCTAL', (0, 2), []), ('RawLiteral', (2, 3), [])])])])

        >>> parse("\\018")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('BackslashSubstitutionOCTAL', (0, 3), []), ('RawLiteral', (3, 4), [])])])])

        >>> parse("\\0128")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('BackslashSubstitutionOCTAL', (0, 4), []), ('RawLiteral', (4, 5), [])])])])

        \xhh  The hexadecimal digits hh give an eight-bit hexadecimal value
              for the Unicode character that will be inserted.
              Any number of hexadecimal digits may be present;
              however, all but the last two are ignored (the
              result is always a one-byte quantity). The upper
              bits of the Unicode character will be 0.

        >>> parse("\\x")
        ('Script', (0, 2), [('Command', (0, 2), [('BackslashSubstitutionCHAR', (0, 2), [])])])

        >>> parse("\\xF")
        ('Script', (0, 3), [('Command', (0, 3), [('BackslashSubstitutionHEX1', (0, 3), [])])])

        >>> parse("\\xEF")
        ('Script', (0, 4), [('Command', (0, 4), [('BackslashSubstitutionHEX2', (0, 4), [])])])

        >>> parse("\\xDEF")
        ('Script', (0, 5), [('Command', (0, 5), [('BackslashSubstitutionHEXLAST2', (0, 5), [])])])

        >>> parse("\\xG")
        ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('BackslashSubstitutionCHAR', (0, 2), []), ('RawLiteral', (2, 3), [])])])])

        >>> parse("\\x0G")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('BackslashSubstitutionHEX1', (0, 3), []), ('RawLiteral', (3, 4), [])])])])

        >>> parse("\\x01G")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('BackslashSubstitutionHEX2', (0, 4), []), ('RawLiteral', (4, 5), [])])])])

        >>> parse("\\x012G")
        ('Script', (0, 6), [('Command', (0, 6), [('RawMixOf', (0, 6), [('BackslashSubstitutionHEXLAST2', (0, 5), []), ('RawLiteral', (5, 6), [])])])])

        \uhhhh The hexadecimal digits hhhh (one, two, three, or four of them)
               give a sixteen-bit hexadecimal value for the
               Unicode character that will be inserted.

        >>> parse("\\uF")
        ('Script', (0, 3), [('Command', (0, 3), [('BackslashSubstitutionUNICODECHAR', (0, 3), [])])])

        >>> parse("\\uEF")
        ('Script', (0, 4), [('Command', (0, 4), [('BackslashSubstitutionUNICODECHAR', (0, 4), [])])])

        >>> parse("\\uDEF")
        ('Script', (0, 5), [('Command', (0, 5), [('BackslashSubstitutionUNICODECHAR', (0, 5), [])])])

        >>> parse("\\uCDEF")
        ('Script', (0, 6), [('Command', (0, 6), [('BackslashSubstitutionUNICODECHAR', (0, 6), [])])])

        >>> parse("\\uG")
        ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('BackslashSubstitutionCHAR', (0, 2), []), ('RawLiteral', (2, 3), [])])])])

        >>> parse("\\uFG")
        ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('BackslashSubstitutionUNICODECHAR', (0, 3), []), ('RawLiteral', (3, 4), [])])])])

        >>> parse("\\uEFG")
        ('Script', (0, 5), [('Command', (0, 5), [('RawMixOf', (0, 5), [('BackslashSubstitutionUNICODECHAR', (0, 4), []), ('RawLiteral', (4, 5), [])])])])

        >>> parse("\\uDEFG")
        ('Script', (0, 6), [('Command', (0, 6), [('RawMixOf', (0, 6), [('BackslashSubstitutionUNICODECHAR', (0, 5), []), ('RawLiteral', (5, 6), [])])])])


        Backslash substitution is not performed on words enclosed in
        braces,
        >>> parse("{\\a}")
        ('Script', (0, 4), [('Command', (0, 4), [('BracedLiteral', (0, 4), [])])])

        except for backslash-newline as described above.
        >>> parse("{" + "\\" + "\n\t " + "}")
        ('Script', (0, 6), [('Command', (0, 6), [('BracedLiteral', (0, 6), [('BackslashSubstitutionEOL', (1, 5), [])])])])

        >>> parse("\\")
        Traceback (most recent call last):
        ...
        ParseError: 'At (1, 1): Incomplete backslash substitution at end of script.'

    [10] Comments.
        If a hash character (#) appears at a point where Tcl is
        expecting the first character of the first word of a command,
        then the hash character and the characters that follow it,
        up through the next newline, are treated as a comment and
        ignored.

        >>> parse("#xyz")
        ('Script', (0, 4), [('Comment', (0, 4), [])])

        >>> parse("#xyz\n")
        ('Script', (0, 5), [('Comment', (0, 5), [])])

        The comment character only has significance when it
        appears at the beginning of a command.

        >>> parse("a #xyz")
        ('Script', (0, 6), [('Command', (0, 6), [('RawLiteral', (0, 1), []), ('Whitespace', (1, 2), []), ('RawLiteral', (2, 6), [])])])

    [11] Order of substitution.
         Each character is processed exactly once by the Tcl interpreter
         as part of creating the words of a command. For example,
         if variable substitution occurs then no further
         substitutions are performed on the value of the variable; the
         value is inserted into the word verbatim. If command
         substitution occurs then the nested command is processed
         entirely by the recursive call to the Tcl interpreter; no
         substitutions are performed before making the recursive call
         and no additional substitutions are performed on the
         result of the nested script.

         Substitutions take place from left to right, and each
         substitution is evaluated completely before attempting to
         evaluate the next. Thus, a sequence like set y [set x 0][incr
         x][incr x] will always set the variable y to the value, 012.

    [12] Substitution and word boundaries.
         Substitutions do not affect the word boundaries of a command,
         except for argument expansion as specified in rule [5].
         For example, during variable substitution the entire value of
         the variable becomes part of a single word, even if the
         variable\'s value contains spaces.

    =================================================================

    Starting from here are additional test cases to increase branch
    coverage in the parse function:

    >>> parse(" ")
    ('Script', (0, 1), [('Whitespace', (0, 1), [])])

    >>> parse('\\' + chr(13) + chr(10) + "a")
    ('Script', (0, 4), [('Command', (0, 4), [('RawMixOf', (0, 4), [('BackslashSubstitutionEOL', (0, 3), []), ('RawLiteral', (3, 4), [])])])])

    >>> parse('{a\\' + chr(13))
    Traceback (most recent call last):
    ...
    ParseError: 'At (1, 4): Missing: }.'

    >>> parse('{}')
    ('Script', (0, 2), [('Command', (0, 2), [('BracedLiteral', (0, 2), [])])])

    >>> parse('"a\\b"')
    ('Script', (0, 5), [('Command', (0, 5), [('QuotedMixOf', (0, 5), [('RawLiteral', (1, 2), []), ('BackslashSubstitutionCONTROLCHAR', (2, 4), [])])])])

    >>> parse('a[]')
    ('Script', (0, 3), [('Command', (0, 3), [('RawMixOf', (0, 3), [('RawLiteral', (0, 1), []), ('SubstitutionCommand', (1, 3), [])])])])

    >>> parse('[' * 10000 + ']' * 10000)
    Traceback (most recent call last):
    ...
    RuntimeError: maximum recursion depth exceeded in cmp

    =================================================================

    Corner Cases:
    % puts $+(x)
    $+(x)
    >>> parse('puts $+(x)')
    ('Script', (0, 10), [('Command', (0, 10), [('RawLiteral', (0, 4), []), ('Whitespace', (4, 5), []), ('RawLiteral', (5, 10), [])])])

    % array set "" [list a 1 b 2]
    % puts $(a)
    1
    >>> parse('puts $(a)')
    ('Script', (0, 9), [('Command', (0, 9), [('RawLiteral', (0, 4), []), ('Whitespace', (4, 5), []), ('SubstitutionArray', (5, 9), [('RawLiteral', (6, 6), []), ('QuotedLiteral', (6, 9), [])])])])

    No substitutions are carried out in the name portion of an array
    substitution but only in the index portion

    % array set ab [list a 1 b 2]
    % puts $ab(a)
    1
    % set b b
    b
    % puts $a[set b](a)
    huhub(a)

    Tcl parses $a as variable substitution and not as the name portion of an
    array substitution
    >>> parse('puts $a[set b](a)')
    ('Script', (0, 17), [('Command', (0, 17), [('RawLiteral', (0, 4), []), ('Whitespace', (4, 5), []), ('RawMixOf', (5, 17), [('SubstitutionScalarVariable', (5, 7), []), ('SubstitutionCommand', (7, 14), [('Command', (8, 13), [('RawLiteral', (8, 11), []), ('Whitespace', (11, 12), []), ('RawLiteral', (12, 13), [])])]), ('RawLiteral', (14, 17), [])])])])

    This however is recognized as an array substitution, because the name
    portion has only letters, digits, underscores and/or two or more colons
    >>> parse('$a([puts "huhu"])')
    ('Script', (0, 17), [('Command', (0, 17), [('SubstitutionArray', (0, 17), [('RawLiteral', (1, 2), []), ('QuotedMixOf', (2, 17), [('SubstitutionCommand', (3, 16), [('Command', (4, 15), [('RawLiteral', (4, 8), []), ('Whitespace', (8, 9), []), ('QuotedLiteral', (9, 15), [])])])])])])])

    Leading whitespaces at the beginning of a command should not
    become part of the command
    >>> parse(' a')
    ('Script', (0, 2), [('Whitespace', (0, 1), []), ('Command', (1, 2), [('RawLiteral', (1, 2), [])])])

    '''

if __name__ == '__main__':  # pragma: nocover
    import doctest
    from pprint import pprint
    #print doctest.testmod()
    with file('b.scf') as f:
        text = f.read()
        ret = parse(text)
    #pprint(ret)
    for command in ret[2]:
        if command[0] == 'Command':
            start = command[1][0]
            for bit in command[2]:
                if bit[0] == 'BracedLiteral':
                    stop = bit[1][0] - 1
                    content = bit[1]
            print(text[start:stop], '->', text[content[0]:content[1]])
