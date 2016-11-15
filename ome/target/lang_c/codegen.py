# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import struct
from ... import optimise
from ...constants import MIN_CONSTANT_TAG
from ...instructions import CONCAT
from ...symbol import symbol_to_label, symbol_arity
from .cstring import literal_c_string
from .stackalloc import allocate_stack_slots

encoding = 'ascii'
comment_format = '// {}'
define_label_format = '{}:'
indent = '    '

def make_message_label(symbol):
    return 'OME_message_' + symbol_to_label(symbol)

def make_default_label(symbol):
    return 'OME_default_' + symbol_to_label(symbol)

def make_lookup_label(symbol):
    return 'OME_lookup_' + symbol_to_label(symbol)

def make_method_label(tag, symbol):
    return 'OME_method_{}_{}'.format(tag, symbol_to_label(symbol))

def literal_integer(value):
    return '{}{}'.format(value, '' if -0x80000000 <= value <= 0x7fffffff else 'L')

def format_function_definition_with_arg_names(name, argnames):
    return 'static OME_Value {}({})'.format(name, ', '.join('OME_Value {}'.format(arg) for arg in argnames))

def format_function_definition(name, num_args):
    return format_function_definition_with_arg_names(name, ('_{}'.format(n) for n in range(num_args)))

def format_function_declaration(name, num_args):
    return 'static OME_Value {}({})'.format(name, ', '.join('OME_Value' for n in range(num_args)))

def format_dispatch_call(name, num_args):
    return '{}({})'.format(name, ', '.join('_{}'.format(n) for n in range(num_args)))

class ProcedureCodegen(object):
    def __init__(self, emitter):
        self.emit = emitter

    def optimise(self, code):
        code.instructions = optimise.eliminate_aliases(code.instructions)
        code.instructions = optimise.move_constants_to_usage_points(code.instructions, code.num_args)
        optimise.renumber_locals(code.instructions, code.num_args)
        optimise.find_live_sets(code.instructions)
        self.is_leaf = all(ins.is_leaf for ins in code.instructions)
        if not self.is_leaf:
            self.stack_size = allocate_stack_slots(code.instructions, code.num_args)
        else:
            self.stack_size = 0
        self.has_stack = self.stack_size > 0 or any(isinstance(ins, CONCAT) for ins in code.instructions)

    def begin(self, name, num_args):
        self.emit(format_function_definition(name, num_args))
        self.emit('{')
        self.emit.indent()
        if self.has_stack:
            self.emit('OME_Value * const _stack = OME_context->stack_pointer;')
            if self.stack_size > 0:
                self.emit('if (&_stack[{}] >= OME_context->stack_limit) {{'.format(self.stack_size + 1))
                with self.emit.indented():
                    self.emit('return OME_error(OME_Stack_Overflow);')
                self.emit('}')
                self.emit('OME_context->stack_pointer = &_stack[{}];'.format(self.stack_size))

    def end(self):
        self.emit.dedent()
        self.emit.end('}')

    def emit_load_list(self, ins):
        for local, slot in ins.load_list:
            self.emit('_{} = _stack[{}];'.format(local, slot))

    def emit_save_list(self, ins):
        for local, slot in ins.save_list:
            self.emit('_stack[{}] = _{};'.format(slot, local))
        for slot in ins.clear_list:
            self.emit('_stack[{}] = OME_False;'.format(slot))

    def emit_return(self, ret):
        if self.stack_size > 0:
            self.emit('OME_context->stack_pointer = _stack;')
        self.emit('return {};'.format(ret))

    def emit_append_traceback(self, traceback_info):
        if traceback_info:
            self.emit('OME_append_traceback({});'.format(traceback_info.index))

    def emit_error_check(self, error, traceback_info=None):
        self.emit('if (OME_is_error(_{})) {{'.format(error))
        with self.emit.indented():
            self.emit_append_traceback(traceback_info)
            self.emit_return('_{}'.format(error))
        self.emit('}')

    def BEGIN_COMPARE(self, ins):
        self.emit('if (OME_equal(_0, _1)) {')
        with self.emit.indented():
            self.emit_return('OME_Equal')
        self.emit('}')
        self.emit('if (OME_get_tag(_1) != {}) {{'.format(ins.tag))
        with self.emit.indented():
            self.emit_return('OME_error(OME_Type_Error)')
        self.emit('}')

    def BEGIN_EQUALS(self, ins):
        self.emit('if (OME_equal(_0, _1)) {')
        with self.emit.indented():
            self.emit_return('OME_True')
        self.emit('}')
        self.emit('if (OME_get_tag(_1) != {}) {{'.format(ins.tag))
        with self.emit.indented():
            self.emit_return('OME_False')
        self.emit('}')

    def LOAD_VALUE(self, ins):
        self.emit('const OME_Value _{} = OME_tag_unsigned({}, {});'.format(ins.dest, ins.tag, ins.value))

    def LOAD_LABEL(self, ins):
        self.emit('const OME_Value _{} = OME_tag_pointer({}, {});'.format(ins.dest, ins.tag, ins.label))

    def ALLOC(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = OME_tag_pointer({}, OME_allocate_slots({}));'.format(ins.dest, ins.tag, ins.size))

    def ARRAY(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = OME_tag_pointer({}, OME_allocate_array({}));'.format(ins.dest, ins.tag, ins.size));

    def CALL(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        if ins.check_tag is not None:
            self.emit('{')
            with self.emit.indented():
                self.emit('OME_Tag _tag = OME_get_tag(_{});'.format(ins.args[0]))
                if ins.check_tag >= MIN_CONSTANT_TAG:
                    self.emit('if (_tag == OME_Tag_Constant) {{ _tag = OME_untag_unsigned(_{}) + OME_MIN_CONSTANT_TAG; }}'.format(ins.args[0]))
                self.emit('if (_tag != {}) {{'.format(ins.check_tag))
                with self.emit.indented():
                    self.emit_append_traceback(ins.traceback_info)
                    self.emit_return('OME_error(OME_Type_Error)')
                self.emit('}')
            self.emit('}')
        self.emit('OME_Value _{} = {}({});'.format(
            ins.dest,
            ins.call_label,
            ', '.join('_{}'.format(x) for x in ins.args)))
        if ins.check_error:
            self.emit_error_check(ins.dest, ins.traceback_info)

    def CONCAT(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        stack_size = self.stack_size + len(ins.args)
        self.emit('if (&_stack[{}] >= OME_context->stack_limit) {{'.format(stack_size + 1))
        with self.emit.indented():
            self.emit_return('OME_error(OME_Stack_Overflow)')
        self.emit('}')
        self.emit('OME_context->stack_pointer = &_stack[{}];'.format(stack_size))
        for index, arg in enumerate(ins.args):
            self.emit('_stack[{}] = _{};'.format(index + self.stack_size, arg))
        self.emit('OME_Value _{} = OME_concat(&_stack[{}], {});'.format(ins.dest, self.stack_size, len(ins.args)))
        self.emit('OME_context->stack_pointer = &_stack[{}];'.format(self.stack_size))
        self.emit_error_check(ins.dest, ins.traceback_info)

    def GET_SLOT(self, ins):
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = OME_get_slot(_{}, {});'.format(ins.dest, ins.object, ins.slot_index))

    def SET_SLOT(self, ins):
        self.emit_load_list(ins)
        self.emit('OME_set_slot(_{}, {}, _{});'.format(ins.object, ins.slot_index, ins.value))

    def SET_ELEM(self, ins):
        self.emit_load_list(ins)
        self.emit('OME_untag_array(_{})->elems[{}] = _{};'.format(ins.array, ins.elem_index, ins.value))

    def RETURN(self, ins):
        self.emit_load_list(ins)
        self.emit_return('_{}'.format(ins.source))

class DispatchCodegen(object):
    def __init__(self, emitter, symbol, default_method):
        self.emit = emitter
        self.symbol = symbol
        self.num_args = symbol_arity(symbol)
        self.default_method = default_method

    def begin(self):
        default_name = make_default_label(self.symbol)
        if self.default_method:
            self.emit(format_function_definition_with_arg_names(default_name, self.default_method.arg_names))
            self.emit('{{{}}}\n'.format(self.default_method.code))

        self.emit(format_function_definition(make_message_label(self.symbol), self.num_args))
        self.emit('{')
        self.emit.indent()

    def end(self):
        self.emit.label('not_understood')
        self.end_empty_dispatch()

    def end_empty_dispatch(self):
        if self.default_method:
            default_name = make_default_label(self.symbol)
            self.emit('return {};'.format(format_dispatch_call(default_name, self.num_args)))
        else:
            self.emit('return OME_error(OME_Not_Understood);')
        self.emit.dedent()
        self.emit.end('}')

    def emit_dispatch(self, any_constant_tags):
        self.emit('OME_Tag _tag = OME_get_tag(_0);')
        if self.symbol == 'equals:':
            self.emit('if (OME_equal(_0, _1)) { return OME_True; }')
            self.emit('if (_tag != OME_get_tag(_1) || _tag == OME_Tag_Constant) { return OME_False; }')
        elif self.symbol == 'compare:':
            self.emit('if (_tag != OME_get_tag(_1) || _tag == OME_Tag_Constant) {')
            with self.emit.indented():
                self.emit('return OME_error(OME_Type_Error);')
            self.emit('}')
            self.emit('if (OME_equal(_0, _1)) { return OME_Equal; }')
        if any_constant_tags:
            self.emit('if (_tag == OME_Tag_Constant) { _tag = OME_untag_unsigned(_0) + OME_MIN_CONSTANT_TAG; }')

    def emit_compare_gte(self, tag, gte_label):
        self.emit('if (_tag >= {}) goto {};'.format(tag, gte_label))

    def emit_call_method(self, tag):
        method_name = make_method_label(tag, self.symbol)
        self.emit('return {};'.format(format_dispatch_call(method_name, self.num_args)))

    def emit_maybe_call_method(self, tag):
        method_name = make_method_label(tag, self.symbol)
        self.emit('if (_tag == {}) return {};'.format(tag, format_dispatch_call(method_name, self.num_args)))
        self.emit('goto not_understood;')

class LookupDispatchCodegen(DispatchCodegen):
    def begin(self):
        self.emit('static OME_Method_{} {}(OME_Value _0)'.format(self.num_args - 1, make_lookup_label(self.symbol)))
        self.emit('{')
        self.emit.indent()

    def end_empty_dispatch(self):
        if self.default_method:
            self.emit('return {};'.format(make_default_label(self.symbol)))
        else:
            self.emit('return NULL;')
        self.emit.dedent()
        self.emit.end('}')

    def emit_dispatch(self, any_constant_tags):
        self.emit('OME_Tag _tag = OME_get_tag(_0);')
        if any_constant_tags:
            self.emit('if (_tag == OME_Tag_Constant) { _tag = OME_untag_unsigned(_0) + OME_MIN_CONSTANT_TAG; }')

    def emit_call_method(self, tag):
        self.emit('return {};'.format(make_method_label(tag, self.symbol)))

    def emit_maybe_call_method(self, tag):
        self.emit('if (_tag == {}) return {};'.format(tag, make_method_label(tag, self.symbol)))
        self.emit('goto not_understood;')

class DataTable(object):
    def __init__(self):
        self.strings = {}

    def allocate_string(self, string):
        if isinstance(string, str):
            string = string.encode('utf8')

        if string in self.strings:
            index = self.strings[string]
        else:
            index = len(self.strings)
            self.strings[string] = index

        return '&OME_static_string_{}'.format(index)

    def emit(self, out):
        for string, index in sorted(self.strings.items(), key=lambda x: x[1]):
            out.write('OME_STATIC_STRING(OME_static_string_{}, {});\n'.format(index, literal_c_string(string)))

def emit_traceback_table(out, traceback_entries, include_source=True):
    out.write('static const OME_Traceback_Entry OME_traceback_table[] = {\n')
    for tb in traceback_entries:
        if include_source:
            out.write('{}{{{}, {}, {}, {}, {}, {}}},\n'.format(
                indent,
                literal_c_string(tb.method_name),
                literal_c_string(tb.stream_name),
                literal_c_string(tb.source_line),
                tb.line_number,
                tb.column,
                tb.underline))
        else:
            out.write('{}{{{}, {}, {}}},\n'.format(
                indent,
                literal_c_string(tb.method_name),
                literal_c_string(tb.stream_name),
                tb.line_number))
    out.write('}; /* end of OME_traceback_table */\n')

def emit_constant(out, name, value):
    out.write('#define OME_{} {}\n'.format(name, literal_integer(value)))

def emit_function_declaration(out, name, num_args):
    out.write(format_function_declaration(name, num_args))
    out.write(';\n')

def emit_lookup_declaration(out, name, num_args):
    out.write('static OME_Method_{} {}(OME_Value);\n'.format(num_args - 1, name))

def emit_method_declarations(out, messages, methods):
    emit_function_declaration(out, 'OME_toplevel', 1)
    for tag, symbol in methods:
        emit_function_declaration(out, make_method_label(tag, symbol), symbol_arity(symbol))
    for symbol in messages:
        emit_function_declaration(out, make_message_label(symbol), symbol_arity(symbol))
    for symbol in messages:
        emit_lookup_declaration(out, make_lookup_label(symbol), symbol_arity(symbol))

def generate_builtin_method(label, argnames, code):
    return '{}\n{{{}}}\n'.format(format_function_definition_with_arg_names(label, argnames), code)
