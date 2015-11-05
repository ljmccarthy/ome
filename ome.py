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
        block = Block(vars, methods)
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
            name = self.check_name(statement.symbol)
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
            whole_stripped = whole.rstrip('0') or '0'
            significand = int(whole_stripped, 10)
            trailing = len(whole) - len(whole_stripped)
            exponent = (int(exponent, 10) if exponent else 0) + trailing
            decimal = decimal.rstrip('0') if decimal else ''
            if decimal:
                significand = significand * 10**(len(decimal)) + int(decimal, 10)
                exponent -= len(decimal)
            return Number(significand, exponent)
        m = self.expr_token(re_string)
        if m:
            return String(m.group(1))
        self.error('Expected expression')

def format_list(xs):
    return ' '.join(str(x) for x in xs)

class Send(object):
    def __init__(self, receiver, message, args):
        self.receiver = receiver
        self.symbol = message
        self.args = args

    def __str__(self):
        args = (' ' if self.args else '') + format_list(self.args)
        return '(send %s %s%s)' % (self.symbol, self.receiver or '<free>', args)

    def resolve_free_vars(self, parent):
        for i, arg in enumerate(self.args):
            self.args[i] = arg.resolve_free_vars(parent)
        if self.receiver:
            self.receiver = self.receiver.resolve_free_vars(parent)
        else:
            if len(self.args) == 0:
                ref = parent.lookup_var(self.symbol)
                if ref:
                    return ref
            self.receiver_block = parent.lookup_receiver(self.symbol)
            if not self.receiver_block:
                raise Exception("Receiver could not be resolved for '%s'" % self.symbol)
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
                receiver = block.constant_ref
            else:
                receiver = parent.get_block_ref(block)
                # Direct slot access optimisation
                if len(self.args) == 0 and self.symbol in block.vars:
                    return SlotGet(receiver, block.vars[self.symbol].index)
                if len(self.args) == 1 and self.symbol[:-1] in block.vars:
                    return SlotSet(receiver, block.vars[self.symbol[:-1]].index, self.args[0])
            # Convert Send to a Call since we know which type of block we're sending to
            return Call(block, receiver, self.symbol, self.args)
        return self

    def collect_blocks(self, block_list):
        self.receiver.collect_blocks(block_list)
        for arg in self.args:
            arg.collect_blocks(block_list)

    def generate_code(self, code, dest):
        receiver = self.receiver.generate_code(code, code.add_temp())
        args = [arg.generate_code(code, code.add_temp()) for arg in self.args]
        code.add_instruction(SEND(dest, self.symbol, receiver, args))
        return dest

    check_error = True

class Call(object):
    def __init__(self, block, receiver, message, args):
        self.block = block
        self.receiver = receiver
        self.symbol = message
        self.args = args

    def __str__(self):
        args = (' ' if self.args else '') + format_list(self.args)
        block_id = getattr(self.block, 'block_id', '<blockid>')
        return '(call %s/%s %s%s)' % (self.symbol, block_id, self.receiver, args)

    def collect_blocks(self, block_list):
        self.receiver.collect_blocks(block_list)
        for arg in self.args:
            arg.collect_blocks(block_list)

    def generate_code(self, code, dest):
        receiver = self.receiver.generate_code(code, code.add_temp())
        args = [arg.generate_code(code, code.add_temp()) for arg in self.args]
        code.add_instruction(CALL(dest, self.block.block_id, self.symbol, receiver, args))
        return dest

    check_error = True

class BlockVariable(object):
    def __init__(self, name, mutable, index, init_ref=None):
        self.name = name
        self.mutable = mutable
        self.index = index
        self.init_ref = init_ref
        self.self_ref = SlotGet(Self, index)

    def generate_code(self, code):
        return self.init_ref.generate_code(code, code.add_temp())

class Block(object):
    def __init__(self, vars, methods):
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
        return '(block%s%s)' % (args, methods)

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
            self.constant_ref = ConstantBlock(self)
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

    def get_block_ref(self, block):
        if block is self:
            return Self
        if block in self.block_refs:
            return self.block_refs[block]
        init_ref = self.parent.get_block_ref(block)
        var = BlockVariable('<blockref>', False, len(self.vars_list), init_ref)
        self.vars_list.append(var)
        self.vars[var.name] = var
        self.block_refs[block] = var.self_ref
        return var.self_ref

    def collect_blocks(self, block_list):
        block_list.append(self)
        for method in self.methods.values():
            method.collect_blocks(block_list)

    def generate_code(self, code, dest):
        args = [var.generate_code(code) for var in self.vars_list]
        code.add_instruction(CREATE(dest, self.block_id, args))
        return dest

    check_error = False

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

    def collect_blocks(self, block_list):
        self.expr.collect_blocks(block_list)

    def generate_code(self, code, dest):
        return self.expr.generate_code(code, self.local_ref.generate_code(code, VOID))

    check_error = False

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

    def get_block_ref(self, block):
        return self.parent.get_block_ref(block)

    def collect_blocks(self, block_list):
        self.expr.collect_blocks(block_list)

    def generate_code(self):
        code = MethodCode(len(self.args), len(self.locals) - len(self.args))
        dest = self.expr.generate_code(code, code.add_temp())
        code.add_instruction(RETURN(dest))
        return code

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

    def get_block_ref(self, block):
        return self.parent.get_block_ref(block)

    def collect_blocks(self, block_list):
        for statement in self.statements:
            statement.collect_blocks(block_list)

    def generate_code(self, code, dest):
        error_label = None
        for statement in self.statements[:-1]:
            statement.generate_code(code, dest)
            if statement.check_error:
                if not error_label:
                    error_label = code.add_label()
                code.add_instruction(ON_ERROR(dest, error_label))
        dest = self.statements[-1].generate_code(code, dest)
        if error_label:
            error_label.location = code.here()
        return dest

    @property
    def check_error(self):
        return self.statements[-1].check_error

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

    def collect_blocks(self, block_list):
        for elem in self.elems:
            elem.collect_blocks(block_list)

    def generate_code(self, code, dest):
        code.add_instruction(CREATE_ARRAY(dest, len(self.elems)))
        for i, elem in enumerate(self.elems):
            elem_dest = elem.generate_code(code, code.add_temp())
            code.add_instruction(SET_SLOT(dest, i, elem_dest))
        return dest

    check_error = False

class Self(object):
    def __str__(self):
        return 'self'

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def collect_blocks(self, block_list):
        pass

    def generate_code(self, code, dest):
        return SELF

    check_error = False

class ConstantBlock(object):
    def __init__(self, block):
        self.block = block

    def __str__(self):
        return '<constant-block>'

    def collect_blocks(self, block_list):
        pass

    def generate_code(self, code, dest):
        code.add_instruction(CREATE(dest, self.block.block_id, []))
        return dest

class LocalGet(object):
    def __init__(self, index):
        self.index = index

    def __str__(self):
        return '(local-get %d)' % self.index

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def collect_blocks(self, block_list):
        pass

    def generate_code(self, code, dest):
        return code.locals[self.index]

    check_error = False

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

    def collect_blocks(self, block_list):
        self.obj_expr.collect_blocks(block_list)

    def generate_code(self, code, dest):
        object = self.obj_expr.generate_code(code, code.add_temp())
        code.add_instruction(GET_SLOT(dest, object, self.index))
        return dest

    check_error = False

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

    def collect_blocks(self, block_list):
        self.obj_expr.collect_blocks(block_list)
        self.set_expr.collect_blocks(block_list)

    def generate_code(self, code, dest):
        value = self.set_expr.generate_code(code, code.add_temp())
        object = self.obj_expr.generate_code(code, code.add_temp())
        code.add_instruction(SET_SLOT(object, self.index, value))
        return VOID

    check_error = False

def encode_tagged_value(tag, value):
    return tag | (value << 16)

MIN_INT = -2**47
MAX_INT = 2**47 - 1
MIN_EXPONENT = -2**7
MAX_EXPONENT = 2**7 - 1
MIN_SIGNIFICAND = -2**39
MAX_SIGNIFICAND = 2**39 - 1

MASK_INT = (1 << 48) - 1
MASK_EXPONENT = (1 << 8) - 1
MASK_SIGNIFICAND = (1 << 40) - 1

class Number(object):
    def __init__(self, significand, exponent):
        self.significand = significand
        self.exponent = exponent

    def __str__(self):
        return '(number %s%s)' % (self.significand, 'e%s' % self.exponent if self.exponent else '')

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def collect_blocks(self, block_list):
        pass

    def encode(self):
        if self.exponent >= 0:
            value = self.significand * 10**self.exponent
            if MIN_INT <= value <= MAX_INT:
                return encode_tagged_value(builtin_type_tag['Small-Integer'], value & MASK_INT)

        if not (MIN_EXPONENT <= self.exponent <= MAX_EXPONENT
        and MIN_SIGNIFICAND <= self.significand <= MAX_SIGNIFICAND):
            raise Exception('Number out of range: %se%s' % (self.significand, self.exponent))

        value = ((self.significand & MASK_SIGNIFICAND) << 8) | (self.exponent & MASK_EXPONENT)
        return encode_tagged_value(builtin_type_tag['Small-Decimal'], value)

    def generate_code(self, code, dest):
        code.add_instruction(LOAD_VALUE(dest, self.encode()))
        return dest

    check_error = False

class String(object):
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return "(string '" + self.string + "')"

    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def collect_blocks(self, block_list):
        pass

    def generate_code(self, code, dest):
        code.add_instruction(LOAD_STRING(dest, self.string))
        return dest

    check_error = False

class TopLevel(object):
    def lookup_var(self, symbol):
        pass

    def lookup_receiver(self, symbol):
        pass

    def get_block_ref(self, block):
        pass

class Label(object):
    def __init__(self, name, location):
        self.name = name
        self.location = location

class MethodCode(object):
    def __init__(self, num_args, num_locals):
        self.num_args = num_args
        self.locals = [LOCAL(i) for i in range(num_args + num_locals)]
        self.instructions = []
        self.labels = []
        self.dest = self.add_temp()

    def add_temp(self):
        local = LOCAL(len(self.locals))
        self.locals.append(local)
        return local

    def here(self):
        return len(self.instructions)

    def add_label(self):
        label = Label('.L%d' % len(self.labels), self.here())
        self.labels.append(label)
        return label

    def add_instruction(self, instruction):
        index = len(self.instructions)
        self.instructions.append(instruction)
        return index

    def build_labels_dict(self):
        labels_dict = {}
        for label in self.labels:
            if label.location not in labels_dict:
                labels_dict[label.location] = []
            labels_dict[label.location].append(label.name)
        return labels_dict

class LOCAL(object):
    def __init__(self, index):
        self.index = index

    def __str__(self):
        return '%%%d' % self.index

class SELF(object):
    def __str__(self):
        return '%self'

class VOID(object):
    def __str__(self):
        return '%void'

SELF = SELF()
VOID = VOID()

class SEND(object):
    def __init__(self, dest, symbol, receiver, args):
        self.dest = dest
        self.symbol = symbol
        self.receiver = receiver
        self.args = args

    def __str__(self):
        return '%s := SEND %s %s %s' % (self.dest, self.symbol, self.receiver, format_list(self.args))

class CALL(object):
    def __init__(self, dest, block_id, symbol, receiver, args):
        self.dest = dest
        self.block_id = block_id
        self.symbol = symbol
        self.receiver = receiver
        self.args = args

    def __str__(self):
        return '%s := CALL %s/%s %s %s' % (self.dest, self.symbol, self.block_id, self.receiver, format_list(self.args))

class CREATE(object):
    def __init__(self, dest, block_id, args):
        self.dest = dest
        self.block_id = block_id
        self.args = args

    def __str__(self):
        return '%s := CREATE %s %s' % (self.dest, self.block_id, format_list(self.args))

class CREATE_ARRAY(object):
    def __init__(self, dest, size):
        self.dest = dest
        self.size = size

    def __str__(self):
        return '%s := CREATE_ARRAY %s' % (self.dest, self.size)

class LOAD_VALUE(object):
    def __init__(self, dest, value):
        self.dest = dest
        self.value = value

    def __str__(self):
        return '%s := $%016X' % (self.dest, self.value)

class LOAD_STRING(object):
    def __init__(self, dest, string):
        self.dest = dest
        self.string = string

    def __str__(self):
        return "%s := '%s'" % (self.dest, self.string)

class GET_SLOT(object):
    def __init__(self, dest, object, index):
        self.dest = dest
        self.object = object
        self.index = index

    def __str__(self):
        return '%s := %s[%s]' % (self.dest, self.object, self.index)

class SET_SLOT(object):
    def __init__(self, object, index, value):
        self.object = object
        self.index = index
        self.value = value

    def __str__(self):
        return '%s[%s] := %s' % (self.object, self.index, self.value)

class ON_ERROR(object):
    def __init__(self, dest, label):
        self.dest = dest
        self.label = label

    def __str__(self):
        return 'ON ERROR %s GOTO %s' % (self.dest, self.label.name)

class RETURN(object):
    def __init__(self, dest):
        self.dest = dest

    def __str__(self):
        return 'RETURN %s' % self.dest

Self = Self()
TopLevel = TopLevel()

reserved_names = {
    'self': Self,
}

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).block()

builtin_data_types = ['False', 'True', 'Empty', 'Small-Integer', 'Small-Decimal']
builtin_object_types = ['String', 'Array']
builtin_type_tag = {}

def allocate_block_ids(block_list):
    block_id = 0
    for tag in builtin_data_types:
        builtin_type_tag[tag] = block_id
        block_id += 1
    for block in block_list:
        if block.is_constant:
            block.block_id = block_id
            block_id += 1
    first_object_id = block_id
    for tag in builtin_object_types:
        builtin_type_tag[tag] = block_id
        block_id += 1
    for block in block_list:
        if not block.is_constant:
            block.block_id = block_id
            block_id += 1
    return first_object_id, block_id

def build_code_table(block_list):
    code_table = {}
    for block in block_list:
        for method in block.methods.values():
            if method.symbol not in code_table:
                code_table[method.symbol] = {}
            code_table[method.symbol][block.block_id] = method.generate_code()
    return code_table

def print_code_table(code_table):
    for symbol, methods in sorted(code_table.items()):
        print('MESSAGE', symbol, '{')
        for block_id, code in sorted(methods.items()):
            print('    BLOCK', block_id, '{')
            labels_dict = code.build_labels_dict()
            for i, instruction in enumerate(code.instructions):
                for label in labels_dict.get(i, ()):
                    print('    %s:' % label)
                print ('       ', instruction)
            print('    }')
        print('}')

def compile_file(filename):
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(TopLevel)
    ast = ast.resolve_block_refs(TopLevel)
    block_list = []
    ast.collect_blocks(block_list)
    first_object_id, num_block_ids = allocate_block_ids(block_list)
    print('# Allocated %d block IDs, 0-%d data types, %d-%d object types\n' % (
        num_block_ids, first_object_id - 1, first_object_id, num_block_ids - 1))
    code_table = build_code_table(block_list)
    print_code_table(code_table)

if __name__ == '__main__':
    import sys
    for filename in sys.argv[1:]:
        try:
            compile_file(filename)
        except SyntaxError as e:
            print(e)
