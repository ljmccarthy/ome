# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re
from .error import OmeError

re_newline = re.compile(r'\r\n|\r|\n')

class ParserState(object):
    def __init__(self, state):
        self.set_state(state)

    def set_state(self, state):
        self.stream = state.stream
        self.stream_name = state.stream_name
        self.pos = state.pos
        self.line_pos = state.line_pos
        self.line_number = state.line_number

    def copy_state(self):
        return ParserState(self)

    @property
    def current_line(self):
        m = re_newline.search(self.stream, self.pos)
        return self.stream[self.line_pos : m.start() if m else len(self.stream)]

    @property
    def column(self):
        return self.pos - self.line_pos

    def format_error(self, message):
        line_unstripped = self.current_line.rstrip()
        line = line_unstripped.lstrip()
        arrow = ' ' * (self.column - (len(line_unstripped) - len(line))) + '\x1b[1;32m^\x1b[0m'
        return ('\x1b[1m{0.stream_name}:{0.line_number}:{0.column}:\x1b[0m {1}\n'
              + '    {2}\n    {3}').format(self, message, line, arrow)

    def error(self, message):
        raise OmeError(self.format_error(message))

class BaseParser(ParserState):
    re_spaces = re.compile('\s*')

    def __init__(self, stream, stream_name):
        self.stream = stream
        self.stream_name = stream_name
        self._pos = 0           # Current position
        self.line_pos = 0       # Position of the 1st character of the current line
        self.line_number = 1    # Current line number (starting from 1)
        self._string_re = {}

    @property
    def pos(self):
        return self._pos

    @pos.setter
    def pos(self, pos):
        assert pos >= self._pos
        m = None
        for m in re_newline.finditer(self.stream, self._pos, pos):
            self.line_number += 1
        if m:
            self.line_pos = m.end()
        self._pos = pos

    def get_re(self, pattern):
        if isinstance(pattern, str):
            if pattern not in self._string_re:
                self._string_re[pattern] = re.compile(re.escape(pattern))
            return self._string_re[pattern]
        return pattern

    def match(self, pattern):
        """
        Try to match a regex or string at current position. If the pattern
        matches, the stream position is advanced the match object is returned.
        """
        m = self.get_re(pattern).match(self.stream, self.pos)
        if m:
            self.pos = m.end()
            return m

    def peek(self, pattern):
        if hasattr(pattern, 'match'):
            return pattern.match(self.stream, self.pos)
        elif self.stream[self.pos : self.pos + len(pattern)] == pattern:
            return pattern

    def scan(self):
        self.match(self.re_spaces)

    def token(self, pattern):
        self.scan()
        return self.match(pattern)

    def expect_match(self, pattern, message):
        m = self.match(pattern)
        if not m:
            self.error(message)
        return m

    def expect_token(self, pattern, message):
        m = self.token(pattern)
        if not m:
            self.error(message)
        return m

    def search(self, pattern, end=None):
        if end is None:
            end = len(self.stream)
        m = self.get_re(pattern).search(self.stream, self.pos, end)
        if m:
            leading = self.stream[self.pos:m.start()]
            self.pos = m.end()
            return leading, m
        return '', None

    def search_iter(self, pattern):
        pattern = self.get_re(pattern)
        while True:
            m = pattern.search(self.stream, self.pos)
            if not m:
                break
            leading = self.stream[self.pos:m.start()]
            self.pos = m.end()
            yield leading, m

    def trailing(self):
        s = self.stream[self.pos:]
        self.pos = len(self.stream)
        return s
