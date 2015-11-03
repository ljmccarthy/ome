# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re

re_newline = re.compile(r'\r\n|\r|\n')
re_spaces = re.compile(r'[ \r\n\t]*')
re_comment = re.compile(r'(?:#|--)([^\r\n]*)')
re_name = re.compile(r'([a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)')
re_keyword = re.compile(r'([a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*:)')
re_number = re.compile(r'([+-]?[0-9]+)(?:\.([0-9]+))?(?:e([+-]?[0-9]+))?')
re_string = re.compile(r"'((?:\\'|[^\r\n'])*)'")
re_assign = re.compile(r'=|:=')
re_end_token = re.compile(r'[|)}\]]')

class SyntaxError(Exception):
    pass

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
        state.copy(self)
        return state

    def error(self, message):
        m = re_newline.search(self.stream, self.pos)
        line = self.stream[self.line_pos : m.start() if m else len(self.stream)]
        col = self.pos - self.line_pos
        arrow = ' ' * col + '^'
        raise SyntaxError('Error in "%s", line %d, column %d: %s\n  %s\n  %s' % (
            self.stream_name, self.line_number, col, message, line, arrow))

class Parser(ParserState):
    def __init__(self, stream, stream_name='<string>', tab_width=8):
        super(Parser, self).__init__(stream, stream_name)
        self.tab_width = tab_width
        self.block_id = 16       

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

    def check_name(self, name):
        if name in reserved_names:
            self.error('%s is a reserved name' % name)
        return name

    def argument_name(self, message='Expected argument name'):
        self.scan()
        if self.peek(re_keyword):
            self.error(message)
        return self.expect_token(re_name, message).group()

    def signature(self):
        argnames = []
        symbol = ''
        for m in self.repeat_token(re_keyword):
            symbol += m.group()
            argnames.append(self.argument_name())
            for m in self.repeat_token(','):
                symbol += ','
                argnames.append(self.argument_name())
        if not symbol:
            m = self.expect_token(re_name, 'Expected name or keyword')
            symbol = self.check_name(m.group())
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
        vars = []
        statements = []
        defined_symbols = set()
        defined_methods = set()
        self.push_indent()
        for _ in self.statement_lines():
            self.scan()
            if self.peek(re_keyword):
                break
            m = self.token(re_name)
            if not m:
                break
            name = self.check_name(m.group())
            if name in defined_symbols:
                self.error("Variable '%s' is already defined" % name)
            mutable = self.expect_token(re_assign, "Expected '=' or ':='").group() == ':='
            statements.append(LocalVariable(name, self.expr()))
            vars.append(BlockVariable(name, mutable, len(vars)))            
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
            methods.append(Method(symbol, args, self.statements()))
            defined_methods.add(symbol)
        self.pop_indent()
        self.scan()
        if self.pos < len(self.stream) and not self.peek('}'):
            self.error('Expected declaration or end of block')
        block_id = self.block_id
        self.block_id += 1
        block = Block(block_id, vars, methods)
        if statements:
            statements.append(block)
            return Sequence(statements)
        return block

    def statement(self):
        maybe_assign = self.peek(re_name)
        statement = self.expr()
        m = self.token(re_assign)
        if m:
            if m.group() == ':=':
                self.error('Mutable variables are only allowed in blocks')
            if not isinstance(statement, Send) or statement.receiver or not maybe_assign:
                self.error('Left hand side of assignment must be a name')
            name = self.check_name(statement.message)
            statement = LocalVariable(name, self.expr())
        return statement

    def statements(self):
        statements = []
        self.push_indent()
        for _ in self.statement_lines():
            statements.append(self.statement())
        self.pop_indent()
        if not statements or isinstance(statements[-1], LocalVariable):
            self.error('Expected statement or expression')
        return statements[0] if len(statements) == 1 else Sequence(statements)

    def array(self):
        elems = []
        self.push_indent()
        for _ in self.statement_lines():
            elems.append(self.expr())
        self.pop_indent()
        return Array(elems)

    def expr(self):
        expr = None
        self.scan()
        if not self.peek(re_keyword):
            expr = self.unaryexpr()
        symbol = ''
        args = []
        for m in self.repeat_expr_token(re_keyword):
            symbol += m.group()
            args.append(self.unaryexpr())
            for m in self.repeat_expr_token(','):
                symbol += ','
                args.append(self.unaryexpr())
        if args:
            expr = Send(expr, symbol, args)
        return expr

    def unaryexpr(self):
        expr = self.atom()
        while True:
            self.scan()
            if self.peek(re_keyword):
                break
            m = self.expr_token(re_name)
            if not m:
                break
            expr = Send(expr, m.group(), [])
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
        m = self.expr_token(re_name)
        if m:
            name = m.group()
            if name in reserved_names:
                return reserved_names[name]
            return Send(None, name, [])
        m = self.expr_token(re_number)
        if m:
            whole, decimal, exponent = m.groups()
            mantissa = int(whole, 10)
            exponent = int(exponent, 10) if exponent is not None else 0
            if decimal is not None:
                mantissa = mantissa * 10**(len(decimal)) + int(decimal, 10)
                exponent -= len(decimal)
            return Number(mantissa, exponent)
        m = self.expr_token(re_string)
        if m:
            return String(m.group(1))
        self.error('Expected expression')

def format_list(xs):
    return ' '.join(str(x) for x in xs)

class Send(object):
    def __init__(self, receiver, message, args):
        self.receiver = receiver
        self.message = message
        self.args = args

    def __str__(self):
        args = (' ' if self.args else '') + format_list(self.args)
        return '(send %s %s%s)' % (self.message, self.receiver or '<free>', args)

    def resolve_free_vars(self, parent):
        for i, arg in enumerate(self.args):
            self.args[i] = arg.resolve_free_vars(parent)
        if self.receiver:
            self.receiver = self.receiver.resolve_free_vars(parent)
        else:
            if len(self.args) == 0:
                ref = parent.lookup_var(self.message)
                if ref:
                    return ref
            self.receiver_block = parent.lookup_receiver(self.message)
            if not self.receiver_block:
                raise Exception("Receiver could not be resolved for '%s'" % self.message)
        return self

    def resolve_block_refs(self, parent):
        for i, arg in enumerate(self.args):
            self.args[i] = arg.resolve_block_refs(parent)
        if self.receiver:
            self.receiver = self.receiver.resolve_block_refs(parent)
        else:
            block = self.receiver_block
            if block.is_constant and block != parent.find_block():
                # No need to get block ref for constant blocks
                self.receiver = block.constant_ref
            else:
                receiver = parent.get_block_ref(block.block_id)
                # Direct slot access optimisation
                if len(self.args) == 0 and self.message in block.vars:
                    return SlotGet(receiver, block.vars[self.message].index)
                if len(self.args) == 1 and self.message[:-1] in block.vars:
                    return SlotSet(receiver, block.vars[self.message[:-1]].index, self.args[0])
                self.receiver = receiver
        return self

class BlockVariable(object):
    def __init__(self, name, mutable, index, init_ref=None):
        self.name = name
        self.mutable = mutable
        self.index = index
        self.init_ref = init_ref
        self.self_ref = SlotGet(Self, index)

class Block(object):
    def __init__(self, block_id, vars, methods):
        self.block_id = block_id
        self.vars_list = vars
        self.vars = {var.name: var for var in self.vars_list}
        self.methods = {method.symbol: method for method in methods}
        self.block_refs = {}
        self.blocks_needed = set()
        # Generate getter and setter methods
        for var in vars:
            self.methods[var.name] = Method(var.name, [], var.self_ref)
            if var.mutable:
                setter = var.name + ':'
                self.methods[setter] = Method(setter, [var.name], var.self_ref.setter(Send(None, var.name, [])))

    def __str__(self):
        args = ' (' + ' '.join('%s %s' % (var.name, var.init_ref) for var in self.vars_list) + ')' if self.vars_list else ''
        methods = ' ' + format_list(x[1] for x in sorted(self.methods.items())) if self.methods else ''
        return '(block #%d%s%s)' % (self.block_id, args, methods)

    def find_block(self):
        return self

    def resolve_free_vars(self, parent):
        for var in self.vars_list:
            var.init_ref = parent.lookup_var(var.name)
        self.parent = parent
        for method in self.methods.values():
            method.resolve_free_vars(self)
        return self

    def resolve_block_refs(self, parent):
        self.is_constant = (len(self.vars_list) == 0 and all(block.is_constant for block in self.blocks_needed))
        if self.is_constant:
            self.constant_ref = ConstantBlock(self.block_id)
        for method in self.methods.values():
            method.resolve_block_refs(self)
        return self

    def lookup_var(self, symbol):
        if symbol not in self.methods:
            ref = self.parent.lookup_var(symbol)
            if ref:
                var = BlockVariable(symbol, False, len(self.vars_list), ref)
                self.vars[symbol] = var
                self.vars_list.append(var)
                return var.self_ref

    def lookup_receiver(self, symbol):
        if symbol in self.methods:
            return self
        block = self.parent.lookup_receiver(symbol)
        if block:
            self.blocks_needed.add(block)
        return block

    def get_block_ref(self, block_id):
        if block_id == self.block_id:
            return Self
        if block_id in self.block_refs:
            return self.block_refs[block_id]
        init_ref = self.parent.get_block_ref(block_id)
        var = BlockVariable('.block-%d' % block_id, False, len(self.vars_list), init_ref)
        self.vars_list.append(var)
        self.vars[var.name] = var
        self.block_refs[block_id] = var.self_ref
        return var.self_ref

class LocalVariable(object):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def __str__(self):
        return '(let %s %s)' % (self.name, self.expr)

    def resolve_free_vars(self, parent):
        self.expr = self.expr.resolve_free_vars(parent)
        self.local_ref = parent.add_local(self.name)
        return self

    def resolve_block_refs(self, parent):
        self.expr = self.expr.resolve_block_refs(parent)
        return self

class Method(object):
    def __init__(self, symbol, args, expr):
        self.symbol = symbol
        self.locals = []
        self.args = args
        self.vars = {}
        for index, arg in enumerate(args):
            ref = LocalGet(index)
            self.locals.append(ref)
            self.vars[arg] = ref
        self.expr = expr

    def __str__(self):
        args = ' ' + format_list(self.args) if self.args else ''
        return '(define (%s%s) %s)' % (self.symbol, args, self.expr)

    def add_local(self):
        ref = LocalGet(len(self.locals))
        self.locals.append(ref)
        return ref

    def find_method(self):
        return self

    def find_block(self):
        return self.parent.find_block()

    def resolve_free_vars(self, parent):
        self.parent = parent
        self.expr = self.expr.resolve_free_vars(self)
        return self

    def resolve_block_refs(self, parent):
        self.expr = self.expr.resolve_block_refs(self)
        return self

    def lookup_var(self, symbol):
        if symbol in self.vars:
            return self.vars[symbol]
        return self.parent.lookup_var(symbol)

    def lookup_receiver(self, symbol):
        return self.parent.lookup_receiver(symbol)

    def get_block_ref(self, block_id):
        return self.parent.get_block_ref(block_id)

class Sequence(object):
    def __init__(self, statements):
        self.statements = statements

    def __str__(self):
        return '(begin %s)' % format_list(self.statements)

    def add_local(self, name):
        ref = self.method.add_local()
        self.vars[name] = ref
        return ref

    def find_method(self):
        return self.parent.find_method()

    def find_block(self):
        return self.parent.find_block()

    def resolve_free_vars(self, parent):
        self.parent = parent
        self.method = self.find_method()
        self.vars = {}
        for i, statement in enumerate(self.statements):
            self.statements[i] = statement.resolve_free_vars(self)
        return self

    def resolve_block_refs(self, parent):
        for i, statement in enumerate(self.statements):
            self.statements[i] = statement.resolve_block_refs(self)
        return self

    def lookup_var(self, symbol):
        if symbol in self.vars:
            return self.vars[symbol]
        return self.parent.lookup_var(symbol)

    def lookup_receiver(self, symbol):
        return self.parent.lookup_receiver(symbol)

    def get_block_ref(self, block_id):
        return self.parent.get_block_ref(block_id)

class Array(object):
    def __init__(self, elems):
        self.elems = elems

    def __str__(self):
        return '(array %s)' % format_list(self.elems)

    def resolve_free_vars(self, parent):
        for i, elem in enumerate(self.elems):
            self.elems[i] = elem.resolve_free_vars(parent)
        return self

    def resolve_block_refs(self, parent):
        for i, elem in enumerate(self.elems):
            self.elems[i] = elem.resolve_block_refs(parent)
        return self

class Self(object):
    def __str__(self):
        return 'self'

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

class ConstantBlock(object):
    def __init__(self, block_id):
        self.block_id = block_id

    def __str__(self):
        return '(constant-block #%d)' % self.block_id

class LocalGet(object):
    def __init__(self, index):
        self.index = index

    def __str__(self):
        return '(local-get %d)' % self.index

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

class SlotGet(object):
    def __init__(self, obj_expr, index):
        self.obj_expr = obj_expr
        self.index = index

    def __str__(self):
        return '(slot-get %s %d)' % (self.obj_expr, self.index)

    def setter(self, set_expr):
        return SlotSet(self.obj_expr, self.index, set_expr)

    def resolve_free_vars(self, parent):
        self.obj_expr = self.obj_expr.resolve_free_vars(parent)
        return self

    def resolve_block_refs(self, parent):
        self.obj_expr = self.obj_expr.resolve_block_refs(parent)
        return self

class SlotSet(object):
    def __init__(self, obj_expr, index, set_expr):
        self.obj_expr = obj_expr
        self.index = index
        self.set_expr = set_expr

    def __str__(self):
        return '(slot-set! %s %d %s)' % (self.obj_expr, self.index, self.set_expr)

    def resolve_free_vars(self, parent):
        self.obj_expr = self.obj_expr.resolve_free_vars(parent)
        self.set_expr = self.set_expr.resolve_free_vars(parent)
        return self

    def resolve_block_refs(self, parent):
        self.obj_expr = self.obj_expr.resolve_block_refs(parent)
        self.set_expr = self.set_expr.resolve_block_refs(parent)
        return self

class Number(object):
    def __init__(self, mantissa, exponent):
        self.mantissa = mantissa
        self.exponent = exponent

    def __str__(self):
        return '(number %s%s)' % (self.mantissa, 'e' + self.exponent if self.exponent else '')

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

class String(object):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "(string '" + self.value + "')"

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

class TopLevel(object):
    def lookup_var(self, symbol):
        pass

    def lookup_receiver(self, symbol):
        pass

    def get_block_ref(self, block_id):
        pass

Self = Self()
TopLevel = TopLevel()

reserved_names = {
    'self': Self,
}

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).block()

def compile_file(filename):
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(TopLevel)
    ast = ast.resolve_block_refs(TopLevel)
    return ast

if __name__ == '__main__':
    import sys
    for filename in sys.argv[1:]:
        try:
            print(compile_file(filename))
        except SyntaxError as e:
            print(e)
