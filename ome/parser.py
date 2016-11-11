# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import re
from . import ast
from .error import OmeParseError
from .symbol import is_private_symbol

re_newline = re.compile(r'\r\n|\r|\n')
re_spaces = re.compile(r'[ \r\n\t]*')
re_comment = re.compile(r'(?:#|--)([^\r\n]*)')
re_name = re.compile(r'~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*(?![:a-zA-Z0-9-])')
re_arg_name = re.compile(r'[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*(?![:a-zA-Z0-9-])')
re_keyword = re.compile(r'~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*:')
re_number = re.compile(r'([+-]?)0*(0|[1-9]+(?:0*[1-9]+)*)(0*)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?')
re_string = re.compile(r"'((?:\\(?:\r\n|\r|\n|.)|[^\r\n'$])*)['$]?")
re_string_next = re.compile(r"((?:\\(?:\r\n|\r|\n|.)|[^\r\n'$])*)['$]?")
re_string_escape = re.compile(r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|\r\n|\r|\n|.)')
re_assign = re.compile(r'=(?!=)|:=')
re_operator = re.compile(r'\+|-|\*|/|×|÷|==|!=|<=|>=|<|>|≠|≤|≥')
re_logical_operator = re.compile(r'&&|\|\|')
re_comparison_operator = re.compile(r'==|!=|<=|>=|<|>|≠|≤|≥')
re_addition_operator = re.compile('\+|-')
re_multiplication_operator = re.compile(r'\*|/|×|÷')
re_end_token = re.compile(r'[|)}\]]')

operator_aliases = {
    '×' : '*',
    '÷' : '/',
    '≠' : '!=',
    '≤' : '<=',
    '≥' : '>=',
    '&&': 'then:',
    '||': 'else:',
}

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
    '$': '$',
    '\\': '\\',
    '\r\n': '',
    '\r': '',
    '\n': '',
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
            parse_state.error("invalid escape sequence '%s'" % esc)
        i = m.end()
    parts.append(string[i:])
    return ''.join(parts)

class ParserState(object):
    def __init__(self, state):
        self.set_state(state)

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
        return ParserState(self)

    @property
    def current_line(self):
        m = re_newline.search(self.stream, self.pos)
        return self.stream[self.line_pos : m.start() if m else len(self.stream)]

    @property
    def column(self):
        return self.pos - self.line_pos

    def error(self, message):
        raise OmeParseError(message, self)

class Parser(ParserState):
    def __init__(self, stream, stream_name, tab_width=8):
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
        if name == 'self':
            parse_state.error('%s is a reserved name' % name)
        return name

    def argument_name(self, message='expected argument name'):
        return self.expect_token(re_arg_name, message).group()

    def check_num_params(self, n, parse_state):
        if n >= 16:
            parse_state.error('too many parameters')

    def signature(self):
        argnames = []
        symbol = ''
        for m in self.repeat_token(re_keyword):
            part = m.group()
            if is_private_symbol(part) and symbol:
                self.error('expected keyword')
            symbol += part
            parse_state = self.copy_state()
            name = self.argument_name()
            if name in argnames:
                parse_state.error("duplicate parameter name '%s'" % name)
            argnames.append(name)
            for m in self.repeat_token(','):
                symbol += ','
                parse_state = self.copy_state()
                name = self.argument_name()
                if name in argnames:
                    parse_state.error("duplicate parameter name '%s'" % name)
                argnames.append(name)
        if not symbol:
            parse_state = self.copy_state()
            m = self.match(re_operator)
            if m:
                argnames.append(self.argument_name())
                symbol = operator_aliases.get(m.group(), m.group())
                if re_comparison_operator.match(symbol):
                    parse_state.error("define compare: or equals: to overload comparison operator")
            else:
                m = self.expect_token(re_name, 'expected name or keyword')
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
                self.error('expected end of statement')
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
            parse_state = self.copy_state()
            m = self.token(re_name)
            if not m:
                break
            name = self.check_name(m.group(), parse_state)
            if name in defined_symbols:
                parse_state.error("variable '%s' is already defined" % name)
            mutable = self.expect_token(re_assign, "expected '=' or ':='").group() == ':='
            statements.append(ast.LocalVariable(name, self.expr()))
            slots.append(ast.BlockVariable(name, mutable, len(slots)))
            defined_symbols.add(name)
            if mutable:
                defined_symbols.add(name + ':')
        for _ in self.repeat_token('|'):
            symbol, args = self.signature()
            if symbol in defined_methods:
                self.error("method '%s' is already defined" % symbol)
            if symbol in defined_symbols:
                self.error("method '%s' conflicts with variable definition" % symbol)
            self.expect_token('|', "expected '|'")
            methods.append(ast.Method(symbol, args, self.statements()))
            defined_methods.add(symbol)
        self.pop_indent()
        self.scan()
        if self.pos < len(self.stream) and not self.peek('}'):
            self.error('expected declaration or end of block')
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
            self.error('expected declaration or end of file')
        return block

    def statement(self):
        parse_state = self.copy_state()
        m = self.token(re_name)
        if m:
            name = m.group()
            m = self.token(re_assign)
            if m:
                if m.group() == ':=':
                    self.error('mutable variables are only allowed in blocks')
                if is_private_symbol(name):
                    parse_state.error('local variables cannot be private')
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
            self.error('expected statement or expression')
        return statements[0] if len(statements) == 1 else ast.Sequence(statements)

    def array(self):
        elems = []
        self.push_indent()
        for _ in self.statement_lines():
            elems.append(self.expr())
        self.pop_indent()
        return ast.Array(elems)

    def keywordexpr(self):
        expr = None
        self.scan()
        if not self.peek(re_keyword):
            expr = self.cmpexpr()
        symbol = ''
        args = []
        self.scan()
        parse_state = self.copy_state()
        kw_parse_state = parse_state
        for m in self.repeat_expr_token(re_keyword):
            part = m.group()
            if is_private_symbol(part) and symbol:
                kw_parse_state.error('expected keyword')
            symbol += part
            args.append(self.cmpexpr())
            for m in self.repeat_expr_token(','):
                symbol += ','
                args.append(self.cmpexpr())
            kw_parse_state = self.copy_state()
        if args:
            self.check_num_params(len(args), parse_state)
            expr = ast.Send(expr, symbol, args, parse_state)
        return expr

    def expr(self):
        return self.logicalexpr()

    def logicalexpr(self):
        lhs = self.keywordexpr()
        self.scan()
        parse_state = self.copy_state()
        for m in self.repeat_expr_token(re_logical_operator):
            op = m.group()
            rhs = ast.Block([], [ast.Method('do', [], self.keywordexpr())])
            lhs = ast.Send(lhs, operator_aliases.get(op, op), [rhs], parse_state)
            self.scan()
            parse_state = self.copy_state()
        return lhs

    def cmpexpr(self):
        lhs = self.addexpr()
        self.scan()
        parse_state = self.copy_state()
        for m in self.repeat_expr_token(re_comparison_operator):
            op = m.group()
            rhs = self.addexpr()
            lhs = ast.Send(lhs, operator_aliases.get(op, op), [rhs], parse_state)
            self.scan()
            parse_state = self.copy_state()
        return lhs

    def addexpr(self):
        lhs = self.mulexpr()
        self.scan()
        parse_state = self.copy_state()
        for m in self.repeat_expr_token(re_addition_operator):
            op = m.group()
            rhs = self.mulexpr()
            lhs = ast.Send(lhs, operator_aliases.get(op, op), [rhs], parse_state)
            self.scan()
            parse_state = self.copy_state()
        return lhs

    def mulexpr(self):
        lhs = self.unaryexpr()
        self.scan()
        parse_state = self.copy_state()
        for m in self.repeat_expr_token(re_multiplication_operator):
            op = m.group()
            rhs = self.unaryexpr()
            lhs = ast.Send(lhs, operator_aliases.get(op, op), [rhs], parse_state)
            self.scan()
            parse_state = self.copy_state()
        return lhs

    def unaryexpr(self):
        expr = self.atom()
        while True:
            self.scan()
            parse_state = self.copy_state()
            m = self.expr_token(re_name)
            if not m:
                break
            name = m.group()
            expr = ast.Send(expr, name, [], parse_state)
        return expr

    def atom(self):
        if self.expr_token('('):
            statements = self.statements()
            self.expect_token(')', "expected ')'")
            return statements
        if self.expr_token('{'):
            block = self.block()
            self.expect_token('}', "expected '}'")
            return block
        if self.expr_token('['):
            array = self.array()
            self.expect_token(']', "expected ']'")
            return array
        parse_state = self.copy_state()
        m = self.expr_token(re_name)
        if m:
            name = m.group()
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
        str_state = self.copy_state()
        parse_state = str_state
        m = self.expr_token(re_string)
        if m:
            s = m.group()
            exprs = []
            while s[-1] == '$':
                s = parse_string_escapes(m.group(1), parse_state)
                if len(s) > 0:
                    exprs.append(ast.String(s))
                if self.match('('):
                    exprs.append(self.statements())
                    self.expect_token(')', "expected ')'")
                else:
                    parse_state = self.copy_state()
                    m = self.expect_token(re_name, 'expected name or expression')
                    name = m.group()
                    exprs.append(ast.Send(None, name, [], parse_state))
                parse_state = self.copy_state()
                m = self.match(re_string_next)
                if not m:
                    parse_state.error('error parsing string')
                s = m.group()
            if s[-1] != "'" or (len(s) == 1 and not exprs):
                self.error('reached end of line while parsing string')
            s = parse_string_escapes(m.group(1), parse_state)
            if not exprs:
                return ast.String(s)
            if len(s) > 0:
                exprs.append(ast.String(s))
            return ast.Concat(exprs, str_state)
        self.error('expected expression')
