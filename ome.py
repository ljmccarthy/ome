# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re
import sys
import struct

NUM_BITS = 64
NUM_TAG_BITS = 20
NUM_DATA_BITS = NUM_BITS - NUM_TAG_BITS
NUM_EXPONENT_BITS = 8
NUM_SIGNIFICAND_BITS = NUM_DATA_BITS - NUM_EXPONENT_BITS
NUM_HEADER_USER_BITS = 32

MAX_TAG = 2**NUM_TAG_BITS - 1
MIN_INT = -2**(NUM_DATA_BITS-1)
MAX_INT = 2**(NUM_DATA_BITS-1) - 1
MIN_EXPONENT = -2**(NUM_EXPONENT_BITS-1)
MAX_EXPONENT = 2**(NUM_EXPONENT_BITS-1) - 1
MIN_SIGNIFICAND = -2**(NUM_SIGNIFICAND_BITS-1)
MAX_SIGNIFICAND = 2**(NUM_SIGNIFICAND_BITS-1) - 1
MAX_ARRAY_SIZE = 2**NUM_HEADER_USER_BITS - 1

MASK_TAG = (1 << NUM_TAG_BITS) - 1
MASK_DATA = (1 << NUM_DATA_BITS) - 1
MASK_INT = (1 << NUM_DATA_BITS) - 1
MASK_EXPONENT = (1 << NUM_EXPONENT_BITS) - 1
MASK_SIGNIFICAND = (1 << NUM_SIGNIFICAND_BITS) - 1

# Tags up to 255 are reserved for non-pointer data types
Tag_False = 0           # False is represented as all zero bits
Tag_True = 1            # True is represented as 1
Tag_Constant = 2
Tag_Small_Integer = 3
Tag_Small_Decimal = 4
Tag_String = 256
Tag_Array = 257
Tag_User = 258          # First ID for user-defined blocks
Constant_Empty = 0      # The empty block
Constant_TopLevel = 1   # Top-level block for built-ins
Constant_User = 2       # First ID for user-defined constant blocks

def constant_to_tag(constant):
    return constant + MAX_TAG + 1

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
        if len(elems) > MAX_ARRAY_SIZE:
            self.error('Array size too big.')
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
    return ' ' + ' '.join(str(x) for x in xs) if xs else ''

class Send(object):
    def __init__(self, receiver, symbol, args, parse_state=None):
        self.receiver = receiver
        self.symbol = symbol
        self.args = args
        self.parse_state = parse_state
        self.receiver_block = None

    def __str__(self):
        args = format_list(self.args)
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
                self.receiver = block.constant_ref
            else:
                self.receiver = parent.get_block_ref(block)
                # Direct slot access optimisation
                if len(self.args) == 0 and self.symbol in block.instance_vars:
                    var = block.instance_vars[self.symbol]
                    return SlotGet(self.receiver, var.slot_index, var.mutable)
                if len(self.args) == 1 and self.symbol[:-1] in block.instance_vars:
                    var = block.instance_vars[self.symbol[:-1]]
                    return SlotSet(self.receiver, var.slot_index, self.args[0])
        return self

    def collect_blocks(self, block_list):
        self.receiver.collect_blocks(block_list)
        for arg in self.args:
            arg.collect_blocks(block_list)

    def generate_code(self, code):
        receiver = self.receiver.generate_code(code)
        args = [arg.generate_code(code) for arg in self.args]
        dest = code.add_temp()

        if self.receiver_block:
            tag = get_block_tag(self.receiver_block)
            call_label = make_call_label(tag, self.symbol)
        else:
            tag = None
            call_label = make_send_label(self.symbol)

        code.add_instruction(CALL(dest, receiver, args, call_label, symbol=self.symbol, tag=tag))
        return dest

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
        return '(block%s%s)' % (args, format_list(self.methods))

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
        dest = code.add_temp()
        if hasattr(self, 'tag'):
            object = code.add_temp()
            code.add_instruction(CREATE(object, self.tag, len(self.slots)))
            for slot_index, var in enumerate(self.slots):
                arg = var.generate_code(code)
                code.add_instruction(SET_SLOT(object, slot_index, arg))
            code.add_instruction(TAG(dest, object, self.tag))
        else:
            code.add_instruction(LOAD_VALUE(dest, Tag_Constant, self.constant_tag))
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
        return '(define (%s%s) %s)' % (self.symbol, format_list(self.args), self.expr)

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

    def generate_code(self, target_type):
        code = MethodCodeBuilder(len(self.args), len(self.locals) - len(self.args))
        code.add_instruction(RETURN(self.expr.generate_code(code)))
        #print('optimising %s' % self.symbol)
        code.optimise(target_type)
        return code

class Sequence(object):
    def __init__(self, statements):
        self.statements = statements

    def __str__(self):
        return '(begin%s)' % format_list(self.statements)

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

    """
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
    """

    def generate_code(self, code):
        """Simple version with no error branching logic."""
        for statement in self.statements[:-1]:
            statement.generate_code(code)
        return self.statements[-1].generate_code(code)

    @property
    def check_error(self):
        return any(statement.check_error for statement in self.statements)

class Array(object):
    def __init__(self, elems):
        self.elems = elems

    def __str__(self):
        return '(array%s)' % format_list(self.elems)

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
        array = code.add_temp()
        dest = code.add_temp()
        code.add_instruction(CREATE_ARRAY(array, len(self.elems)))
        for i, elem in enumerate(self.elems):
            elem = elem.generate_code(code)
            code.add_instruction(SET_SLOT(array, i, elem))
        code.add_instruction(TAG(dest, array, Tag_Array))
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

class BuiltInConstantBlock(TerminalNode):
    def __init__(self, constant_tag):
        self.constant_tag = constant_tag

    def __str__(self):
        return '<builtin %s>' % self.constant_tag

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, Tag_Constant, self.constant_tag))
        return dest

class EmptyBlock(BuiltInConstantBlock):
    def __str__(self):
        return '(block)'

EmptyBlock = EmptyBlock(Constant_Empty)

class ConstantBlock(TerminalNode):
    def __init__(self, block):
        self.block = block

    def __str__(self):
        return '<constant-block>'

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, Tag_Constant, self.block.constant_tag))
        return dest

class BuiltInMethod(object):
    def __init__(self, symbol, tag, code):
        self.symbol = symbol
        self.tag = tag
        self.code = code

class TopLevelBlock(object):
    is_constant = True
    constant_ref = BuiltInConstantBlock(Constant_TopLevel)
    constant_tag = Constant_TopLevel

    def __init__(self, target_type):
        self.methods = {method.symbol: method for method in target_type.builtin_methods}

    def lookup_var(self, symbol):
        pass

    def lookup_receiver(self, symbol):
        if symbol in self.methods:
            return self

    def get_block_ref(self, block):
        pass

class Self(TerminalNode):
    def __str__(self):
        return 'self'

    def generate_code(self, code):
        return 0

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
        return self.local_index + 1

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
        untagged_object = code.add_temp()
        dest = code.add_temp()
        code.add_instruction(UNTAG(untagged_object, object))
        code.add_instruction(GET_SLOT(dest, untagged_object, self.slot_index))
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
        object = self.obj_expr.generate_code(code)
        value = self.set_expr.generate_code(code)
        untagged_object = code.add_temp()
        code.add_instruction(UNTAG(untagged_object, object))
        code.add_instruction(SET_SLOT(untagged_object, self.slot_index, value))
        return value

    check_error = True

class Number(TerminalNode):
    def __init__(self, significand, exponent, parse_state):
        self.significand = significand
        self.exponent = exponent
        self.parse_state = parse_state

    def __str__(self):
        return '(number %s%s)' % (self.significand, 'e%s' % self.exponent if self.exponent else '')

    def encode_value(self):
        if self.exponent >= 0:
            value = self.significand * 10**self.exponent
            if MIN_INT <= value <= MAX_INT:
                return (Tag_Small_Integer, value & MASK_INT)

        if not (MIN_EXPONENT <= self.exponent <= MAX_EXPONENT
        and MIN_SIGNIFICAND <= self.significand <= MAX_SIGNIFICAND):
            self.parse_state.error('Number out of range')

        value = ((self.significand & MASK_SIGNIFICAND) << NUM_EXPONENT_BITS) | (self.exponent & MASK_EXPONENT)
        return (Tag_Small_Decimal, value)

    def generate_code(self, code):
        tag, value = self.encode_value()
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

def format_instruction_args(args):
    return ' ' + ' '.join('%%%s' % x for x in args) if args else ''

class Instruction(object):
    args = ()
    label = None

    def emit(self, target):
        getattr(target, self.__class__.__name__)(self)

class CALL(Instruction):
    def __init__(self, dest, receiver, args, call_label, symbol=None, tag=None):
        self.dest = dest
        self.args = [receiver] + args
        self.call_label = call_label
        self.symbol = symbol
        self.tag = tag

    def __str__(self):
        dest = '%%%s = ' % self.dest if self.dest else ''
        return '%sCALL %s%s' % (dest, self.call_label, format_instruction_args(self.args))

class TAG(Instruction):
    def __init__(self, dest, source, tag):
        self.dest = dest
        self.args = [source]
        self.tag = tag

    def __str__(self):
        return '%%%s = TAG %%%s $%04X' % (self.dest, self.source, self.tag)

    @property
    def source(self):
        return self.args[0]

class UNTAG(Instruction):
    def __init__(self, dest, source):
        self.dest = dest
        self.args = [source]

    def __str__(self):
        return '%%%s = UNTAG %%%s' % (self.dest, self.source)

    @property
    def source(self):
        return self.args[0]

class CREATE(Instruction):
    def __init__(self, dest, tag, num_slots):
        self.dest = dest
        self.tag = tag
        self.num_slots = num_slots

    def __str__(self):
        return '%%%s = CREATE $%04X %d' % (self.dest, self.tag, self.num_slots)

class CREATE_ARRAY(Instruction):
    def __init__(self, dest, size):
        self.dest = dest
        self.size = size

    def __str__(self):
        return '%%%s = CREATE_ARRAY %s' % (self.dest, self.size)

class ALIAS(Instruction):
    def __init__(self, dest, source):
        self.dest = dest
        self.args = [source]

    def __str__(self):
        return '%%%s = %%%s' % (self.dest, self.source)

    @property
    def source(self):
        return self.args[0]

class LOAD_VALUE(Instruction):
    def __init__(self, dest, tag, value):
        self.dest = dest
        self.tag = tag
        self.value = value

    def __str__(self):
        return '%%%s = $%04X:%012X' % (self.dest, self.tag, self.value)

class LOAD_STRING(Instruction):
    def __init__(self, dest, string):
        self.dest = dest
        self.string = string

    def __str__(self):
        return "%%%s = '%s'" % (self.dest, self.string)

class GET_SLOT(Instruction):
    def __init__(self, dest, object, slot_index):
        self.dest = dest
        self.args = [object]
        self.slot_index = slot_index

    def __str__(self):
        return '%%%s = %%%s[%d]' % (self.dest, self.object, self.slot_index)

    @property
    def object(self):
        return self.args[0]

class SET_SLOT(Instruction):
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
        return '%%%s[%d] := %%%s' % (self.object, self.slot_index, self.value)

class ON_ERROR(Instruction):
    def __init__(self, label):
        self.label = label

    def __str__(self):
        return 'ON ERROR GOTO %s' % (self.label.name)

class RETURN(Instruction):
    def __init__(self, source):
        self.args = [source]

    @property
    def source(self):
        return self.args[0]

    def __str__(self):
        return 'RETURN%s' % format_instruction_args(self.args)

# SPILL, UNSPILL, MOVE, and PUSH are generated by the register allocator

class SPILL(Instruction):
    def __init__(self, register, stack_slot):
        self.register = register
        self.stack_slot = stack_slot

    def __str__(self):
        return 'stack[%d] := %%%s' % (self.stack_slot, self.register)

class UNSPILL(Instruction):
    def __init__(self, register, stack_slot):
        self.register = register
        self.stack_slot = stack_slot

    def __str__(self):
        return '%%%s := stack[%d]' % (self.register, self.stack_slot)

class MOVE(Instruction):
    def __init__(self, dest_reg, source_reg):
        self.dest_reg = dest_reg
        self.source_reg = source_reg

    def __str__(self):
        return '%%%s := %%%s' % (self.dest_reg, self.source_reg)

class PUSH(Instruction):
    def __init__(self, source_reg):
        self.source_reg = source_reg

    def __str__(self):
        return 'PUSH %%%s' % self.source_reg

def apply_labels_to_instructions(instructions, labels):
    labels = {label.location: label.name for label in labels}
    for loc, ins in enumerate(instructions):
        if loc in labels:
            ins.label = labels[loc]

def eliminate_aliases(instructions):
    """Eliminate all local variable aliases (i.e. ALIAS instructions)."""

    aliases = {}
    instructions_out = []

    for location, ins in enumerate(instructions):
        if isinstance(ins, ALIAS):
            aliases[ins.dest] = aliases.get(ins.source, ins.source)
        else:
            for i, arg in enumerate(ins.args):
                if arg in aliases:
                    ins.args[i] = aliases[arg]
            instructions_out.append(ins)

    return instructions_out

def move_constants_to_usage_points(instructions, num_locals):
    """
    Remove LOAD_VALUE/LOAD_STRING instructions and re-inserts loading to a
    new local just before they are needed. This reduces the size of the live
    set since it is only needed for an instance and can be re-loaded again
    as needed.
    """

    instructions_out = []
    constant_values = {}
    constant_strings = {}

    for ins in instructions:
        if isinstance(ins, LOAD_VALUE):
            constant_values[ins.dest] = ins
        elif isinstance(ins, LOAD_STRING):
            constant_strings[ins.dest] = ins
        else:
            for i, arg in enumerate(ins.args):
                if arg in constant_values:
                    cins = constant_values[arg]
                    instructions_out.append(LOAD_VALUE(num_locals, cins.tag, cins.value))
                    ins.args[i] = num_locals
                    num_locals += 1
                elif arg in constant_strings:
                    cins = constant_strings[arg]
                    instructions_out.append(LOAD_STRING(num_locals, cins.string))
                    ins.args[i] = num_locals
                    num_locals += 1
            instructions_out.append(ins)

    return instructions_out

def eliminate_redundant_untags(instructions):
    instructions_out = []
    untagged_locals = {}
    untagged_local_aliases = {}

    for ins in instructions:
        if isinstance(ins, UNTAG):
            if ins.source not in untagged_locals:
                untagged_locals[ins.source] = ins.dest
                untagged_local_aliases[ins.dest] = ins.dest
                instructions_out.append(ins)
            else:
                untagged_local_aliases[ins.dest] = untagged_locals[ins.source]
        else:
            for i, arg in enumerate(ins.args):
                if arg in untagged_local_aliases:
                    ins.args[i] = untagged_local_aliases[arg]
            instructions_out.append(ins)

    return instructions_out

def renumber_locals(instructions, num_args):
    """Renumbers locals in the order of creation without any gaps."""

    locals_map = {i: i for i in range(num_args)}

    for ins in instructions:
        for i, arg in enumerate(ins.args):
            ins.args[i] = locals_map[arg]
        if hasattr(ins, 'dest'):
            assert ins.dest not in locals_map
            new_dest = len(locals_map)
            locals_map[ins.dest] = new_dest
            ins.dest = new_dest

    return len(locals_map)

def find_local_usage_points(instructions, num_args):
    usage_points = {i: [] for i in range(num_args)}
    for loc, ins in enumerate(instructions):
        if hasattr(ins, 'dest'):
            usage_points[ins.dest] = [loc]
        for local in ins.args:
            usage_points[local].append(loc)
    return usage_points

def find_usage_distances(instructions, num_args):
    """
    For each instruction, find the the distance to the next use of each local
    variable in the live set.
    """
    usage_distances = []
    current_distance = {}
    created_point = {}

    for loc, ins in reversed(list(enumerate(instructions))):
        used_here = set(ins.args)
        if hasattr(ins, 'dest'):
            used_here.add(ins.dest)
            created_point[ins.dest] = loc
        not_used_here = set(current_distance.keys()) - used_here
        for local in used_here:
            current_distance[local] = 0
        for local in not_used_here:
            current_distance[local] += 1
        usage_distances.append(current_distance.copy())

    usage_distances.reverse()
    for local, created_loc in created_point.items():
        for loc in range(created_loc):
            del usage_distances[loc][local]

    # Add usage distance to instruction objects
    for loc, ins in enumerate(instructions):
        ins.usage_distance = usage_distances[loc]

    return usage_distances

def get_call_registers(call_ins, arg_regs):
    """
    Returns a dict mapping locals to registers for each register used
    to pass arguments to the call instruction.
    """
    return {call_ins.args[i]: arg_regs[i]
            for i in range(min(len(call_ins.args), len(arg_regs)))}

def get_call_ranges(instructions):
    call_ranges = []
    start = 0
    for loc, ins in enumerate(instructions):
        if isinstance(ins, CALL):
            call_ranges.append((start, loc))
            start = loc + 1
    return call_ranges, start

class LocalStorage(object):
    def __init__(self, num_args, target):
        self.arg_regs = target.arg_registers
        self.temp_regs = target.temp_registers
        self.return_reg = target.return_register

        self.local_register = {i: self.arg_regs[i] for i in range(min(num_args, len(self.arg_regs)))}
        self.register_local = {self.arg_regs[i]: i for i in range(min(num_args, len(self.arg_regs)))}
        self.free_registers = list(self.arg_regs[num_args:] + self.temp_regs)

        # Stack slots are negatively indexed from the position of the first argument
        # The real offset is computed by subtracting from the maximum frame size
        #
        # | loc1 | 5  0  num_stack_slots = 6
        # | loc0 | 4  1
        # | retn | 3  -
        # | arg0 | 2  3
        # | arg1 | 1  4
        # | arg2 | 0  5

        self.local_stack = {i: num_args - i - 1 for i in range(len(self.arg_regs), num_args)}
        self.free_stack_slots = []
        self.stack_offset = len(self.local_stack) + 1  # One slot for return address after args
        self.num_stack_slots = 0

        self.spills = []

    def get_local_register(self, local):
        return self.local_register[local]

    def remove_local_from_register(self, local):
        if local in self.local_register:
            reg = self.local_register[local]
            del self.local_register[local]
            del self.register_local[reg]
            self.free_registers.append(reg)
            return reg

    def remove_local_from_stack(self, local):
        if local in self.local_stack:
            slot = self.local_stack[local]
            del self.local_stack[local]
            self.free_stack_slots.append(slot)
            return slot

    def remove_inactive_locals(self, active_locals):
        active_locals = frozenset(active_locals)
        locals_using_regs = frozenset(self.local_register.keys())
        locals_using_stack = frozenset(self.local_stack.keys())
        reg_locals_to_free = sorted(locals_using_regs - active_locals)
        stack_locals_to_free = sorted(locals_using_stack - active_locals)

        for local in reg_locals_to_free:
            self.remove_local_from_register(local)

        for local in stack_locals_to_free:
            self.remove_local_from_stack(local)

    def get_stack_slot(self, local):
        if local in self.local_stack:
            stack_slot = self.local_stack[local]
        elif self.free_stack_slots:
            stack_slot = self.free_stack_slots.pop()
            self.local_stack[local] = stack_slot
        else:
            stack_slot = self.stack_offset
            self.stack_offset += 1
            self.num_stack_slots += 1
            self.local_stack[local] = stack_slot
        return stack_slot

    def move_local_to_register(self, local, new_reg):
        old_reg = self.local_register[local]
        del self.register_local[old_reg]
        self.local_register[local] = new_reg
        self.register_local[new_reg] = local
        if new_reg in self.free_registers:
            self.free_registers.remove(new_reg)
        if old_reg not in self.free_registers:
            self.free_registers.append(old_reg)
        self.spills.append(MOVE(new_reg, old_reg))
        return old_reg

    def spill(self, local):
        if local in self.local_stack:
            return self.local_stack[local]
        else:
            stack_slot = self.get_stack_slot(local)
            self.spills.append(SPILL(self.local_register[local], stack_slot))
            return stack_slot

    def unspill(self, local, reg):
        assert local not in self.local_register
        self.local_register[local] = reg
        self.register_local[reg] = local
        if reg in self.free_registers:
            self.free_registers.remove(reg)
        if local in self.local_stack:
            self.spills.append(UNSPILL(reg, self.local_stack[local]))

    def get_spills(self):
        spills = self.spills
        self.spills = []
        return spills

    def move_to_free_register_or_spill(self, local):
        if self.free_registers:
            self.move_local_to_register(local, self.free_registers.pop())
        else:
            self.spill(local)

    def find_lowest_priority_register(self, reg_priority):
        """
        Find the register containing the lowest priority local (i.e. largest
        distance to next use.
        """
        max_priority = -1
        lowest_priority_reg = None
        for local, reg in self.local_register.items():
            if reg_priority[local] > max_priority:
                max_priority = reg_priority[local]
                lowest_priority_reg = reg
        return lowest_priority_reg

    def get_local_to_any_register(self, local, reg_priority):
        if local in self.local_register:
            return self.local_register[local]
        if self.free_registers:
            reg = self.free_registers.pop()
        else:
            reg = self.find_lowest_priority_register(reg_priority)
            self.spill(self.local_register[reg])
        self.unspill(local, reg)
        return reg

    def get_local_to_register(self, local, preferred_regs, reg_priority):
        if local not in self.local_register:
            if local not in preferred_regs:
                self.get_local_to_any_register(local, reg_priority)
            else:
                preferred_reg = preferred_regs[local]
                if preferred_reg not in self.register_local:
                    self.unspill(local, preferred_reg)
                else:
                    self.get_local_to_any_register(local, reg_priority)
        return self.local_register[local]

    def prepare_call(self, call_ins, after_call_ins):
        self.remove_inactive_locals(call_ins.usage_distance.keys())

        # Spill all locals needed after the call
        for local in list(self.local_register.keys()):
            if local in after_call_ins.usage_distance:
                self.spill(local)
                if local not in call_ins.args:
                    self.remove_local_from_register(local)

        # Shuffle argument to correct registers
        for i, arg in enumerate(call_ins.args[:len(self.arg_regs)]):
            if self.arg_regs[i] in self.register_local:
                local_in_arg_reg = self.register_local[self.arg_regs[i]]
                if local_in_arg_reg != arg and local_in_arg_reg in call_ins.args:
                    self.move_to_free_register_or_spill(local_in_arg_reg)
            if arg in self.local_register:
                if self.local_register[arg] != self.arg_regs[i]:
                    self.move_local_to_register(arg, self.arg_regs[i])
            else:
                self.unspill(arg, self.arg_regs[i])

        # Push stack arguments
        for arg in call_ins.args[len(self.arg_regs):]:
            reg = self.get_local_to_any_register(arg, {})
            self.spills.append(PUSH(reg))
            self.remove_local_from_register(arg)

        self.local_register = {call_ins.dest: self.return_reg}
        self.register_local = {self.return_reg: call_ins.dest}
        self.free_registers = list(self.arg_regs + self.temp_regs)

        call_ins.num_stack_args = max(0, len(call_ins.args) - len(self.arg_regs))

    def prepare_return(self):
        self.free_registers = list(self.arg_regs + self.temp_regs)

    def move_to_return_register(self, local):
        if local not in self.local_register:
            self.unspill(local, self.return_reg)
        elif self.local_register[local] != self.return_reg:
            self.spills.append(MOVE(self.return_reg, self.local_register[local]))

    def adjust_stack_offsets(self, instructions):
        # Fix up stack offsets to be relative to stack pointer
        stack_adjust = self.stack_offset - 1
        for ins in instructions:
            if isinstance(ins, (SPILL, UNSPILL)):
                ins.stack_slot = stack_adjust - ins.stack_slot
            elif isinstance(ins, PUSH):
                stack_adjust += 1
            elif isinstance(ins, CALL):
                stack_adjust = self.stack_offset - 1

def allocate_registers(instructions, num_args, target):
    locals = LocalStorage(num_args, target)
    usage_distances = find_usage_distances(instructions, num_args)
    instructions_out = []

    def process_instruction(ins, next_ins, preferred_regs):
        locals.remove_inactive_locals(ins.usage_distance.keys())
        #if isinstance(ins, (TAG, UNTAG)) and ins.source not in next_ins.usage_distance:
        #    ins.dest = ins.source
        if hasattr(ins, 'dest'):
            locals.get_local_to_register(ins.dest, preferred_regs, ins.usage_distance)
        for arg in ins.args:
            locals.get_local_to_register(arg, preferred_regs, ins.usage_distance)
        for i, arg in enumerate(ins.args):
            ins.args[i] = locals.get_local_register(arg)
        if hasattr(ins, 'dest'):
            ins.dest = locals.get_local_register(ins.dest)
        instructions_out.extend(locals.get_spills())
        instructions_out.append(ins)

    call_ranges, tail = get_call_ranges(instructions)

    for start, end in call_ranges:
        next_call_ins = instructions[end]
        preferred_regs = get_call_registers(next_call_ins, target.arg_registers)

        for i in range(start, end):
            process_instruction(instructions[i], instructions[i+1], preferred_regs)

        locals.prepare_call(next_call_ins, instructions[end + 1])
        instructions_out.extend(locals.get_spills())

        next_call_ins.dest = None
        next_call_ins.args = []
        instructions_out.append(next_call_ins)

    return_ins = instructions[-1]
    preferred_regs = {return_ins.source: target.return_register}
    locals.prepare_return()

    for i in range(tail, len(instructions)-1):
        process_instruction(instructions[i], instructions[i+1], preferred_regs)

    locals.move_to_return_register(return_ins.source)
    instructions_out.extend(locals.get_spills())
    locals.adjust_stack_offsets(instructions_out)

    return instructions_out, locals.num_stack_slots

class Label(object):
    def __init__(self, name, location):
        self.name = name
        self.location = location

class MethodCodeBuilder(object):
    def __init__(self, num_args, num_locals):
        self.num_args = num_args + 1  # self is arg 0
        self.num_locals = num_args + num_locals + 1
        self.instructions = []
        self.labels = []
        self.dest = self.add_temp()

    def add_temp(self):
        local = self.num_locals
        self.num_locals += 1
        return local

    def here(self):
        return len(self.instructions)

    def add_label(self):
        label = Label('.L%d' % len(self.labels), self.here())
        self.labels.append(label)
        return label

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def optimise(self, target_type):
        apply_labels_to_instructions(self.instructions, self.labels)
        self.instructions = eliminate_aliases(self.instructions)
        self.instructions = move_constants_to_usage_points(self.instructions, self.num_locals)
        self.instructions = eliminate_redundant_untags(self.instructions)
        self.num_locals = renumber_locals(self.instructions, self.num_args)
        self.instructions, self.num_stack_slots = allocate_registers(self.instructions, self.num_args, target_type)

class CodeEmitter(object):
    def __init__(self):
        self.output = []

    def __call__(self, format, *args):
        self.output.append('\t' + format % args)

    def label(self, name):
        self.output.append('%s:' % name)

    def comment(self, format, *args):
        self.output.append('\t; ' + format % args)

class ProcedureCodeEmitter(CodeEmitter):
    def __init__(self, label):
        self.header_output = []
        self.prelude_output = [label + ':']
        self.output = []
        self.tail_emitters = []

    def header_comment(self, format, *args):
        self.header_output.append('; ' + format % args)

    def prelude(self, format, *args):
        self.prelude_output.append('\t' + format % args)

    def tail_emitter(self, label):
        emitter = CodeEmitter()
        emitter.label(label)
        self.tail_emitters.append(emitter)
        return emitter

    def get_output(self):
        lines = self.header_output[:]
        lines.extend(self.prelude_output)
        lines.extend(self.output)
        for emitter in self.tail_emitters:
            lines.extend(emitter.output)
        lines.append('')
        return '\n'.join(lines)

def generate_assembly_code(emit, code, target_type, data_table):
    target = target_type(emit)
    target.emit_enter(code.num_stack_slots)
    for ins in code.instructions:
        if isinstance(ins, LOAD_STRING):
            ins.data_label = data_table.allocate_string(ins.string)
        ins.emit(target)
    target.emit_leave(code.num_stack_slots)

def split_tag_range(target, label_format, tags, exit_label, min_tag, max_tag):
    target.emit.comment('[0x%x..0x%x]', min_tag, max_tag)
    if len(tags) == 1:
        tag = tags[0]
        if min_tag == tag and max_tag == tag:
            target.emit_jump(label_format % tag)
        else:
            target.emit_dispatch_compare_eq(tag, label_format % tag, exit_label)
    else:
        middle = len(tags) // 2
        middle_label = '.tag_ge_%X' % tags[middle]
        target.emit_dispatch_compare_gte(tags[middle], middle_label)
        split_tag_range(target, label_format, tags[:middle], exit_label, min_tag, tags[middle] - 1)
        target.emit.label(middle_label)
        split_tag_range(target, label_format, tags[middle:], exit_label, tags[middle], max_tag)

def generate_dispatcher(symbol, tags, target_type):
    tags = sorted(tags)
    any_constant_tags = any(tag > MAX_TAG for tag in tags)
    emit = ProcedureCodeEmitter(make_send_label(symbol))
    target = target_type(emit)
    target.emit_dispatch(any_constant_tags)
    split_tag_range(target, make_call_label_format(symbol), tags, '.not_understood', 0, 1 << NUM_DATA_BITS)
    return emit.get_output()

def encode_tagged_value(value, tag):
    assert (value & MASK_DATA) == value
    assert (tag & MASK_TAG) == tag
    return (tag << NUM_DATA_BITS) | value

class Target_x86_64(object):
    stack_pointer = 'rsp'
    context_pointer = 'rbp'
    nursery_bump_pointer = 'rbx'
    nursery_limit_pointer = 'r12'
    arg_registers = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
    return_register = 'rax'
    temp_registers = ('r10', 'r11')

    def __init__(self, emitter):
        self.emit = emitter
        self.num_jumpback_labels = 0

    def emit_enter(self, num_stack_slots):
        if num_stack_slots > 0:
            self.emit('sub rsp, %s', num_stack_slots * 8)

    def emit_leave(self, num_stack_slots):
        if num_stack_slots > 0:
            self.emit('add rsp, %s', num_stack_slots * 8)
        self.emit('ret')

    def emit_dispatch(self, any_constant_tags):
        self.emit('mov rax, %s', self.arg_registers[0])
        self.emit('shr rax, %s', NUM_DATA_BITS)
        if any_constant_tags:
            self.emit('cmp rax, %s', Tag_Constant)
            self.emit('je .constant')
        self.emit.label('.dispatch')
        if any_constant_tags:
            const_emit = self.emit.tail_emitter('.constant')
            const_emit('xor rax, rax')
            const_emit('mov eax, edi')
            const_emit('add rax, 0x%x', 1 << NUM_TAG_BITS)
            const_emit('jmp .dispatch')
        not_understood_emit = self.emit.tail_emitter('.not_understood')
        not_understood_emit('jmp OME_not_understood')

    def emit_dispatch_compare_eq(self, tag, tag_label, exit_label):
        self.emit('cmp rax, 0x%X', tag)
        self.emit('jne %s', exit_label)
        self.emit('jmp %s', tag_label)

    def emit_dispatch_compare_gte(self, tag, gt_label):
        self.emit('cmp rax, 0x%X', tag)
        self.emit('jae %s', gt_label)

    def emit_jump(self, label):
        self.emit('jmp %s', label)

    def MOVE(self, ins):
        self.emit('mov %s, %s', ins.dest_reg, ins.source_reg)

    def SPILL(self, ins):
        self.emit('mov [rsp+%s], %s', ins.stack_slot * 8, ins.register)

    def UNSPILL(self, ins):
        self.emit('mov %s, [rsp+%s]', ins.register, ins.stack_slot * 8)

    def PUSH(self, ins):
        self.emit('push %s', ins.source_reg)

    def CALL(self, ins):
        self.emit('call %s', ins.call_label)
        if ins.num_stack_args > 0:
            self.emit('add rsp, %s', ins.num_stack_args * 8)

    def emit_tag(self, reg, tag):
        self.emit('shl %s, %s', reg, NUM_TAG_BITS - 3)
        self.emit('or %s, %s', reg, tag)
        self.emit('ror %s, %s', reg, NUM_TAG_BITS)

    def TAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit_tag(ins.dest, ins.tag)

    def UNTAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit('shl %s, %s', ins.dest, NUM_TAG_BITS)
        self.emit('shr %s, %s', ins.dest, NUM_TAG_BITS - 3)

    def LOAD_VALUE(self, ins):
        value = encode_tagged_value(ins.value, ins.tag)
        self.emit('mov %s, 0x%x', ins.dest, value)

    def LOAD_STRING(self, ins):
        self.emit('lea %s, [rel %s]', ins.dest, ins.data_label)
        self.emit_tag(ins.dest, Tag_String)

    def GET_SLOT(self, ins):
        self.emit('mov %s, [%s+%s]', ins.dest, ins.object, ins.slot_index * 8)

    def SET_SLOT(self, ins):
        self.emit('mov [%s+%s], %s', ins.object, ins.slot_index * 8, ins.value)

    def emit_create(self, dest, num_slots):
        return_label = '.gc_return_%d' % self.num_jumpback_labels
        full_label = '.gc_full_%d' % self.num_jumpback_labels
        self.num_jumpback_labels += 1

        self.emit.label(return_label)
        self.emit('mov %s, %s', dest, self.nursery_bump_pointer)
        self.emit('add %s, %s', self.nursery_bump_pointer, (num_slots + 1) * 8)
        self.emit('cmp %s, %s', self.nursery_bump_pointer, self.nursery_limit_pointer)
        self.emit('jae %s', full_label)

        tail_emit = self.emit.tail_emitter(full_label)
        tail_emit('call OME_collect_nursery')
        tail_emit('jmp %s', return_label)

    def CREATE(self, ins):
        self.emit_create(ins.dest, ins.num_slots)

    def CREATE_ARRAY(self, ins):
        self.emit_create(ins.dest, ins.size)
        self.emit('mov dword [%s-4], %s', ins.dest, ins.size)

    builtin_code = '''\
%define OME_NUM_TAG_BITS {NUM_TAG_BITS}
%define OME_NUM_DATA_BITS {NUM_DATA_BITS}
%define OME_Value(value, tag) (((tag) << OME_NUM_DATA_BITS) | (value))
%define OME_Constant(value) OME_Value(value, OME_Tag_Constant)

%define OME_Tag_Constant 2
%define OME_Tag_String 256
%define OME_Constant_TopLevel 1
%define OME_Constant_TypeError 2

%define SYS_write 1
%define SYS_mmap 9
%define SYS_mprotect 10
%define SYS_munmap 11
%define SYS_mremap 25
%define SYS_exit 60

%define MAP_PRIVATE 0x2
%define MAP_ANONYMOUS 0x20

%define PROT_READ 0x1
%define PROT_WRITE 0x2
%define PROT_EXEC 0x4

global _start
_start:
	call OME_allocate_thread_context
	lea rsp, [rax+0x2000]  ; stack pointer (grows down)
	mov rbx, rsp           ; GC nursery pointer (grows up)
	lea r12, [rax+0x9000]  ; GC nursery limit
	call OME_toplevel
	mov rdi, rax
	call {MAIN}
	xor rdi, rdi
	test rax, rax
	jns .success
	inc rdi
.success:
	mov rax, SYS_exit
	syscall

OME_allocate_thread_context:
	mov rax, SYS_mmap
	xor rdi, rdi	  ; addr
	mov rsi, 0xA000   ; size
	xor rdx, rdx	  ; PROT_NONE
	mov r10, MAP_PRIVATE|MAP_ANONYMOUS
	mov r8, r8
	dec r8
	xor r9, r9
	syscall
	lea rdi, [rax + 0x1000]  ; save pointer returned by mmap
	push rdi
	shr rax, 47   ; test for MAP_FAILED or address that is too big
	jnz .panic
	mov rax, SYS_mprotect
	mov rsi, 0x8000
	mov rdx, PROT_READ|PROT_WRITE
	syscall
	test rax, rax
	js .panic
	pop rax
	ret
.panic:
	mov rsi, OME_message_mmap_failed
	mov rdx, OME_message_mmap_failed.size
	jmp OME_panic

OME_collect_nursery:
	lea rsi, [rel OME_message_collect_nursery]
	mov rdx, OME_message_collect_nursery.size
OME_panic:
	mov rax, SYS_write
	mov rdi, 2
	syscall
	mov rax, SYS_exit
	mov rdi, 1
	syscall

OME_not_understood:
	lea rsi, [rel OME_message_not_understood]
	mov rdx, OME_message_not_understood.size
	jmp OME_panic

'''

    builtin_data = '''\
OME_message_mmap_failed
.str:
	db "Failed to allocate thread context", 10
.size equ $-.str

OME_message_collect_nursery:
.str:
	db "Garbage collector called", 10
.size equ $-.str

OME_message_not_understood:
.str:
	db "Message not understood", 10
.size equ $-.str
'''

    builtin_methods = [
        BuiltInMethod('print:', constant_to_tag(Constant_TopLevel), '''\
	mov rax, rsi
	shr rax, OME_NUM_DATA_BITS
	cmp rax, OME_Tag_String
	jne .type_error
	shl rsi, OME_NUM_TAG_BITS
	shr rsi, OME_NUM_TAG_BITS - 3
	mov rdx, [rsi]
	add rsi, 8
	mov rax, SYS_write
	mov rdi, 1
	syscall
	sub rsp, 8
	mov [rsp], byte 10
	mov rsi, rsp
	mov rdx, 1
	mov rax, SYS_write
	mov rdi, 1
	syscall
	add rsp, 8
	ret
.type_error:
	mov rax, OME_Constant(OME_Constant_TypeError)
	ret
'''),
    ]

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

def make_call_label_format(symbol):
    return 'OME_method_%X_' + symbol_to_label(symbol)

def make_call_label(tag, symbol):
    return make_call_label_format(symbol) % tag

def get_block_tag(block):
    if hasattr(block, 'tag'):
        return block.tag
    else:
        return constant_to_tag(block.constant_tag)

class DataTable(object):
    def __init__(self):
        self.size = 0
        self.data = []
        self.string_offsets = {}

    def append_data(self, data):
        offset = self.size
        self.data.append(data)
        self.size += len(data)
        return offset

    def allocate_string(self, string):
        if string not in self.string_offsets:
            padding = b'\0' * (8 - (len(string) & 7))  # nul termination padding
            data = struct.pack('Q', len(string)) + string.encode('utf8') + padding
            self.string_offsets[string] = self.append_data(data)
        return '(OME_data+%s)' % self.string_offsets[string]

    def generate_assembly(self, f):
        f.write('align 8\nOME_data:\n')
        for data in self.data:
             f.write('\tdb ' + ','.join('%d' % byte for byte in data) + '\n')
        f.write('.end:\n')

class Program(object):
    def __init__(self, ast, target_type):
        self.toplevel_method = ast
        self.toplevel_block = ast.expr
        if isinstance(self.toplevel_block, Sequence):
            self.toplevel_block = self.toplevel_block.statements[-1]

        self.target_type = target_type
        self.block_list = []
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = DataTable()

        if 'main' not in self.toplevel_block.symbols:
            raise Error('Error: No main method defined')

        ast.collect_blocks(self.block_list)
        self.allocate_tag_ids()
        self.allocate_constant_tag_ids()
        self.build_code_table()

    def allocate_tag_ids(self):
        tag = Tag_User
        for block in self.block_list:
            if not block.is_constant:
                block.tag = tag
                tag += 1
        if tag > MAX_TAG:
            raise Error('Exhausted all tag IDs, your program is too big!')

    def allocate_constant_tag_ids(self):
        constant_tag = Constant_User
        for block in self.block_list:
            if block.is_constant:
                block.constant_tag = constant_tag
                constant_tag += 1

    def _compile_method(self, method, label):
        emit = ProcedureCodeEmitter(label)
        code = method.generate_code(self.target_type)
        generate_assembly_code(emit, code, self.target_type, self.data_table)
        return emit.get_output()

    def compile_method(self, method, tag):
        return self._compile_method(method, make_call_label(tag, method.symbol))

    def build_code_table(self):
        methods = {}
        for method in self.target_type.builtin_methods:
            if method.symbol not in methods:
                methods[method.symbol] = []
            label = make_call_label(method.tag, method.symbol)
            code = '%s:\n%s' % (label, method.code)
            methods[method.symbol].append((method.tag, code))

        for block in self.block_list:
            for method in block.methods:
                if method.symbol not in methods:
                    methods[method.symbol] = []
                tag = get_block_tag(block)
                code = self.compile_method(method, tag)
                methods[method.symbol].append((tag, code))

        for symbol in sorted(methods.keys()):
            self.code_table.append((symbol, methods[symbol]))
        methods.clear()

    def print_code_table(self):
        for symbol, methods in self.code_table:
            print('MESSAGE %s {' % symbol)
            for tag, code in methods:
                print('    TAG $%X {' % tag)
                for i, instruction in enumerate(code.instructions):
                    if instruction.label:
                        print('    .%s:' % instruction.label)
                    print('        %s' % instruction)
                print('    }')
            print('}')

    def generate_assembly(self, f):
        f.write('bits 64\n\nsection .text\n\n')

        main_label = make_call_label(get_block_tag(self.toplevel_block), 'main')
        env = {
            'MAIN': main_label,
            'NUM_TAG_BITS': NUM_TAG_BITS,
            'NUM_DATA_BITS': NUM_DATA_BITS,
        }      
        f.write(self.target_type.builtin_code.format(**env))
        f.write(self._compile_method(self.toplevel_method, 'OME_toplevel'))
        f.write('\n')

        for symbol, methods in self.code_table:
            tags = [tag for tag, code in methods]
            f.write(generate_dispatcher(symbol, tags, self.target_type))
            f.write('\n')
            for tag, code in methods:
                f.write(code)
                f.write('\n')

        f.write('section .rodata\n\n')
        self.data_table.generate_assembly(f)
        f.write('\n')
        f.write(self.target_type.builtin_data)

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).toplevel()

def compile_file(filename, target_type=Target_x86_64):
    toplevel = TopLevelBlock(target_type)
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(toplevel)
    ast = ast.resolve_block_refs(toplevel)
    program = Program(ast, target_type)
    #program.print_code_table()
    program.generate_assembly(sys.stdout)

def main():
    for filename in sys.argv[1:]:
        try:
            compile_file(filename)
        except Error as e:
            sys.stderr.write('%s\n' % e)

if __name__ == '__main__':
    main()
