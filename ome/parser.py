# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re
from . import ast
from .constants import *

re_newline = re.compile(r'\r\n|\r|\n')
re_spaces = re.compile(r'[ \r\n\t]*')
re_comment = re.compile(r'(?:#|--)([^\r\n]*)')
re_name = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)')
re_arg_name = re.compile(r'([a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)')
re_keyword = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*:)')
re_number = re.compile(r'([+-]?)0*(0|[1-9]+(?:0*[1-9]+)*)(0*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?')
re_string = re.compile(r"'((?:\\.|[^\r\n'])*)'?")
re_string_escape = re.compile(r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)')
re_assign = re.compile(r'=|:=')
re_end_token = re.compile(r'[|)}\]]')

string_escapes = {
    'a': chr(7),
    'b': chr(8),
    't': chr(9),
    'n': chr(10),
    'v': chr(11),
    'f': chr(12),
    'r': chr(13),
    'e': chr(27),
    "'": "'",
    '"': '"',
    '\\': '\\',
}

def parse_string_escapes(string, parse_state):
    i = 0
    parts = []
    for m in re_string_escape.finditer(string):
        parts.append(string[i:m.start()])
        esc = m.group(1)
        if esc[0] in 'xu' and len(esc) > 1:
            parts.append(chr(int(esc[1:], 16)))
        elif esc in string_escapes:
            parts.append(string_escapes[esc])
        else:
            parse_state.pos += m.start() + 2
            parse_state.error("Invalid escape sequence '%s'" % esc)
        i = m.end()
    parts.append(string[i:])
    return ''.join(parts)

class ParserState(object):
    def __init__(self, stream='', stream_name='<string>'):
        self.stream = stream
        self.stream_name = stream_name
        self.pos = 0            # Current position
        self.line_pos = 0       # Position of the 1st character of the current line
        self.line_number = 1    # Current line number (starting from 1)
        self.line_indent = 0    # Indentation level of current line
        self.indent_level = -1  # Minimum indentation level of current sub-expression
        self.indent_line = -1   # Line number where indentation level begines
        self.indent_stack = []  # Stack of indent levels for outer expressions
        self.comments = []      # List of comments collected by previous scan()

    def set_state(self, state):
        self.stream = state.stream
        self.stream_name = state.stream_name
        self.pos = state.pos
        self.line_pos = state.line_pos
        self.line_number = state.line_number
        self.line_indent = state.line_indent
        self.indent_level = state.indent_level
        self.indent_line = state.indent_line
        self.indent_stack = state.indent_stack[:]
        self.comments = state.comments

    def copy_state(self):
        state = ParserState(self.stream)
        state.set_state(self)
        return state

    @property
    def current_line(self):
        m = re_newline.search(self.stream, self.pos)
        return self.stream[self.line_pos : m.start() if m else len(self.stream)]

    @property
    def column(self):
        return self.pos - self.line_pos

    def error(self, message):
        line = self.current_line
        column = self.column
        arrow = ' ' * column + '^'
        raise Error('In "%s", line %d, column %d\n    %s\n    %s\nError: %s' % (
            self.stream_name, self.line_number, column, line, arrow, message))

class Parser(ParserState):
    def __init__(self, stream, stream_name='<string>', tab_width=8):
        super(Parser, self).__init__(stream, stream_name)
        self.tab_width = tab_width

    def match(self, pattern):
        """
        Try to match a regex or string at current position. If the pattern
        matches, the stream position is advanced the match object is returned.
        """
        if hasattr(pattern, 'match'):
            m = pattern.match(self.stream, self.pos)
            if m:
                self.pos = m.end()
                return m
        elif self.stream[self.pos : self.pos + len(pattern)] == pattern:
            self.pos += len(pattern)
            return pattern

    def peek(self, pattern):
        if hasattr(pattern, 'match'):
            return pattern.match(self.stream, self.pos)
        elif self.stream[self.pos : self.pos + len(pattern)] == pattern:
            return pattern

    def scan(self):
        """
        Scan for the next token by skipping passed any spaces or comments.
        """
        self.comments = []
        while True:
            spaces = re_newline.sub('\n', self.match(re_spaces).group())
            new_lines = spaces.count('\n')
            self.line_number += new_lines
            if new_lines > 0:
                indent = spaces.rsplit('\n', 1)[1]
                self.line_pos = self.pos - len(indent)
                self.line_indent = len(indent.expandtabs(self.tab_width))
            m_comment = self.match(re_comment)
            if m_comment:
                self.comments.append(m_comment.group(1).strip())
            else:
                break

    def set_indent(self):
        self.indent_level = self.pos - self.line_pos
        self.indent_line = self.line_number

    def push_indent(self):
        self.indent_stack.append((self.indent_level, self.indent_line))

    def pop_indent(self):
        self.indent_level, self.indent_line = self.indent_stack.pop()

    def has_more_tokens(self):
        return (self.pos < len(self.stream)
            and ((self.pos - self.line_pos) > self.indent_level or self.line_number == self.indent_line))

    def expr_token(self, pattern):
        self.scan()
        if self.has_more_tokens():
            return self.match(pattern)

    def token(self, pattern):
        self.scan()
        return self.match(pattern)

    def expect_token(self, pattern, message):
        m = self.token(pattern)
        if not m:
            self.error(message)
        return m

    def repeat_token(self, pattern):
        while True:
            m = self.token(pattern)
            if not m:
                break
            yield m

    def repeat_expr_token(self, pattern):
        while True:
            m = self.expr_token(pattern)
            if not m:
                break
            yield m

    def check_name(self, name, parse_state):
        if name in ast.reserved_names:
            parse_state.error('%s is a reserved name' % name)
        return name

    def argument_name(self, message='Expected argument name'):
        self.scan()
        if self.peek(re_keyword):
            self.error(message)
        return self.expect_token(re_arg_name, message).group()

    def check_num_params(self, n, parse_state):
        if n >= 16:
            parse_state.error('Seriously? %d parameters? Take a step back and redesign your code' % n)

    def signature(self):
        argnames = []
        symbol = ''
        for m in self.repeat_token(re_keyword):
            part = m.group()
            if part[0] == '~' and symbol:
                self.error('Expected keyword')
            symbol += part
            argnames.append(self.argument_name())
            for m in self.repeat_token(','):
                symbol += ','
                argnames.append(self.argument_name())
        if not symbol:
            parse_state = self.copy_state()
            m = self.expect_token(re_name, 'Expected name or keyword')
            symbol = self.check_name(m.group(), parse_state)
        self.check_num_params(len(argnames), self)
        return symbol, argnames

    def statement_lines(self):
        """Loop over newline or semicolon separated statements."""
        prev_indent_line = -1
        while True:
            self.scan()
            if self.peek(re_end_token) or self.pos >= len(self.stream):
                break
            self.set_indent()
            if self.line_number == prev_indent_line:
                self.error('Expected end of statement')
            prev_indent_line = self.indent_line
            yield
            if self.token(';'):
                prev_indent_line = -1

    def block(self):
        methods = []
        slots = []
        statements = []
        defined_symbols = set()
        defined_methods = set()
        self.push_indent()
        for _ in self.statement_lines():
            self.scan()
            if self.peek(re_keyword):
                break
            parse_state = self.copy_state()
            m = self.token(re_name)
            if not m:
                break
            name = self.check_name(m.group(), parse_state)
            if name in defined_symbols:
                parse_state.error("Variable '%s' is already defined" % name)
            mutable = self.expect_token(re_assign, "Expected '=' or ':='").group() == ':='
            statements.append(ast.LocalVariable(name, self.expr()))
            slots.append(ast.BlockVariable(name, mutable, len(slots)))
            defined_symbols.add(name)
            if mutable:
                defined_symbols.add(name + ':')
        for _ in self.repeat_token('|'):
            symbol, args = self.signature()
            if symbol in defined_methods:
                self.error("Method '%s' is already defined" % symbol)
            if symbol in defined_symbols:
                self.error("Method '%s' conflicts with variable definition" % symbol)
            self.expect_token('|', "Expected '|'")
            methods.append(ast.Method(symbol, args, self.statements()))
            defined_methods.add(symbol)
        self.pop_indent()
        self.scan()
        if self.pos < len(self.stream) and not self.peek('}'):
            self.error('Expected declaration or end of block')
        if not slots and not methods:
            return ast.EmptyBlock
        block = ast.Block(slots, methods)
        if statements:
            statements.append(block)
            return ast.Sequence(statements)
        return block

    def toplevel(self):
        block = self.block()
        if self.pos < len(self.stream):
            self.error('Expected declaration or end of file')
        return block

    def statement(self):
        parse_state = self.copy_state()
        m = self.token(re_name)
        if m:
            name = m.group()
            m = self.token(re_assign)
            if m:
                if m.group() == ':=':
                    self.error('Mutable variables are only allowed in blocks')
                if name[0] == '~':
                    parse_state.error('Local variables cannot be private')
                self.check_name(name, parse_state)
                return ast.LocalVariable(name, self.expr())
        self.set_state(parse_state)
        return self.expr()

    def statements(self):
        statements = []
        self.push_indent()
        for _ in self.statement_lines():
            statements.append(self.statement())
        self.pop_indent()
        if not statements or isinstance(statements[-1], ast.LocalVariable):
            self.error('Expected statement or expression')
        return statements[0] if len(statements) == 1 else ast.Sequence(statements)

    def array(self):
        elems = []
        self.push_indent()
        for _ in self.statement_lines():
            elems.append(self.expr())
        self.pop_indent()
        if len(elems) > MAX_ARRAY_SIZE:
            self.error('Array size too big.')
        return ast.Array(elems)

    def expr(self):
        expr = None
        parse_state = self.copy_state()
        self.scan()
        if not self.peek(re_keyword):
            expr = self.unaryexpr()
        symbol = ''
        args = []
        kw_parse_state = self.copy_state()
        for m in self.repeat_expr_token(re_keyword):
            part = m.group()
            if part[0] == '~':
                if symbol:
                    kw_parse_state.error('Expected keyword')
                if expr:
                    kw_parse_state.error('Private message sent to an explicit receiver')
            symbol += part
            args.append(self.unaryexpr())
            for m in self.repeat_expr_token(','):
                symbol += ','
                args.append(self.unaryexpr())
            kw_parse_state = self.copy_state()
        if args:
            self.check_num_params(len(args), parse_state)
            expr = ast.Send(expr, symbol, args, parse_state)
        return expr

    def unaryexpr(self):
        expr = self.atom()
        while True:
            self.scan()
            if self.peek(re_keyword):
                break
            parse_state = self.copy_state()
            m = self.expr_token(re_name)
            if not m:
                break
            name = m.group()
            if name[0] == '~':
                parse_state.error('Private message sent to an explicit receiver')
            expr = ast.Send(expr, name, [])
        return expr

    def atom(self):
        if self.expr_token('('):
            statements = self.statements()
            self.expect_token(')', "Expected ')'")
            return statements
        if self.expr_token('{'):
            block = self.block()
            self.expect_token('}', "Expected '}'")
            return block
        if self.expr_token('['):
            array = self.array()
            self.expect_token(']', "Expected ']'")
            return array
        parse_state = self.copy_state()
        m = self.expr_token(re_name)
        if m:
            name = m.group()
            if name in ast.reserved_names:
                return ast.reserved_names[name]
            return ast.Send(None, name, [], parse_state)
        m = self.expr_token(re_number)
        if m:
            sign, significand, trailing, decimal, exponent = m.groups()
            significand = int(sign + significand, 10)
            exponent = (int(exponent, 10) if exponent else 0) + len(trailing)
            decimal = decimal.rstrip('0') if decimal else ''
            if decimal:
                significand = significand * 10**(len(decimal)) + int(decimal, 10)
                exponent -= len(decimal)
            return ast.Number(significand, exponent, parse_state)
        parse_state = self.copy_state()
        m = self.expr_token(re_string)
        if m:
            s = m.group()
            if s[-1] != "'" or len(s) == 1:
                self.error('Reached end of line while parsing string')
            string = parse_string_escapes(m.group(1), parse_state)
            return ast.String(string)
        self.error('Expected expression')
