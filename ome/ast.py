# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .builder import MethodCodeBuilder
from .constants import *
from .error import OmeError
from .instructions import *
from .labels import *

def format_list(xs):
    return ' ' + ' '.join(str(x) for x in xs) if xs else ''

class Send(object):
    def __init__(self, receiver, symbol, args, parse_state=None):
        self.receiver = receiver
        self.symbol = symbol
        self.args = args
        self.parse_state = parse_state
        self.receiver_block = None
        self.traceback_info = None

    def __str__(self):
        args = format_list(self.args)
        return '(send %s %s%s)' % (self.symbol, self.receiver or '<free>', args)

    def error(self, message):
        if self.parse_state:
            self.parse_state.error(message)
        else:
            raise OmeError(message)

    def resolve_free_vars(self, parent):
        self.method = parent.find_method()
        for i, arg in enumerate(self.args):
            self.args[i] = arg.resolve_free_vars(parent)
        if self.receiver:
            self.receiver = self.receiver.resolve_free_vars(parent)
        else:
            if len(self.args) == 0:
                ref = parent.lookup_var(self.symbol)
                if ref:
                    return ref
            if self.symbol:
                self.receiver_block = parent.lookup_receiver(self.symbol)
                if not self.receiver_block:
                    self.error("receiver could not be resolved for '%s'" % self.symbol)
        return self

    def resolve_block_refs(self, parent):
        for i, arg in enumerate(self.args):
            self.args[i] = arg.resolve_block_refs(parent)
        if self.receiver:
            self.receiver = self.receiver.resolve_block_refs(parent)
        elif self.receiver_block:
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

    def walk(self, visitor):
        visitor(self)
        if self.receiver:
            self.receiver.walk(visitor)
        for arg in self.args:
            arg.walk(visitor)

    def generate_code(self, code):
        receiver = self.receiver.generate_code(code)
        args = [arg.generate_code(code) for arg in self.args]
        dest = code.add_temp()

        if self.receiver_block:
            label = make_method_label(self.receiver_block.tag, self.symbol)
        else:
            label = make_message_label(self.symbol)

        code.add_instruction(CALL(dest, [receiver] + args, label, self.traceback_info))
        return dest

class Concat(Send):
    def __init__(self, args, parse_state=None):
        super(Concat, self).__init__(None, '', args, parse_state)

    def generate_code(self, code):
        args = [arg.generate_code(code) for arg in self.args]
        dest = code.add_temp()
        code.add_instruction(CONCAT(dest, args, self.traceback_info))
        return dest

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

    def walk(self, visitor):
        visitor(self)
        for method in self.methods:
            method.walk(visitor)

    def generate_code(self, code):
        dest = code.add_temp()
        if self.is_constant:
            code.add_instruction(LOAD_VALUE(dest, code.get_tag('Constant'), self.tag_constant))
        else:
            code.add_instruction(ALLOC(dest, len(self.slots), self.tag))
            for index, slot in enumerate(self.slots):
                value = slot.generate_code(code)
                code.add_instruction(SET_SLOT(dest, index, value))
        return dest

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

    def walk(self, visitor):
        visitor(self)
        self.expr.walk(visitor)

    def generate_code(self, code):
        local = self.local_ref.generate_code(code)
        expr = self.expr.generate_code(code)
        code.add_instruction(ALIAS(local, expr))
        return local

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

    def walk(self, visitor):
        visitor(self)
        self.expr.walk(visitor)

    def generate_code(self, program):
        code = MethodCodeBuilder(len(self.args), len(self.locals) - len(self.args), program)
        code.add_instruction(RETURN(self.expr.generate_code(code)))
        return code.get_code()

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

    def walk(self, visitor):
        visitor(self)
        for statement in self.statements:
            statement.walk(visitor)

    def generate_code(self, code):
        for statement in self.statements[:-1]:
            statement.generate_code(code)
        return self.statements[-1].generate_code(code)

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

    def walk(self, visitor):
        visitor(self)
        for elem in self.elems:
            elem.walk(visitor)

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(ARRAY(dest, len(self.elems), code.get_tag('Array')))
        for index, elem in enumerate(self.elems):
            value = elem.generate_code(code)
            code.add_instruction(SET_ELEM(dest, index, value))
        return dest

class TerminalNode(object):
    def resolve_free_vars(self, parent):
        return self

    def resolve_block_refs(self, parent):
        return self

    def walk(self, visitor):
        visitor(self)

class Value(TerminalNode):
    def __init__(self, tag_name, value):
        self.tag_name = tag_name
        self.value = value

    def __str__(self):
        return '<value %s:%s>' % (self.tag_name, self.value)

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, code.get_tag(self.tag_name), self.value))
        return dest

class Constant(TerminalNode):
    def __init__(self, constant_name):
        self.constant_name = constant_name

    def __str__(self):
        return '<constant %s>' % (self.constant_name)

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, code.get_tag('Constant'), code.get_constant(self.constant_name)))
        return dest

EmptyBlock = Constant('Empty')

class ConstantBlock(TerminalNode):
    def __init__(self, block):
        self.block = block

    def __str__(self):
        return '<constant-block>'

    def generate_code(self, code):
        dest = code.add_temp()
        code.add_instruction(LOAD_VALUE(dest, Tag_Constant, self.block.tag_constant))
        return dest

class BuiltInMethod(object):
    def __init__(self, symbol, tag_name, sent_messages, code):
        self.symbol = symbol
        self.tag_name = tag_name
        self.sent_messages = sent_messages
        self.code = code

    def generate_target_code(self, label, target):
        return target.generate_builtin_method(label, symbol_arity(self.symbol), self.code)

class BuiltInBlock(object):
    is_constant = True
    tag = constant_to_tag(Constant_BuiltIn)
    tag_constant = Constant_BuiltIn
    constant_ref = Constant('BuiltIn')

    def __init__(self, target):
        self.symbols = {method.symbol for method in target.builtin_methods if method.tag_name == 'BuiltIn'}

    def lookup_var(self, symbol):
        pass

    def lookup_receiver(self, symbol):
        if symbol in self.symbols:
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
    'False': Value('Boolean', 0),
    'True': Value('Boolean', 1),
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

    def walk(self, visitor):
        visitor(self)
        self.obj_expr.walk(visitor)

    def generate_code(self, code):
        object = self.obj_expr.generate_code(code)
        dest = code.add_temp()
        code.add_instruction(GET_SLOT(dest, object, self.slot_index))
        return dest

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

    def walk(self, visitor):
        visitor(self)
        self.obj_expr.walk(visitor)
        self.set_expr.walk(visitor)

    def generate_code(self, code):
        object = self.obj_expr.generate_code(code)
        value = self.set_expr.generate_code(code)
        code.add_instruction(SET_SLOT(object, self.slot_index, value))
        return value

class Number(TerminalNode):
    def __init__(self, significand, exponent, parse_state):
        self.significand = significand
        self.exponent = exponent
        self.parse_state = parse_state

    def __str__(self):
        return '(number %s%s)' % (self.significand, 'e%s' % self.exponent if self.exponent else '')

    def encode_value(self, code):
        if self.exponent >= 0:
            value = self.significand * 10**self.exponent
            if MIN_SMALL_INTEGER <= value <= MAX_SMALL_INTEGER:
                return (code.get_tag('Small-Integer'), value & MASK_DATA)

        if not (MIN_EXPONENT <= self.exponent <= MAX_EXPONENT
        and MIN_SIGNIFICAND <= self.significand <= MAX_SIGNIFICAND):
            self.parse_state.error('number out of range')

        value = ((self.significand & MASK_SIGNIFICAND) << NUM_EXPONENT_BITS) | (self.exponent & MASK_EXPONENT)
        return (code.get_tag('Small-Decimal'), value)

    def generate_code(self, code):
        tag, value = self.encode_value(code)
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
        label = code.allocate_string(self.string)
        code.add_instruction(LOAD_LABEL(dest, code.get_tag('String'), label))
        return dest
