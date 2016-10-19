# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import struct
from ... import optimise
from ...constants import *
from ...instructions import CONCAT
from .cstring import literal_c_string
from .stackalloc import allocate_stack_slots

define_constant_format = '#define {} {}\n'
comment_format = '// {}'
define_label_format = '{}:'
label_format = '{}'
indent = '    '

def format_function_defn(name, num_args):
    return 'static OME_Value {}({})'.format(name, ', '.join('OME_Value _{}'.format(n) for n in range(num_args)))

def format_function_decl(name, num_args):
    return 'static OME_Value {}({})'.format(name, ', '.join('OME_Value' for n in range(num_args)))

def format_dispatch_call(name, num_args):
    return '{}({})'.format(name, ', '.join('_{}'.format(n) for n in range(num_args)))

class ProcedureCodegen(object):
    def __init__(self, emitter):
        self.emit = emitter

    def optimise(self, code):
        code.instructions = optimise.eliminate_aliases(code.instructions)
        optimise.renumber_locals(code.instructions, code.num_args)
        optimise.find_live_sets(code.instructions)
        self.is_leaf = all(ins.is_leaf for ins in code.instructions)
        if not self.is_leaf:
            self.stack_size = allocate_stack_slots(code.instructions, code.num_args)
        else:
            self.stack_size = 0

    def begin(self, name, num_args, instructions):
        self.emit(format_function_defn(name, num_args))
        self.emit('{')
        self.emit.indent()
        if not self.is_leaf and self.stack_size > 0:
            self.emit('OME_Value * const _stack = OME_context->stack_pointer;')
            self.emit('if (&_stack[{}] >= OME_context->stack_limit) {{'.format(self.stack_size))
            with self.emit.indented():
                self.emit('return OME_error_constant(OME_Constant_Stack_Overflow);')
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

    def LOAD_VALUE(self, ins):
        self.emit('const OME_Value _{} = OME_tag_unsigned({}, {});'.format(ins.dest, ins.tag, ins.value))

    def LOAD_LABEL(self, ins):
        self.emit('const OME_Value _{} = OME_tag_pointer({}, {});'.format(ins.dest, ins.tag, ins.label))

    def ALLOC(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = OME_allocate_slots({}, {});'.format(ins.dest, ins.size, ins.tag))

    def emit_return(self, ret):
        if self.stack_size > 0:
            self.emit('OME_context->stack_pointer = _stack;')
            self.emit('return {};'.format(ret))
        else:
            self.emit('return {};'.format(ret))

    def CALL(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = {}({});'.format(
            ins.dest,
            ins.call_label,
            ', '.join('_{}'.format(x) for x in ins.args)))

        if ins.check_error:
            self.emit('if (OME_is_error(_{})) {{'.format(ins.dest))
            with self.emit.indented():
                if ins.traceback_info:
                    self.emit('OME_append_traceback(&OME_traceback_table[{}]);'.format(ins.traceback_info.index))
                self.emit_return('_{}'.format(ins.dest))
            self.emit('}')

    def CONCAT(self, ins):
        self.emit_save_list(ins)
        self.emit_load_list(ins)
        if self.stack_size == 0:
            self.emit('OME_Value * const _stack = OME_context->stack_pointer;')
        stack_size = self.stack_size + len(ins.args)
        self.emit('if (&_stack[{}] >= OME_context->stack_limit) {{'.format(stack_size))
        with self.emit.indented():
            self.emit('OME_context->stack_pointer = _stack;')
            self.emit('return OME_error_constant(OME_Constant_Stack_Overflow);')
        self.emit('}')
        self.emit('OME_context->stack_pointer = &_stack[{}];'.format(stack_size))
        for index, arg in enumerate(ins.args):
            self.emit('_stack[{}] = _{};'.format(index + self.stack_size, arg))
        self.emit('OME_Value _{} = OME_concat(&_stack[{}], {});'.format(ins.dest, self.stack_size, len(ins.args)))
        self.emit('OME_context->stack_pointer = &_stack[{}];'.format(self.stack_size))
        self.emit('if (OME_is_error(_{})) {{'.format(ins.dest))
        with self.emit.indented():
            if ins.traceback_info:
                self.emit('OME_append_traceback(&OME_traceback_table[{}]);'.format(ins.traceback_info.index))
            self.emit_return('_{}'.format(ins.dest))
        self.emit('}')

    def GET_SLOT(self, ins):
        self.emit_load_list(ins)
        self.emit('OME_Value _{} = OME_untag_object(_{})[{}];'.format(ins.dest, ins.object, ins.slot_index))

    def SET_SLOT(self, ins):
        self.emit_load_list(ins)
        self.emit('OME_untag_object(_{})[{}] = _{};'.format(ins.object, ins.slot_index, ins.value))

    def RETURN(self, ins):
        self.emit_load_list(ins)
        if self.stack_size > 0:
            self.emit('OME_context->stack_pointer -= {};'.format(self.stack_size))
        self.emit('return _{};'.format(ins.source))

class DispatchCodegen(object):
    def __init__(self, emitter):
        self.emit = emitter

    def begin(self, name, num_args):
        self.emit(format_function_defn(name, num_args))
        self.emit('{')
        self.emit.indent()

    def end(self):
        self.emit.label('not_understood')
        self.end_empty_dispatch()

    def end_empty_dispatch(self):
        self.emit('return OME_error_constant(OME_Constant_Not_Understood);')
        self.emit.dedent()
        self.emit.end('}')

    def emit_dispatch(self, any_constant_tags):
        self.emit('OME_Tag _tag = OME_get_tag(_0);')
        if any_constant_tags:
            self.emit('if (_tag == OME_Tag_Constant) {{ _tag = OME_untag_unsigned(_0) + {}; }}'.format(MIN_CONSTANT_TAG))

    def emit_compare_gte(self, tag, gte_label):
        self.emit('if (_tag >= {}) goto {};'.format(tag, gte_label))

    def emit_call_method(self, method_name, num_args):
        self.emit('return {};'.format(format_dispatch_call(method_name, num_args)))

    def emit_maybe_call_method(self, method_name, num_args, tag):
        self.emit('if (_tag == {}) return {};'.format(tag, format_dispatch_call(method_name, num_args)))
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
            out.write('static const OME_String OME_static_string_{} OME_ALIGNED = {{{}, {}}};\n'.format(
                index, len(string), literal_c_string(string)))

def emit_traceback_table(out, traceback_entries):
    out.write('static const OME_Traceback_Entry OME_traceback_table[] = {\n')
    for tb in traceback_entries:
        out.write('{{{}, {}, {}, {}, {}, {}}},\n'.format(
            literal_c_string(tb.method_name),
            literal_c_string(tb.stream_name),
            literal_c_string(tb.source_line),
            tb.line_number,
            tb.column,
            tb.underline))
    out.write('}; /* end of OME_traceback_table */\n')

def emit_declaration(out, name, num_args):
    out.write(format_function_decl(name, num_args))
    out.write(';\n')

def generate_builtin_method(label, num_args, code):
    return '{}\n{{{}}}\n'.format(format_function_defn(label, num_args), code)
