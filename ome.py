# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re
import struct
from contextlib import contextmanager

re_newline = re.compile(r'\r\n|\r|\n')
re_spaces = re.compile(r'[ \r\n\t]*')
re_comment = re.compile(r'(?:#|--)([^\r\n]*)')
re_name = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)')
re_arg_name = re.compile(r'([a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)')
re_keyword = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*:)')
re_number = re.compile(r'([+-]?[0-9]+)(?:\.([0-9]+))?(?:e([+-]?[0-9]+))?')
re_string = re.compile(r"'((?:\\'|[^\r\n'])*)'")
re_assign = re.compile(r'=|:=')
re_end_token = re.compile(r'[|)}\]]')
re_symbol_part = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)(:,*)?')

class Error(Exception):
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
        if name in reserved_names:
            self.error('%s is a reserved name' % name)
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
            statements.append(LocalVariable(name, self.expr()))
            slots.append(BlockVariable(name, mutable, len(slots)))
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
        if not slots and not methods:
            return EmptyBlock
        block = Block(slots, methods)
        if statements:
            statements.append(block)
            return Sequence(statements)
        return block

    def toplevel(self):
        block = self.block()
        if self.pos < len(self.stream):
            self.error('Expected declaration or end of file')
        return block

    def statement(self):
        maybe_assign = self.peek(re_name)
        parse_state = self.copy_state()
        statement = self.expr()
        m = self.token(re_assign)
        if m:
            if m.group() == ':=':
                self.error('Mutable variables are only allowed in blocks')
            if not isinstance(statement, Send) or statement.receiver or not maybe_assign:
                parse_state.error('Left hand side of assignment must be a name')
            if statement.symbol[0] == '~':
                parse_state.error('Local variables cannot be private')
            name = self.check_name(statement.symbol, parse_state)
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
            expr = Send(expr, symbol, args, parse_state)
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
            expr = Send(expr, name, [])
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
            if name in reserved_names:
                return reserved_names[name]
            return Send(None, name, [], parse_state)
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
            return Number(significand, exponent, parse_state)
        m = self.expr_token(re_string)
        if m:
            return String(m.group(1))
        self.error('Expected expression')

def format_list(xs):
    return ' '.join(str(x) for x in xs)

class Send(object):
    def __init__(self, receiver, message, args, parse_state=None):
        self.receiver = receiver
        self.symbol = message
        self.args = args
        self.parse_state = parse_state

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
                self.parse_state.error("Receiver could not be resolved for '%s'" % self.symbol)
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
                if len(self.args) == 0 and self.symbol in block.instance_vars:
                    var = block.instance_vars[self.symbol]
                    return SlotGet(receiver, var.slot_index, var.mutable)
                if len(self.args) == 1 and self.symbol[:-1] in block.instance_vars:
                    var = block.instance_vars[self.symbol[:-1]]
                    return SlotSet(receiver, var.slot_index, self.args[0])
            # Convert Send to a Call since we know which type of block we're sending to
            return Call(block, receiver, self.symbol, self.args)
        return self

    def collect_blocks(self, block_list):
        self.receiver.collect_blocks(block_list)
        for arg in self.args:
            arg.collect_blocks(block_list)

    def generate_code(self, code):
        receiver = code.retval(self.receiver.generate_code(code))
        args = [code.retval(arg.generate_code(code)) for arg in self.args]
        code.add_instruction(SEND(self.symbol, receiver, args))
        return RETVAL

    check_error = True

class Call(object):
    def __init__(self, block, receiver, message, args):
        self.block = block
        self.receiver = receiver
        self.symbol = message
        self.args = args

    def __str__(self):
        args = (' ' if self.args else '') + format_list(self.args)
        tag = getattr(self.block, 'tag', '<tag>')
        return '(call %s/%s %s%s)' % (self.symbol, tag, self.receiver, args)

    def collect_blocks(self, block_list):
        self.receiver.collect_blocks(block_list)
        for arg in self.args:
            arg.collect_blocks(block_list)

    def generate_code(self, code):
        receiver = code.retval(self.receiver.generate_code(code))
        args = [code.retval(arg.generate_code(code)) for arg in self.args]
        tag = self.block.tag if hasattr(self.block, 'tag') else self.block.constant_tag
        code.add_instruction(CALL(tag, self.symbol, receiver, args))
        return RETVAL

    check_error = True

class BlockVariable(object):
    def __init__(self, name, mutable, index, init_ref=None):
        self.name = name
        self.mutable = mutable
        self.private = name[0] == '~'
        self.slot_index = index
        self.init_ref = init_ref
        self.self_ref = SlotGet(Self, index, mutable)

    def generate_code(self, code):
        return self.init_ref.generate_code(code)

class Block(object):
    def __init__(self, slots, methods):
        self.slots = slots  # list of BlockVariables for instance vars, closure vars and block references
        self.methods = methods
        self.instance_vars = {var.name: var for var in slots}
        self.closure_vars = {}
        self.block_refs = {}
        self.blocks_needed = set()
        self.symbols = set(self.instance_vars)  # Set of all symbols this block defines
        self.symbols.update(method.symbol for method in self.methods)

        # Generate getter and setter methods
        for var in slots:
            setter = var.name + ':'
            if var.mutable:
                self.symbols.add(setter)
            if not var.private:
                self.methods.append(Method(var.name, [], var.self_ref))
                if var.mutable:
                    self.methods.append(Method(setter, [var.name], var.self_ref.setter(Send(None, var.name, []))))

    def __str__(self):
        args = ' (' + ' '.join('%s %s' % (var.name, var.init_ref) for var in self.slots) + ')' if self.slots else ''
        methods = ' ' + format_list(self.methods) if self.methods else ''
        return '(block%s%s)' % (args, methods)

    @property
    def is_constant(self):
        return len(self.slots) == 0 and all(block.is_constant for block in self.blocks_needed)

    def find_block(self):
        return self

    def resolve_free_vars(self, parent):
        for var in self.slots:
            var.init_ref = parent.lookup_var(var.name)
        self.parent = parent
        for method in self.methods:
            method.resolve_free_vars(self)
        return self

    def resolve_block_refs(self, parent):
        if self.is_constant:
            self.constant_ref = ConstantBlock(self)
        for method in self.methods:
            method.resolve_block_refs(self)
        return self

    def lookup_var(self, symbol):
        if symbol in self.closure_vars:
            return self.closure_vars[symbol].self_ref
        if symbol not in self.symbols:
            ref = self.parent.lookup_var(symbol)
            if ref:
                var = BlockVariable(symbol, False, len(self.slots), ref)
                self.closure_vars[symbol] = var
                self.slots.append(var)
                return var.self_ref

    def lookup_receiver(self, symbol):
        if symbol in self.symbols:
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
        var = BlockVariable('<blockref>', False, len(self.slots), init_ref)
        self.block_refs[block] = var.self_ref
        self.slots.append(var)
        return var.self_ref

    def collect_blocks(self, block_list):
        block_list.append(self)
        for method in self.methods:
            method.collect_blocks(block_list)

    def generate_code(self, code):
        args = [var.generate_code(code) for var in self.slots]
        dest = code.add_temp()
        if hasattr(self, 'tag'):
            code.add_instruction(CREATE(dest, self.tag, args))
        else:
            code.add_instruction(LOAD_VALUE(dest, code.program.tag_constant_block, self.constant_tag))
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

    def generate_code(self, code):
        local = self.local_ref.generate_code(code)
        expr = self.expr.generate_code(code)
        if expr == RETVAL:
            code.add_instruction(GET_RETVAL(local))
        else:
            code.add_instruction(ALIAS(local, expr))
        return local

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

    def generate_code(self, program):
        code = MethodCode(program, len(self.args), len(self.locals) - len(self.args))
        code.set_retval(self.expr.generate_code(code))
        #print('optimising %s' % self.symbol)
        code.optimise()
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
        self.method = parent.find_method()
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

    def generate_code(self, code):
        error_label = None
        for statement in self.statements[:-1]:
            dest = statement.generate_code(code)
            if statement.check_error:
                code.set_retval(dest)
                if not error_label:
                    error_label = code.add_label()
                code.add_instruction(ON_ERROR(error_label))
        code.set_retval(self.statements[-1].generate_code(code))
        if error_label:
            error_label.location = code.here()
        return RETVAL

    @property
    def check_error(self):
        return any(statement.check_error for statement in self.statements)

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

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(CREATE_ARRAY(dest, len(self.elems)))
        for i, elem in enumerate(self.elems):
            elem = elem.generate_code(code)
            code.add_instruction(SET_SLOT(dest, i, elem))
        return dest

    check_error = False

class TerminalNode(object):
    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def collect_blocks(self, block_list):
        pass

    check_error = False

class EmptyBlock(TerminalNode):
    def __str__(self):
        return '(block)'

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, code.program.tag_constant_block, 0))
        return dest

EmptyBlock = EmptyBlock()

class ConstantBlock(TerminalNode):
    def __init__(self, block):
        self.block = block

    def __str__(self):
        return '<constant-block>'

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, code.program.tag_constant_block, self.block.constant_tag))
        return dest

class Self(TerminalNode):
    def __str__(self):
        return 'self'

    def generate_code(self, code):
        return code.locals[0]

Self = Self()

reserved_names = {
    'self': Self,
}

class LocalGet(TerminalNode):
    def __init__(self, index):
        self.local_index = index

    def __str__(self):
        return '(local-get %d)' % self.local_index

    def generate_code(self, code):
        return code.locals[self.local_index + 1]

class SlotGet(object):
    def __init__(self, obj_expr, slot_index, mutable):
        self.obj_expr = obj_expr
        self.slot_index = slot_index
        self.mutable = mutable

    def __str__(self):
        return '(slot-get %s %d)' % (self.obj_expr, self.slot_index)

    def setter(self, set_expr):
        return SlotSet(self.obj_expr, self.slot_index, set_expr)

    def resolve_free_vars(self, parent):
        self.obj_expr = self.obj_expr.resolve_free_vars(parent)
        return self

    def resolve_block_refs(self, parent):
        self.obj_expr = self.obj_expr.resolve_block_refs(parent)
        return self

    def collect_blocks(self, block_list):
        self.obj_expr.collect_blocks(block_list)

    def generate_code(self, code):
        object = self.obj_expr.generate_code(code)
        dest = code.add_temp()
        code.add_instruction(GET_SLOT(dest, object, self.slot_index))
        return dest

    check_error = True

class SlotSet(object):
    def __init__(self, obj_expr, slot_index, set_expr):
        self.obj_expr = obj_expr
        self.slot_index = slot_index
        self.set_expr = set_expr

    def __str__(self):
        return '(slot-set! %s %d %s)' % (self.obj_expr, self.slot_index, self.set_expr)

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

    def generate_code(self, code):
        object = code.retval(self.obj_expr.generate_code(code))
        value = code.retval(self.set_expr.generate_code(code))
        code.add_instruction(SET_SLOT(object, self.slot_index, value))
        return value

    check_error = True

NUM_BITS = 64
NUM_TAG_BITS = 16
NUM_DATA_BITS = NUM_BITS - NUM_TAG_BITS
NUM_EXPONENT_BITS = 8
NUM_SIGNIFICAND_BITS = NUM_DATA_BITS - NUM_EXPONENT_BITS

MAX_TAG = 2**NUM_TAG_BITS - 1
MIN_INT = -2**(NUM_DATA_BITS-1)
MAX_INT = 2**(NUM_DATA_BITS-1) - 1
MIN_EXPONENT = -2**(NUM_EXPONENT_BITS-1)
MAX_EXPONENT = 2**(NUM_EXPONENT_BITS-1) - 1
MIN_SIGNIFICAND = -2**(NUM_SIGNIFICAND_BITS-1)
MAX_SIGNIFICAND = 2**(NUM_SIGNIFICAND_BITS-1) - 1

MASK_INT = (1 << NUM_DATA_BITS) - 1
MASK_EXPONENT = (1 << NUM_EXPONENT_BITS) - 1
MASK_SIGNIFICAND = (1 << NUM_SIGNIFICAND_BITS) - 1

class Number(TerminalNode):
    def __init__(self, significand, exponent, parse_state):
        self.significand = significand
        self.exponent = exponent
        self.parse_state = parse_state

    def __str__(self):
        return '(number %s%s)' % (self.significand, 'e%s' % self.exponent if self.exponent else '')

    def encode(self, program):
        if self.exponent >= 0:
            value = self.significand * 10**self.exponent
            if MIN_INT <= value <= MAX_INT:
                return (program.tag_integer, value & MASK_INT)

        if not (MIN_EXPONENT <= self.exponent <= MAX_EXPONENT
        and MIN_SIGNIFICAND <= self.significand <= MAX_SIGNIFICAND):
            self.parse_state.error('Number out of range')

        value = ((self.significand & MASK_SIGNIFICAND) << 8) | (self.exponent & MASK_EXPONENT)
        return (program.tag_decimal, value)

    def generate_code(self, code):
        tag, value = self.encode(code.program)
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, tag, value))
        return dest

class String(TerminalNode):
    def __init__(self, string):
        self.string = string

    def __str__(self):
        return "(string '" + self.string + "')"

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_STRING(dest, self.string))
        return dest

class TopLevel(object):
    def lookup_var(self, symbol):
        pass

    def lookup_receiver(self, symbol):
        pass

    def get_block_ref(self, block):
        pass

TopLevel = TopLevel()

class Label(object):
    def __init__(self, name, location):
        self.name = name
        self.location = location

class MethodCode(object):
    def __init__(self, program, num_args, num_locals):
        self.program = program
        self.num_args = num_args + 1  # self is arg 0
        self.locals = list(range(1 + num_args + num_locals))
        self.instructions = []
        self.labels = set()
        self.dest = self.add_temp()

    def add_temp(self):
        local = len(self.locals)
        self.locals.append(local)
        return local

    def here(self):
        return len(self.instructions)

    def add_label(self):
        label = Label('.L%d' % len(self.labels), self.here())
        self.labels.add(label)
        return label

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def retval(self, local):
        if local != RETVAL:
            return local
        temp = self.add_temp()
        self.add_instruction(GET_RETVAL(temp))
        return temp

    def set_retval(self, source):
        if source != RETVAL:
            self.add_instruction(SET_RETVAL(source))

    def optimise(self):
        self.optimise_error_branches()
        self.eliminate_aliases()
        self.find_live_ranges()

    def iter_instructions_by_type(self, type):
        for instruction in self.instructions:
            if isinstance(instruction, type):
                yield instruction

    def optimise_error_branches(self):
        for ins in self.iter_instructions_by_type(ON_ERROR):
            error_label = ins.label
            while error_label.location < len(self.instructions) \
            and isinstance(self.instructions[error_label.location], ON_ERROR):
                error_label = self.instructions[error_label.location].label
            ins.label = error_label

        self.labels = set(ins.label for ins in self.iter_instructions_by_type(ON_ERROR))

    def eliminate_aliases(self):
        """Eliminate all local variable aliases (i.e. ALIAS instructions)."""

        aliases = {}
        retval_aliases = set()
        labels = {label.location: label for label in self.labels}
        instructions = []
        location = 0

        def flush_retval_aliases():
            if retval_aliases:
                saved_retval = retval_aliases.pop()
                instructions.append(GET_RETVAL(self.locals[saved_retval]))
                for needs_retval in retval_aliases:
                    aliases[needs_retval] = saved_retval
                retval_aliases.clear()

        def update_labels(location):
            if location in labels:
                labels[location].location = len(instructions)

        def remove_aliases_from_args(ins):
            for i, arg in enumerate(ins.args):
                if arg in aliases:
                    ins.args[i] = self.locals[aliases[arg]]

        for location, ins in enumerate(self.instructions):
            update_labels(location)
            if isinstance(ins, ALIAS):
                aliases[ins.dest] = aliases.get(ins.source, ins.source)
            elif isinstance(ins, GET_RETVAL):
                retval_aliases.add(ins.dest)
            elif isinstance(ins, SET_RETVAL):
                flush_retval_aliases()
                remove_aliases_from_args(ins)
                instructions.append(ins)
            else:
                if ins.invalidates_retval or any(local in retval_aliases for local in ins.args):
                    flush_retval_aliases()
                remove_aliases_from_args(ins)
                instructions.append(ins)

        update_labels(location + 1)
        self.instructions = instructions

    def find_live_ranges(self):
        """Find the set of live locals for each instruction."""

        init_point = {i: 0 for i in range(self.num_args)}
        dead_point = {i: 0 for i in range(self.num_args)}

        for loc, ins in enumerate(self.instructions):
            if hasattr(ins, 'dest'):
                init_point[ins.dest] = loc
                dead_point[ins.dest] = loc
            for local in ins.args:
                dead_point[local] = loc

        def reverse_dict(d):
            result = {}
            for key, value in d.items():
                if value not in result:
                    result[value] = []
                result[value].append(key)
            return result

        init_locations = reverse_dict(init_point)
        dead_locations = reverse_dict(dead_point)

        live_set = set(range(self.num_args))
        for loc, ins in enumerate(self.instructions):
            ins.live_set_before = frozenset(live_set)
            live_set.update(init_locations.get(loc, []))
            live_set.difference_update(dead_locations.get(loc, []))
            ins.live_set_after = frozenset(live_set)

        # Sanity check
        for ins in self.instructions:
            for arg in ins.args:
                assert arg in ins.live_set_before

    def build_labels_dict(self):
        labels_dict = {}
        for label in self.labels:
            if label.location not in labels_dict:
                labels_dict[label.location] = []
            labels_dict[label.location].append(label.name)
        return labels_dict

class RETVAL(object):
    def __str__(self):
        return '%retval'

RETVAL = RETVAL()

def format_instruction_args(args):
    return ' ' + ' '.join('%%%d' % x for x in args) if args else ''

class SEND(object):
    invalidates_retval = True

    def __init__(self, symbol, receiver, args):
        self.symbol = symbol
        self.label = symbol_to_label(symbol)
        self.args = [receiver] + args

    def __str__(self):
        return 'SEND %%%d %s%s' % (self.args[0], self.symbol, format_instruction_args(self.args[1:]))

    def emit(self, target):
        target.SEND(self)

class CALL(object):
    invalidates_retval = True

    def __init__(self, tag, symbol, receiver, args):
        self.tag = tag
        self.symbol = symbol
        self.label = symbol_to_label(symbol)
        self.args = [receiver] + args

    def __str__(self):
        return 'CALL %%%d $%04X:%s%s' % (self.args[0], self.tag, self.symbol, format_instruction_args(self.args[1:]))

    def emit(self, target):
        target.CALL(self)

class CREATE(object):
    invalidates_retval = False

    def __init__(self, dest, tag, args):
        self.dest = dest
        self.tag = tag
        self.args = args

    def __str__(self):
        return '%%%d = CREATE $%04X%s' % (self.dest, self.tag, format_instruction_args(self.args))

    def emit(self, target):
        target.CREATE(self)

class CREATE_ARRAY(object):
    invalidates_retval = False
    args = ()

    def __init__(self, dest, size):
        self.dest = dest
        self.size = size

    def __str__(self):
        return '%%%d = CREATE_ARRAY %s' % (self.dest, self.size)

    def emit(self, target):
        target.CREATE_ARRAY(self)

class ALIAS(object):
    invalidates_retval = False
    args = ()

    def __init__(self, dest, source):
        self.dest = dest
        self.args = [source]

    def __str__(self):
        return '%%%d = %%%d' % (self.dest, self.source)

    @property
    def source(self):
        return self.args[0]

    def emit(self, target):
        target.ALIAS(self)

class GET_RETVAL(object):
    invalidates_retval = False
    args = ()

    def __init__(self, dest):
        self.dest = dest

    def __str__(self):
        return '%%%d = %%retval' % self.dest

    def emit(self, target):
        target.GET_RETVAL(self)

class SET_RETVAL(object):
    invalidates_retval = True

    def __init__(self, source):
        self.args = [source]

    def __str__(self):
        return '%%retval := %%%d' % self.source

    @property
    def source(self):
        return self.args[0]

    def emit(self, target):
        target.SET_RETVAL(self)

class LOAD_VALUE(object):
    invalidates_retval = False
    args = ()

    def __init__(self, dest, tag, value):
        self.dest = dest
        self.tag = tag
        self.value = value

    def __str__(self):
        return '%%%d = $%04X:%012X' % (self.dest, self.tag, self.value)

    def emit(self, target):
        target.LOAD_VALUE(self)

class LOAD_STRING(object):
    invalidates_retval = False
    args = ()

    def __init__(self, dest, string):
        self.dest = dest
        self.string = string

    def __str__(self):
        return "%%%d = '%s'" % (self.dest, self.string)

    def emit(self, target):
        target.LOAD_STRING(self)

class GET_SLOT(object):
    invalidates_retval = False

    def __init__(self, dest, object, slot_index):
        self.dest = dest
        self.args = [object]
        self.slot_index = slot_index

    def __str__(self):
        return '%%%d = %%%d[%d]' % (self.dest, self.object, self.slot_index)

    @property
    def object(self):
        return self.args[0]

    def emit(self, target):
        target.GET_SLOT(self)

class SET_SLOT(object):
    invalidates_retval = False

    def __init__(self, object, slot_index, value):
        self.args = [object, value]
        self.slot_index = slot_index

    @property
    def object(self):
        return self.args[0]

    @property
    def value(self):
        return self.args[1]

    def __str__(self):
        return '%%%d[%d] := %%%d' % (self.object, self.slot_index, self.value)

    def emit(self, target):
        target.SET_SLOT(self)

class ON_ERROR(object):
    invalidates_retval = False
    args = ()

    def __init__(self, label):
        self.label = label

    def __str__(self):
        return 'ON ERROR GOTO %s' % (self.label.name)

    def emit(self, target):
        target.ON_ERROR(self)

def symbol_to_label(symbol):
    """
    Encodes a symbol into a form that can be used for an assembly label, e.g.
        foo            foo__0
        foo:           foo__1
        foo-bar-baz    foo_bar_baz__0
        foo:,,         foo__3
        foo4:,,bar5:,  foo4__3bar5__2
    """
    return ''.join(
        name.replace('-', '_') + '__' + str(len(args))
        for name, args in re_symbol_part.findall(symbol))

def make_send_label(symbol):
    return 'OME_message_' + symbol_to_label(symbol)

def make_call_label(tag, symbol):
    return 'OME_method_%04X_%s' % (tag, symbol_to_label(symbol))

class CodeGenerator(object):
    def __init__(self, program, code, target_type):
        self.target = target_type(self)
        self.program = program
        self.instructions = code.instructions
        self.labels = code.build_labels_dict()
        self.tag_string = program.tag_string
        self.output = []
        self.head_output = []
        self.tail_output = []

        num_reg_args = min(code.num_args, self.target.num_arg_regs)
        num_stack_args = max(0, code.num_args - num_reg_args)
        self.locals_register = {i: self.target.argument_registers[i] for i in range(num_reg_args)}
        self.register_locals = {self.target.argument_registers[i]: i for i in range(num_reg_args)}
        self.locals_stack = {i + num_reg_args: num_stack_args-i-1 for i in range(num_stack_args)}
        self.stack_locals = {num_stack_args-i-1: i + num_reg_args for i in range(num_stack_args)}
        self.constant_values = {}
        self.constant_strings = {}
        self.num_stack_slots = len(self.stack_locals)
        self.free_stack_slots = set()
        self.free_registers = set(self.target.argument_registers[num_reg_args:] + self.target.temp_registers)

    def generate(self):
        self.find_desired_regs()

        for loc, ins in enumerate(self.instructions):
            if loc in self.labels:
                for label in self.labels[loc]:
                    self.output.append(label + ':')

            # Remove locals from registers that are no longer in the live set
            for local_id in set(self.locals_register.keys()) - ins.live_set_before:
                reg = self.locals_register[local_id]
                del self.locals_register[local_id]
                if reg in self.register_locals:
                    del self.register_locals[reg]
                self.free_registers.add(reg)

            # Remove locals from stack slots that are no longer in the live set
            for local_id in set(self.locals_stack.keys()) - ins.live_set_before:
                slot = self.locals_stack[local_id]
                del self.locals_stack[local_id]
                del self.stack_locals[slot]
                self.free_stack_slots.add(slot)

            locals_locations = ['%s: %%%d' % (reg, local) for reg, local in self.register_locals.items()]
            locals_locations.extend('sp[%d]: %%%d' % (slot, local) for slot, local in self.stack_locals.items())
            self.output.append('\n\t; %s {%s}' % (ins, ', '.join(locals_locations)))

            self.live_set_before = ins.live_set_before
            self.live_set_after = ins.live_set_after
            ins.emit(self)

        if loc + 1 in self.labels:
            for label in self.labels[loc + 1]:
                self.output.append(label + ':')

        self.target.emit_return()
        self.output.extend(self.tail_output)

    def find_desired_regs(self):
        desired_regs = {}
        for loc in range(len(self.instructions)-1, -1, -1):
            ins = self.instructions[loc]
            if hasattr(ins, 'dest'):
                ins.desired_dest_reg = desired_regs.get(ins.dest, None)
            if isinstance(ins, (CALL, SEND)):
                desired_regs = {}
                for i in range(min(len(ins.args), len(self.target.argument_registers))):
                    desired_regs[ins.args[i]] = self.target.argument_registers[i]
            elif isinstance(ins, SET_RETVAL):
                desired_regs[ins.source] = self.target.return_register

    def allocate_stack_slot(self):
        if self.free_stack_slots:
            return self.free_stack_slots.pop()
        slot = self.num_stack_slots
        self.num_stack_slots += 1
        return slot

    def save_register(self, reg):
        """
        Save a register if it contains a local variable that will be needed
        for subsequent instructions. The variable will still appear to be in
        the register, so invalidate_register() should be called once it has
        been modified.
        """
        if reg in self.register_locals:
            evicted_local = self.register_locals[reg]
            #if evicted_local in self.live_set_after:
            if evicted_local not in self.stack_locals:
                slot = self.allocate_stack_slot()
                self.output.append('\t; %%%d evicted to [%d]' % (evicted_local, slot))
                self.locals_stack[evicted_local] = slot
                self.stack_locals[slot] = evicted_local
                self.target.emit_mov_to_stack(slot, reg)

    def invalidate_register(self, reg):
        if reg in self.register_locals:
            local = self.register_locals[reg]
            del self.register_locals[reg]
            if local in self.locals_register:
                del self.locals_register[local]

    def evict_register(self, reg):
        if reg in self.register_locals:
            self.save_register(reg)
            self.invalidate_register(reg)

    def emit_load_local(self, local, reg):
        if local in self.constant_values:
            self.target.emit_load_constant(reg, self.constant_values[local])
        elif local in self.constant_strings:
            self.target.emit_load_tagged_label(reg, self.constant_strings[local], self.tag_string)
        else:
            self.target.emit_mov_from_stack(reg, self.locals_stack[local])

    def get_copy_of_local_in_register(self, local, reg):
        if local in self.locals_register:
            src = self.locals_register[local]
            if local in self.live_set_after:
                self.evict_register(reg)
                self.locals_register[local] = reg
                self.register_locals[reg] = local
                if reg != src:
                    self.target.emit_mov(reg, src)
        else:
            self.evict_register(reg)
            self.emit_load_local(local, reg)

    def get_local_in_register_for_read(self, local, reg):
        if local in self.locals_register:
            src = self.locals_register[local]
            if reg != src:
                self.evict_register(reg)
                self.locals_register[local] = reg
                self.register_locals[reg] = local
                self.target.emit_mov(reg, src)
        else:
            self.evict_register(reg)
            self.emit_load_local(local, reg)

    @contextmanager
    def copy_local_to_any_register(self, local):
        """Temporarily get a copy of a local into any free register that may be modified."""
        if local in self.locals_register:
            src = self.locals_register[local]
            if local not in self.live_set_after:
                # Not needed after this instruction, no need to copy
                yield src
            else:
                reg = self.free_registers.pop()
                self.target.emit_mov(reg, src)
                yield reg
                self.free_registers.add(reg)
        else:
            reg = self.free_registers.pop()
            self.emit_load_local(local, reg)
            yield reg
            self.free_registers.add(reg)

    @contextmanager
    def get_local_to_any_register_for_read(self, local):
        """Get a local variable to a register. May not be modified."""
        if local in self.locals_register:
            yield self.locals_register[local]
        else:
            reg = self.free_registers.pop()
            self.emit_load_local(local, reg)
            yield reg
            self.free_registers.add(reg)

    @contextmanager
    def get_dest_reg(self, ins):
        reg = ins.desired_dest_reg or self.target.temp_registers[0]
        self.evict_register(reg)
        self.locals_register[ins.dest] = reg
        self.register_locals[reg] = ins.dest
        yield reg

    def LOAD_VALUE(self, ins):
        self.constant_values[ins.dest] = (ins.value << NUM_TAG_BITS) | ins.tag

    def LOAD_STRING(self, ins):
        self.constant_strings[ins.dest] = self.program.allocate_string(ins.string)

    def emit_call(self, ins, label):
        # Save needed locals in registers that are not saved across calls
        for reg in self.target.argument_registers:
            if reg in self.register_locals:
                local = self.register_locals[reg]
                if local in ins.live_set_after:
                    self.save_register(reg)

        # Load register arguments
        for i, arg in enumerate(ins.args[:self.target.num_arg_regs]):
            self.get_copy_of_local_in_register(arg, self.target.argument_registers[i])

        # Load stack arguments
        for i, arg in enumerate(ins.args[self.target.num_arg_regs:], 1):
            self.target.emit_stack_arg(i, arg)

        # Registers for saved locals are invalid after the call
        for reg in self.target.argument_registers:
            self.invalidate_register(reg)

        num_stack_args = max(0, len(ins.args) - self.target.num_arg_regs)
        self.target.emit_call(label, num_stack_args)

    def CALL(self, ins):
        self.emit_call(ins, make_call_label(ins.tag, ins.symbol))

    def SEND(self, ins):
        self.emit_call(ins, make_send_label(ins.symbol))

    def GET_RETVAL(self, ins):
        with self.get_dest_reg(ins) as reg:
            self.target.emit_mov(reg, self.target.return_register)

    def SET_RETVAL(self, ins):
        self.get_local_in_register_for_read(ins.source, self.target.return_register)

    def GET_SLOT(self, ins):
        with self.get_dest_reg(ins) as dest_reg:
            with self.copy_local_to_any_register(ins.object) as object_reg:
                self.target.GET_SLOT(dest_reg, object_reg, ins.slot_index)

    def SET_SLOT(self, ins):
        with self.copy_local_to_any_register(ins.object) as object_reg:
            with self.get_local_to_any_register_for_read(ins.value) as value_reg:
                self.target.SET_SLOT(object_reg, ins.slot_index, value_reg)

    def CREATE(self, ins):
        with self.get_dest_reg(ins) as reg:
            self.target.CREATE(reg, ins)

    def ON_ERROR(self, ins):
        self.target.ON_ERROR(ins)

class Target_x86_64(object):
    stack_pointer = 'rsp'
    context_pointer = 'rbp'
    nursery_bump_pointer = 'rbx'
    nursery_limit_pointer = 'r12'
    argument_registers = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
    return_register = 'rax'
    temp_registers = ('r10', 'r11')
    num_arg_regs = len(argument_registers)

    def __init__(self, codegen):
        self.gen = codegen
        self.num_jumpback_labels = 0

    def add_gc_jumpback_label(self):
        return_label = '.gc_return_%d' % self.num_jumpback_labels
        full_label = '.gc_full_%d' % self.num_jumpback_labels
        self.num_jumpback_labels += 1
        return (return_label, full_label)

    def emit(self, format, *args):
        self.gen.output.append('\t' + (format % args))

    def emit_label(self, label):
        self.gen.output.append(label + ':')

    def tail_emit(self, format, *args):
        self.gen.tail_output.append('\t' + (format % args))

    def tail_emit_label(self, label):
        self.gen.tail_output.append('')
        self.gen.tail_output.append(label + ':')

    def emit_load_constant(self, dst, value):
        self.emit('mov %s, 0x%x', dst, value)

    def emit_load_tagged_label(self, dst, label, tag):
        self.emit('mov %s, %s', dst, label)
        self.emit('shl %s, %s', dst, NUM_TAG_BITS)
        if tag != 0:
            self.emit('or %s, %s', dst, tag)

    def emit_mov(self, dst, src):
        self.emit('mov %s, %s', dst, src)

    def emit_mov_from_stack(self, dst, src):
        self.emit('mov %s, [rsp + %s]', dst, src)

    def emit_mov_to_stack(self, dst, src):
        self.emit('mov [rsp + %s], %s', dst, src)

    def emit_stack_arg(self, offset, arg):
        self.emit('mov [rsp - %s], %s', offset * 8, self.gen.get_local_in_register_for_read(arg, self.temp_registers[0]))

    def emit_call(self, label, num_stack_args):
        if num_stack_args > 0:
            self.emit('sub rsp, %s', num_stack_args * 8)
        self.emit('call %s', label)
        if num_stack_args > 0:
            self.emit('add rsp, %s', num_stack_args * 8)

    def emit_return(self):
        self.emit('ret')

    def CREATE(self, dest_reg, ins):
        return_label, full_label = self.add_gc_jumpback_label()
        self.emit_label(return_label)
        self.emit('mov %s, %s', dest_reg, self.nursery_bump_pointer)
        self.emit('add %s, %s', self.nursery_bump_pointer, len(ins.args) * 8)
        self.emit('cmp %s, %s', self.nursery_bump_pointer, self.nursery_limit_pointer)
        self.emit('jae %s', full_label)
        for i, arg in enumerate(ins.args):
            with self.gen.copy_local_to_any_register(arg) as arg_reg:
                self.emit('mov [%s + %s], %s', dest_reg, i * 8, arg_reg)
        self.emit('shl %s, %s', dest_reg, NUM_TAG_BITS)
        if ins.tag != 0:
            self.emit('or %s, %s', dest_reg, ins.tag)

        self.tail_emit_label(full_label)
        self.tail_emit('call OME_collect_nursery')
        self.tail_emit('jmp %s', return_label)

    def CREATE_ARRAY(self, dest_reg, ins):
        pass

    def GET_SLOT(self, dest_reg, object_reg, index):
        self.emit('shr %s, %s', object_reg, NUM_TAG_BITS)
        self.emit('mov %s, [%s + %s]', dest_reg, object_reg, index * 8)

    def SET_SLOT(self, object_reg, index, value_reg):
        self.emit('shr %s, %s', object_reg, NUM_TAG_BITS)
        self.emit('mov [%s + %s], %s', object_reg, index * 8, value_reg)

    def ON_ERROR(self, ins):
        self.emit('test %s, 0x8000', self.return_register)
        self.emit('jnz %s', ins.label.name)

builtin_data_types = ['False', 'True', 'Constant-Block', 'Small-Integer', 'Small-Decimal']
builtin_object_types = ['String', 'Array']

class Program(object):
    def __init__(self, ast):
        self.block_list = []
        self.type_tag = {}
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.string_table_size = 0
        self.string_table = []
        self.string_table_offset = {}

        ast.collect_blocks(self.block_list)
        self.allocate_tag_ids()
        self.build_code_table()

    def allocate_tag_ids(self):
        tag = 0
        constant_tag = 1  # 0 is reserved for empty block {}

        for type_name in builtin_data_types:
            self.type_tag[type_name] = tag
            tag += 1
        self.first_object_id = tag

        for block in self.block_list:
            if block.is_constant:
                block.constant_tag = constant_tag
                constant_tag += 1

        for type_name in builtin_object_types:
            self.type_tag[type_name] = tag
            tag += 1

        for block in self.block_list:
            if not block.is_constant:
                block.tag = tag
                tag += 1

        self.num_tags = tag
        if tag > MAX_TAG:
            raise Error('Exhausted all tag IDs, your program is too big!')

        self.tag_constant_block = self.type_tag['Constant-Block']
        self.tag_integer = self.type_tag['Small-Integer']
        self.tag_decimal = self.type_tag['Small-Decimal']
        self.tag_string = self.type_tag['String']
        self.tag_array = self.type_tag['Array']

        #print('# Allocated %d tag IDs, %d constant tag IDs, 0-%d for data types, %d-%d for object types\n' % (
        #    self.num_tags, constant_tag, self.first_object_id - 1,
        #    self.first_object_id, self.num_tags - 1))

    def build_code_table(self):
        methods = {}
        for block in self.block_list:
            for method in block.methods:
                if method.symbol not in methods:
                    methods[method.symbol] = []
                tag = block.tag if hasattr(block, 'tag') else ((block.constant_tag << NUM_TAG_BITS) | self.tag_constant_block)
                methods[method.symbol].append((tag, method.generate_code(self)))
        for symbol in sorted(methods.keys()):
            self.code_table.append((symbol, methods[symbol]))
        methods.clear()

    def print_code_table(self):
        for symbol, methods in self.code_table:
            print('MESSAGE %s {' % symbol)
            for tag, code in methods:
                print('    TAG $%04X {' % tag)
                labels_dict = code.build_labels_dict()
                for i, instruction in enumerate(code.instructions):
                    for label in labels_dict.get(i, ()):
                        print('    %s:' % label)
                    print('        %s {%s}' % (
                        instruction, ', '.join(map(str, instruction.live_set_before))))
                for label in labels_dict.get(i + 1, ()):
                    print('    %s:' % label)
                print('    }')

            print('}')

    def print_assembly_code(self):
        print('bits 64\n')
        for symbol, methods in self.code_table:
            for tag, code in methods:
                print('; $%04X %s' % (tag, symbol))
                print('%s:' % make_call_label(tag, symbol))
                gen = CodeGenerator(self, code, Target_x86_64)
                gen.generate()
                for line in gen.output:
                    print(line)
                print()
        print('OME_data:')
        for string in self.string_table:
            print('\tdb ' + ', '.join('%d' % x for x in string))

    def allocate_string(self, string):
        if string not in self.string_table_offset:
            self.string_table_offset[string] = self.string_table_size
            padding = b'\0' * (8 - (len(string) & 7))
            data = struct.pack('I', len(string)) + string.encode('utf8') + padding
            self.string_table.append(data)
            self.string_table_size += len(data)
        return '(OME_data + %s)' % self.string_table_offset[string]

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).toplevel()

def compile_file(filename):
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(TopLevel)
    ast = ast.resolve_block_refs(TopLevel)
    program = Program(ast)
    program.print_assembly_code()

if __name__ == '__main__':
    import sys
    for filename in sys.argv[1:]:
        try:
            compile_file(filename)
        except Error as e:
            print(e)
