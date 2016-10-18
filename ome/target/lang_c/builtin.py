# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ...ast import BuiltInMethod
from ...constants import *

builtin_macros = '''\
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

typedef uint32_t OME_Tag;
typedef union OME_Value OME_Value;
typedef struct OME_Heap_Header OME_Heap_Header;
typedef struct OME_Traceback_Entry OME_Traceback_Entry;
typedef struct OME_Context OME_Context;
typedef struct OME_String OME_String;

union OME_Value {
    uintptr_t _bits;
    struct {
        uintptr_t _utag  : OME_NUM_TAG_BITS;
        uintptr_t _udata : OME_NUM_DATA_BITS;
    };
    struct {
        uintptr_t _stag : OME_NUM_TAG_BITS;
        intptr_t _sdata : OME_NUM_DATA_BITS;
    };
};

struct OME_Heap_Header {
    uint32_t mark_next;      // heap index of next object in the mark stack
    uint32_t marked   : 1;   // mark bit
    uint32_t size     : 10;  // number of slots
    uint32_t slots    : 10;  // number of slots to scan
    uint32_t disposer : 11;  // index of dispose method - 0 for no disposer
};

struct OME_Traceback_Entry {
    const char *method_name;
    const char *stream_name;
    const char *source_line;
    uint32_t line_number;
    uint32_t column;
    uint32_t underline;
};

struct OME_Context {
    OME_Value *stack_pointer;
    OME_Value *const stack_limit;
    OME_Value *const stack_base;
    OME_Traceback_Entry const **traceback;
    void *const callstack_base;
    const int argc;
    const char *const *argv;
};

struct OME_String {
    uint32_t size;
    char data[];
};

static __thread OME_Context *OME_context;

static const OME_Value OME_False = {._udata = 0, ._utag = OME_Tag_Boolean};
static const OME_Value OME_True = {._udata = 1, ._utag = OME_Tag_Boolean};
static const OME_Value OME_Empty = {._udata = OME_Constant_Empty, ._utag = OME_Tag_Constant};

static OME_Value OME_tag_unsigned(OME_Tag tag, uintptr_t udata)
{
    return (OME_Value) {._udata = udata, ._utag = tag};
}

static OME_Value OME_tag_signed(OME_Tag tag, intptr_t sdata)
{
    return (OME_Value) {._sdata = sdata, ._stag = tag};
}

static OME_Value OME_tag_pointer(OME_Tag tag, const void *pointer)
{
    return (OME_Value) {._udata = (uintptr_t) pointer >> OME_HEAP_ALIGNMENT_SHIFT, ._utag = tag};
}

static OME_Value OME_constant(uintptr_t constant)
{
    return OME_tag_unsigned(OME_Tag_Constant, constant);
}

static uintptr_t OME_untag_unsigned(OME_Value value)
{
    return (uintptr_t) value._udata;
}

static uintptr_t OME_untag_signed(OME_Value value)
{
    return (intptr_t) value._sdata;
}

static void *OME_untag_pointer(OME_Value value)
{
    return (void *) (uintptr_t) (value._udata << OME_HEAP_ALIGNMENT_SHIFT);
}

static OME_Value *OME_untag_object(OME_Value value)
{
    return (OME_Value *) OME_untag_pointer(value);
}

static OME_String *OME_untag_string(OME_Value value)
{
    return (OME_String *) OME_untag_pointer(value);
}

static OME_Tag OME_get_tag(OME_Value value)
{
    return (OME_Tag) value._utag;
}

static OME_Value OME_error(OME_Value value)
{
    return (OME_Value) {._udata = value._udata, ._utag = value._utag | OME_ERROR_BIT};
}

static OME_Value OME_error_constant(uintptr_t constant)
{
    return OME_tag_unsigned(OME_Tag_Constant | OME_ERROR_BIT, constant);
}

static OME_Value OME_strip_error(OME_Value value)
{
    return (OME_Value) {._udata = value._udata, ._utag = value._utag & ~OME_ERROR_BIT};
}

static int OME_is_error(OME_Value value)
{
    return (value._utag & OME_ERROR_BIT) != 0;
}

static int OME_not_understood(OME_Value value)
{
    return value._bits == OME_error_constant(OME_Constant_Not_Understood)._bits;
}

static size_t OME_heap_alignment(size_t size)
{
    return (size + OME_HEAP_ALIGNMENT - 1) & ~(OME_HEAP_ALIGNMENT - 1);
}

#define OME_ENTER_OR_RETURN(stack_size, retval)\\
    OME_Value * const _OME_stack = OME_context->stack_pointer;\\
    OME_Value * const stack = _OME_stack;\\
    do {\\
        OME_Value * const _stack_next = &_OME_stack[stack_size];\\
        if (_stack_next >= OME_context->stack_limit) {\\
            return (retval);\\
        }\\
        OME_context->stack_pointer = _stack_next;\\
    } while (0)

#define OME_ENTER(stack_size)\\
    OME_ENTER_OR_RETURN(stack_size, OME_error_constant(OME_Constant_Stack_Overflow))

#define OME_RETURN(retval)\\
    do { OME_context->stack_pointer = _OME_stack; return (retval); } while (0)

#define OME_ERROR(error)\\
    OME_RETURN(OME_error_constant(OME_Constant_##error))

#define OME_RETURN_ERROR(value)\\
    do {\\
        OME_Value _OME_maybe_error = (value);\\
        if (OME_is_error(_OME_maybe_error)) {\\
            OME_RETURN(_OME_maybe_error);\\
        }\\
    }\\
    while (0)

#define OME_STATIC_STRING(name, string)\\
    static const OME_String name __attribute__((aligned(OME_HEAP_ALIGNMENT))) = {sizeof(string), string}
'''

builtin_code = '''\
static void OME_print_value(FILE *out, OME_Value value)
{
    if (OME_get_tag(value) != OME_Tag_String) {
        value = OME_message_string__0(value);
    }
    if (OME_get_tag(value) == OME_Tag_String) {
        OME_String *string = OME_untag_string(value);
        fwrite(string->data, 1, string->size, out);
    }
    else {
        fprintf(out, "#<%ld:%ld>", (long) OME_get_tag(value), (long) OME_untag_unsigned(value));
    }
}

static void OME_append_traceback(OME_Traceback_Entry const *entry)
{
    OME_Traceback_Entry const **traceback = &OME_context->traceback[-1];
    if ((void *) traceback >= (void *) OME_context->stack_pointer) {
        *traceback = entry;
        OME_context->traceback = traceback;
    }
}

static void OME_reset_traceback(void)
{
    OME_context->traceback = (OME_Traceback_Entry const **) OME_context->stack_limit;
}

static void OME_print_traceback(FILE *out, OME_Value error)
{
    fputs("Traceback (most recent call last):", out);

    OME_Traceback_Entry const **end = (OME_Traceback_Entry const **) OME_context->stack_limit;
    for (OME_Traceback_Entry const **cur = OME_context->traceback; cur < end; cur++) {
        OME_Traceback_Entry const *tb = *cur;
        fprintf(out, "\\n  File \\"%s\\", line %d, in |%s|\\n    %s\\n    ",
                tb->stream_name, tb->line_number, tb->method_name, tb->source_line);
        for (int i = 0; i < tb->column; i++) {
            fputc(' ', out);
        }
        for (int i = 0; i < tb->underline; i++) {
            fputc('^', out);
        }
    }
    fputs("\\nError: ", out);
    OME_print_value(out, OME_strip_error(error));
    fputc('\\n', out);
    fflush(out);
}

static OME_Value OME_allocate_slots(uint32_t num_slots, OME_Tag tag)
{
    // temporary until GC is implemented
    size_t size = OME_heap_alignment(sizeof(OME_Value[num_slots]));
    void *slots = calloc(1, size);
    return OME_tag_pointer(tag, slots);
}

static void *OME_allocate_data(size_t size)
{
    size = OME_heap_alignment(size);
    return calloc(1, size);
}

static OME_Value OME_concat(OME_Value *strings, unsigned int count)
{
    size_t size = 0;
    for (unsigned int i = 0; i < count; i++) {
        OME_Value string = strings[i];
        if (OME_get_tag(string) != OME_Tag_String) {
            string = OME_message_string__0(string);
            if (OME_is_error(string)) {
                return string;
            }
            strings[i] = string;
        }
        if (OME_get_tag(string) != OME_Tag_String) {
            return OME_error_constant(OME_Constant_Type_Error);
        }
        size += OME_untag_string(string)->size; // TODO check overflow
    }

    OME_String *output = OME_allocate_data(sizeof(OME_String) + size + 1);
    output->size = size;
    char *cur = &output->data[0];
    for (unsigned int i = 0; i < count; i++) {
        OME_String *string = OME_untag_string(strings[i]);
        memcpy(cur, string->data, string->size);
        cur += string->size;
    }

    return OME_tag_pointer(OME_Tag_String, output);
}
'''

builtin_code_main = '''\
int main(const int argc, const char *const *argv)
{
    const unsigned int stack_size = 256;
    OME_Value stack[stack_size];
    OME_Context main_context = {
        .stack_pointer = &stack[0],
        .stack_limit = &stack[stack_size],
        .stack_base = &stack[0],
        .callstack_base = NULL,
        .traceback = (OME_Traceback_Entry const **) &stack[stack_size],
        .argc = argc,
        .argv = argv,
    };
    OME_context = &main_context;
    OME_Value value = OME_message_main__0(OME_toplevel(OME_False));
    if (OME_is_error(value)) {
        OME_print_traceback(stderr, value);
    }
    OME_context = NULL;
    return OME_is_error(value) ? 1 : 0;
}
'''

builtin_data = ''

builtin_methods = [

BuiltInMethod('print:', constant_to_tag(Constant_BuiltIn), [], '''
    OME_print_value(stdout, _1);
    return OME_Empty;
'''),

BuiltInMethod('for:', constant_to_tag(Constant_BuiltIn), ['do', 'while', 'return'], '''
    OME_ENTER(1);
    stack[0] = _1;
    while (1) {
        OME_Value cond = OME_message_while__0(_1);
        OME_RETURN_ERROR(cond);
        if (OME_get_tag(cond) != OME_Tag_Boolean) {
            OME_ERROR(Type_Error);
        }
        _1 = stack[0];
        if (!OME_untag_unsigned(cond)) {
            OME_Value ret = OME_message_return__0(_1);
            if (OME_not_understood(ret)) {
                OME_reset_traceback();
                OME_RETURN(OME_Empty);
            }
            OME_RETURN(ret);
        }
        OME_RETURN_ERROR(OME_message_do__0(_1));
        _1 = stack[0];
    }
'''),

BuiltInMethod('string', Tag_Boolean, [], '''
    OME_STATIC_STRING(s_false, "False");
    OME_STATIC_STRING(s_true, "True");
    return OME_tag_pointer(OME_Tag_String, OME_untag_unsigned(_0) ? &s_true : &s_false);
'''),

BuiltInMethod('string', Tag_Small_Integer, [], '''
    intptr_t n = OME_untag_signed(_0);
    OME_String *s = OME_allocate_data(32);
    s->size = snprintf(s->data, 31 - sizeof(OME_String), "%" PRIdPTR, n);
    return OME_tag_pointer(OME_Tag_String, s);
'''),

BuiltInMethod('or:', Tag_Boolean, [], '''
    return OME_untag_unsigned(_0) ? _0 : _1;
'''),

BuiltInMethod('and:', Tag_Boolean, [], '''
    return OME_untag_unsigned(_0) ? _1 : _0;
'''),

BuiltInMethod('if:', Tag_Boolean, ['then', 'else'], '''
    if (OME_untag_unsigned(_0)) {
        return OME_message_then__0(_1);
    }
    else {
        return OME_message_else__0(_1);
    }
'''),

BuiltInMethod('then:', Tag_Boolean, ['do'], '''
    if (OME_untag_unsigned(_0)) {
        OME_message_do__0(_1);
    }
    return OME_Empty;
'''),

BuiltInMethod('else:', Tag_Boolean, ['do'], '''
    if (!OME_untag_unsigned(_0)) {
        OME_message_do__0(_1);
    }
    return OME_Empty;
'''),

BuiltInMethod('+', Tag_Small_Integer, [], '''
    intptr_t result = OME_untag_signed(_0) + OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('-', Tag_Small_Integer, [], '''
    intptr_t result = OME_untag_signed(_0) - OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('×', Tag_Small_Integer, [], '''
    __int128_t result = (__int128_t) OME_untag_signed(_0) * OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, (intptr_t) result);
'''),

BuiltInMethod('mod:', Tag_Small_Integer, [], '''
    intptr_t result = OME_untag_signed(_0) % OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
'''),

BuiltInMethod('==', Tag_Small_Integer, [], '''
    uintptr_t result = OME_untag_signed(_0) == OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_False;
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

BuiltInMethod('<', Tag_Small_Integer, [], '''
    uintptr_t result = OME_untag_signed(_0) < OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

BuiltInMethod('≤', Tag_Small_Integer, [], '''
    uintptr_t result = OME_untag_signed(_0) <= OME_untag_signed(_1);
    if (OME_get_tag(_1) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_unsigned(OME_Tag_Boolean, result);
'''),

] # end of builtin_methods

def build_builtin_methods():
    for name in constant_names:
        value = constant_value[name]
        builtin_methods.append(BuiltInMethod('string', constant_to_tag(value), [], '''
    OME_STATIC_STRING(s, "{}");
    return OME_tag_pointer(OME_Tag_String, &s);
'''.format(name)))

build_builtin_methods()
del build_builtin_methods
