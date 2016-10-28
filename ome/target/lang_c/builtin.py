# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ...ast import BuiltInMethod
from ...constants import *
from ...runtime import runtime_header, runtime_source

builtin_macros = runtime_header

builtin_code = runtime_source

builtin_code_main = '''
int main(int argc, const char *const *argv)
{
    OME_initialize(argc, argv);
    return OME_thread_main();
}
'''

builtin_methods = [

BuiltInMethod('print:', 'BuiltIn', [], '''
    OME_print_value(OME_context->stdout, _1);
    return OME_Empty;
'''),

BuiltInMethod('for:', 'BuiltIn', ['do', 'while', 'return'], '''
    OME_ENTER(1);
    stack[0] = _1;
    OME_Method_0 while_method = OME_lookup_while__0(_1);
    OME_Method_0 do_method = OME_lookup_do__0(_1);
    if (!while_method || !do_method) {
        OME_ERROR(Not_Understood);
    }
    while (1) {
        OME_Value cond = while_method(_1);
        OME_RETURN_ERROR(cond);
        if (OME_get_tag(cond) != OME_Tag_Boolean) {
            OME_ERROR(Type_Error);
        }
        _1 = stack[0];
        if (!OME_untag_unsigned(cond)) {
            OME_Method_0 return_method = OME_lookup_return__0(_1);
            if (return_method) {
                OME_RETURN(return_method(_1));
            }
            OME_RETURN(OME_Empty);
        }
        OME_RETURN_ERROR(do_method(_1));
        _1 = stack[0];
    }
'''),

BuiltInMethod('argv', 'BuiltIn', [], '''
    return OME_tag_pointer(OME_Tag_Array, OME_argv);
'''),

BuiltInMethod('string', 'Boolean', [], '''
    OME_STATIC_STRING(s_false, "False");
    OME_STATIC_STRING(s_true, "True");
    return OME_tag_pointer(OME_Tag_String, OME_untag_unsigned(_0) ? &s_true : &s_false);
'''),

BuiltInMethod('string', 'Small-Integer', [], '''
    intptr_t n = OME_untag_signed(_0);
    OME_String *s = OME_allocate_data(32);
    s->size = snprintf(s->data, 31 - sizeof(OME_String), "%" PRIdPTR, n);
    return OME_tag_pointer(OME_Tag_String, s);
'''),

BuiltInMethod('or:', 'Boolean', [], '''
    return OME_untag_unsigned(_0) ? _0 : _1;
'''),

BuiltInMethod('and:', 'Boolean', [], '''
    return OME_untag_unsigned(_0) ? _1 : _0;
'''),

BuiltInMethod('if:', 'Boolean', ['then', 'else'], '''
    if (OME_untag_unsigned(_0)) {
        return OME_message_then__0(_1);
    }
    else {
        return OME_message_else__0(_1);
    }
'''),

BuiltInMethod('then:', 'Boolean', ['do'], '''
    if (OME_untag_unsigned(_0)) {
        OME_message_do__0(_1);
    }
    return OME_Empty;
'''),

BuiltInMethod('else:', 'Boolean', ['do'], '''
    if (!OME_untag_unsigned(_0)) {
        OME_message_do__0(_1);
    }
    return OME_Empty;
'''),

BuiltInMethod('+', 'Small-Integer', [], '''
    intptr_t result = OME_untag_signed(_0) + OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('-', 'Small-Integer', [], '''
    intptr_t result = OME_untag_signed(_0) - OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('×', 'Small-Integer', [], '''
    __int128_t result = (__int128_t) OME_untag_signed(_0) * OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, (intptr_t) result);
'''),

BuiltInMethod('mod:', 'Small-Integer', [], '''
    intptr_t result = OME_untag_signed(_0) % OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('==', 'Small-Integer', [], '''
    uintptr_t result = OME_untag_signed(_0) == OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_False;
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

BuiltInMethod('<', 'Small-Integer', [], '''
    uintptr_t result = OME_untag_signed(_0) < OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

BuiltInMethod('≤', 'Small-Integer', [], '''
    uintptr_t result = OME_untag_signed(_0) <= OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

BuiltInMethod('at:', 'Array', [], '''
    OME_Array *self = OME_untag_pointer(_0);
    intptr_t index = OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (index < 0 || index >= self->size) {
        return OME_error(OME_Index_Error);
    }
    return self->elems[index];
'''),

BuiltInMethod('size', 'Array', [], '''
    OME_Array *self = OME_untag_pointer(_0);
    return OME_tag_signed(OME_Tag_Small_Integer, self->size);
'''),

BuiltInMethod('each:', 'Array', ['item:'], '''
    OME_ENTER(2);
    stack[0] = _0;
    stack[1] = _1;
    OME_Method_1 item_method = OME_lookup_item__1(_1);
    if (!item_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *self = OME_untag_pointer(_0);
    size_t size = self->size;
    for (size_t index = 0; index < size; index++) {
        OME_RETURN_ERROR(item_method(_1, self->elems[index]));
        _0 = stack[0];
        _1 = stack[1];
        self = OME_untag_pointer(_0);
    }
    OME_RETURN(OME_Empty);
'''),

BuiltInMethod('enumerate:', 'Array', ['item:index:'], '''
    OME_ENTER(2);
    stack[0] = _0;
    stack[1] = _1;
    OME_Method_2 item_index_method = OME_lookup_item__1index__1(_1);
    if (!item_index_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *self = OME_untag_pointer(_0);
    size_t size = self->size;
    for (size_t index = 0; index < size; index++) {
        OME_Value t_index = OME_tag_signed(OME_Tag_Small_Integer, index);
        OME_RETURN_ERROR(item_index_method(_1, self->elems[index], t_index));
        _0 = stack[0];
        _1 = stack[1];
        self = OME_untag_pointer(_0);
    }
    OME_RETURN(OME_Empty);
'''),

] # end of builtin_methods

def build_builtins():
    data_defs = []

    for name in constant_names[:-1]:
        uname = name.replace('-', '_')
        data_defs.append('static const OME_Value OME_{} = {{._udata = OME_Constant_{}, ._utag = OME_Tag_Constant}};\n'.format(uname, uname))
        builtin_methods.append(BuiltInMethod('string', name, [], '''
    OME_STATIC_STRING(s, "{}");
    return OME_tag_pointer(OME_Tag_String, &s);
'''.format(name)))

    data_defs.append('\n')
    for n in range(17):
        data_defs.append('typedef OME_Value (*OME_Method_{})({});\n'.format(n, ', '.join(['OME_Value'] * (n + 1))))

    global builtin_data
    builtin_data = ''.join(data_defs)

build_builtins()
del build_builtins
