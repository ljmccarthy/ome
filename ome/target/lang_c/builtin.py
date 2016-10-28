# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ...ast import BuiltInMethod
from ...constants import *

builtin_macros = r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <sys/mman.h>

typedef uint32_t OME_Tag;
typedef union OME_Value OME_Value;
typedef struct OME_Traceback_Entry OME_Traceback_Entry;
typedef union OME_Header OME_Header;
typedef struct OME_Heap_Relocation OME_Heap_Relocation;
typedef struct OME_Heap OME_Heap;
typedef struct OME_Context OME_Context;
typedef struct OME_String OME_String;
typedef struct OME_Array OME_Array;
typedef struct OME_Buffer OME_Buffer;

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

struct OME_Traceback_Entry {
    const char *method_name;
    const char *stream_name;
    const char *source_line;
    uint32_t line_number;
    uint32_t column;
    uint32_t underline;
};

union OME_Header {
    uint64_t bits;
    struct {
        uint32_t mark_next;         // heap index of next object in the mark stack
        uint32_t size        : 8;   // size in words not including header
        uint32_t scan_offset : 8;   // word offset from where to scan
        uint32_t scan_size   : 8;   // number of words to scan
        uint32_t marked      : 1;   // mark bit
    };
};

struct OME_Heap_Relocation {
    uint32_t src;
    uint32_t diff;
};

struct OME_Heap {
    char *pointer;
    char *base;
    char *limit;
    OME_Heap_Relocation *relocs;
    size_t size;
    size_t relocs_size;
    size_t bytes_allocated;
    size_t num_allocated;
    size_t num_collections;
};

struct OME_Context {
    OME_Value *stack_pointer;
    OME_Value *const stack_limit;
    OME_Value *const stack_base;
    OME_Traceback_Entry const **traceback;
    void *const callstack_base;
    OME_Heap heap;
    FILE *stdin;
    FILE *stdout;
    FILE *stderr;
};

struct OME_String {
    uint32_t size;
    char data[];
};

struct OME_Array {
    uint32_t size;
    uint32_t padding;
    OME_Value elems[];
};

struct OME_Buffer {
    uint32_t size;
    uint32_t allocated;
    OME_Value elems;
};

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
    return (void *) ((uintptr_t) value._udata << OME_HEAP_ALIGNMENT_SHIFT);
}

static OME_Value *OME_untag_slots(OME_Value value)
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

static int OME_is_header_aligned(void *header)
{
    return (((uintptr_t) header + sizeof(OME_Header)) & 0xF) == 0;
}

static int OME_is_pointer(OME_Value value)
{
    return OME_get_tag(value) >= OME_Pointer_Tag;
}

#define OME_ALIGNED __attribute__((aligned(OME_HEAP_ALIGNMENT)))

#define OME_ENTER_OR_RETURN(stack_size, retval)\
    OME_Value * const _OME_stack = OME_context->stack_pointer;\
    OME_Value * const stack = _OME_stack;\
    do {\
        OME_Value * const _stack_next = &_OME_stack[stack_size];\
        if (_stack_next >= OME_context->stack_limit) {\
            return (retval);\
        }\
        OME_context->stack_pointer = _stack_next;\
    } while (0)

#define OME_ENTER(stack_size)\
    OME_ENTER_OR_RETURN(stack_size, OME_error_constant(OME_Constant_Stack_Overflow))

#define OME_RETURN(retval)\
    do { OME_context->stack_pointer = _OME_stack; return (retval); } while (0)

#define OME_ERROR(error)\
    OME_RETURN(OME_error_constant(OME_Constant_##error))

#define OME_RETURN_ERROR(value)\
    do {\
        OME_Value _OME_maybe_error = (value);\
        if (OME_is_error(_OME_maybe_error)) {\
            OME_RETURN(_OME_maybe_error);\
        }\
    } while (0)

#define OME_STATIC_STRING(name, string)\
    static const OME_String name OME_ALIGNED = {sizeof(string), string}

static __thread OME_Context *OME_context;
static OME_Array *OME_argv;

static const OME_Value OME_False = {._udata = 0, ._utag = OME_Tag_Boolean};
static const OME_Value OME_True = {._udata = 1, ._utag = OME_Tag_Boolean};
'''

builtin_code = r'''
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
    size_t size = (const char *) OME_context->stack_limit - (const char *) OME_context->traceback;
    memset(OME_context->traceback, 0, size);
    OME_context->traceback = (OME_Traceback_Entry const **) OME_context->stack_limit;
}

static void OME_print_traceback(FILE *out, OME_Value error)
{
    OME_Traceback_Entry const **cur = OME_context->traceback;
    OME_Traceback_Entry const **end = (OME_Traceback_Entry const **) OME_context->stack_limit;

    if (cur < end) {
        fputs("Traceback (most recent call last):\n", out);
    }
    for (; cur < end; cur++) {
        OME_Traceback_Entry const *tb = *cur;
        fprintf(out, "  File \"%s\", line %d, in |%s|\n    %s\n    ",
                tb->stream_name, tb->line_number, tb->method_name, tb->source_line);
        for (int i = 0; i < tb->column; i++) {
            fputc(' ', out);
        }
        for (int i = 0; i < tb->underline; i++) {
            fputc('^', out);
        }
        fputc('\n', out);
    }
    fputs("Error: ", out);
    OME_print_value(out, OME_strip_error(error));
    fputc('\n', out);
    fflush(out);
}

#define OME_MARK_LIST_NULL 0xFFFFFFFF

static void OME_mark(void)
{
    OME_Context *context = OME_context;
    OME_Heap *heap = &context->heap;
    OME_Header *heap_base = (OME_Header *) heap->base;
    OME_Header *heap_end = (OME_Header *) heap->pointer;
    uint32_t mark_list = OME_MARK_LIST_NULL;

    for (OME_Value *cur = context->stack_base, *end = context->stack_pointer; cur < end; cur++) {
        if (OME_is_pointer(*cur)) {
            char *body = OME_untag_pointer(*cur);
            OME_Header *header = (OME_Header *) body - 1;
            if (header >= heap_base && header <= heap_end && !header->marked) {
                header->marked = 1;
                header->mark_next = mark_list;
                mark_list = (body - heap->base) / OME_HEAP_ALIGNMENT;
                //assert((mark_list * OME_HEAP_ALIGNMENT) + heap->base == body);
                //printf("marked %p %d\n", header, mark_list);
            }
        }
    }
    while (mark_list != OME_MARK_LIST_NULL) {
        char *body = heap->base + mark_list * OME_HEAP_ALIGNMENT;
        OME_Header *header = (OME_Header *) body - 1;
        mark_list = header->mark_next;
        OME_Value *cur = (OME_Value *) body + header->scan_offset;
        OME_Value *end = cur + header->scan_size;
        for (; cur < end; cur++) {
            if (OME_is_pointer(*cur)) {
                char *body = OME_untag_pointer(*cur);
                OME_Header *header = (OME_Header *) body - 1;
                if (header >= heap_base && header <= heap_end && !header->marked) {
                    header->marked = 1;
                    header->mark_next = mark_list;
                    mark_list = (body - heap->base) / OME_HEAP_ALIGNMENT;
                    //printf("marked %p %d\n", header, mark_list);
                }
            }
        }
    }
}

static uintptr_t OME_find_relocation(char *pointer, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    uint32_t index = (pointer - heap->base) / OME_HEAP_ALIGNMENT;
    OME_Heap_Relocation *reloc = heap->relocs;
    for (OME_Heap_Relocation *next_reloc = reloc + 1; next_reloc < end_relocs; reloc = next_reloc++) {
        if (next_reloc->src > index) {
            break;
        }
    }
    return reloc->src <= index ? (uintptr_t) reloc->diff * OME_HEAP_ALIGNMENT : 0;
}

static void OME_relocate_slot(OME_Value *slot, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    OME_Tag tag = OME_get_tag(*slot);
    if (tag >= OME_Pointer_Tag) {
        char *p = OME_untag_pointer(*slot);
        if (p >= heap->base && p < heap->limit) {
            uintptr_t diff = OME_find_relocation(p, heap, end_relocs);
            if (diff) {
                //printf("changing field at %p from %p to %p\n", slot, p, p - diff);
                *slot = OME_tag_pointer(tag, p - diff);
            }
        }
    }
}

static void OME_relocate_slots(OME_Value *slot, OME_Value *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (; slot < end; slot++) {
        OME_relocate_slot(slot, heap, end_relocs);
    }
}

static void OME_relocate_stack(OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    OME_relocate_slots(OME_context->stack_base, OME_context->stack_pointer, heap, end_relocs);
}

static void OME_relocate_object(OME_Header *header, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    OME_Value *slot = (OME_Value *) (header + 1) + header->scan_offset;
    OME_relocate_slots(slot, slot + header->scan_size, heap, end_relocs);
}

static void OME_relocate_compacted(char *start, char *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (OME_Header *cur = (OME_Header *) start; (char *) cur < end; cur += cur->size + 1) {
        OME_relocate_object(cur, heap, end_relocs);
    }
}

static void OME_compact(void)
{
    OME_Heap *heap = &OME_context->heap;
    OME_Header *cur = (OME_Header *) heap->base;
    OME_Header *end = (OME_Header *) heap->pointer;
    char *dest = heap->base;
    OME_Heap_Relocation *relocs_cur = heap->relocs;
    OME_Heap_Relocation *relocs_end = heap->relocs + heap->relocs_size;

    while (cur < end) {
        while (cur < end && !cur->marked) {
            //printf("delete %p (%d bytes)\n", cur, cur->size * 8);
            cur += cur->size + 1;
        }
        if (!OME_is_header_aligned(dest)) {
            ((OME_Header *) dest)->bits = 0;
            dest += sizeof(OME_Header);
        }
        char *src = (char *) cur;
        char *dest_next = dest;
        while (cur < end && (cur->marked || (cur->size == 0 && cur+1 < end && (cur+1)->marked))) {
            //printf("retain %p (%d bytes) src=%p dest=%p\n", cur, cur->size * 8, cur, dest_next);
            cur->marked = 0;
            dest_next += (cur->size + 1) * sizeof(OME_Header);
            cur += cur->size + 1;
        }
        uint32_t size = (char *) cur - src;
        if (dest != src && size > 0) {
            memmove(dest, src, size);
            relocs_cur->src = (src + sizeof(OME_Header) - heap->base) / OME_HEAP_ALIGNMENT;
            relocs_cur->diff = (src - dest) / OME_HEAP_ALIGNMENT;
            //printf("reloc src=%p dest=%p size=%u reloc=%u-%u\n", src, dest, size, relocs_cur->src, relocs_cur->diff);
            if (++relocs_cur >= relocs_end) {
                fprintf(stderr, "relocation buffer full!\n");
                exit(1);
            }
        }
        dest = dest_next;
    }

    heap->pointer = dest;
    memset(heap->pointer, 0, heap->limit - heap->pointer);

    OME_relocate_stack(heap, relocs_cur);
    OME_relocate_compacted(heap->base, heap->pointer, heap, relocs_cur);
}

static void OME_collect(void)
{
    //printf("---- begin collection %ld\n", OME_context->heap.num_collections);
    OME_mark();
    OME_compact();
    //printf("---- end collection (%lu bytes used)\n\n", OME_context->heap.pointer - OME_context->heap.base);
    OME_context->heap.num_collections++;
    //exit(0);
}

static void *OME_allocate(uint32_t object_size, uint32_t scan_offset, uint32_t scan_size)
{
    OME_Heap *heap = &OME_context->heap;

    object_size = (object_size + 7) & ~7;
    uint32_t alloc_size = sizeof(OME_Header) + object_size;

    //printf("alloc_size: %d object_size: %d\n", alloc_size, object_size);

    // ensure body of object is 16-byte aligned
    if (!OME_is_header_aligned(heap->pointer)) {
        ((OME_Header *) heap->pointer)->bits = 0;
        heap->pointer += sizeof(OME_Header);
    }

    if (heap->pointer + alloc_size >= heap->limit) {
        OME_collect();
    }

    if (heap->pointer + alloc_size >= heap->limit) {
        size_t new_size = heap->size * 2;
        char *new_heap = mremap(heap->base, heap->size, new_size, 0);
        if (new_heap == MAP_FAILED) {
            perror("mremap");
            exit(1);
        }
        heap->limit = new_heap + new_size;
    }

    OME_Header *header = (OME_Header *) heap->pointer;
    header->marked = 0;
    header->size = object_size / sizeof(OME_Header);
    header->scan_offset = scan_offset;
    header->scan_size = scan_size;
    heap->pointer += alloc_size;
    heap->num_allocated++;
    heap->bytes_allocated += object_size;

    void *body = header + 1;
    assert(OME_untag_pointer(OME_tag_pointer(OME_Pointer_Tag, body)) == body);
    return body;
}

static void *OME_allocate_slots(uint32_t num_slots)
{
    return OME_allocate(sizeof(OME_Value[num_slots]), 0, num_slots);
}

static OME_Array *OME_allocate_array(uint32_t num_elems)
{
    size_t size = sizeof(OME_Array) + sizeof(OME_Value[num_elems]);
    OME_Array *array = OME_allocate(size, sizeof(OME_Array) / sizeof(OME_Value), num_elems);
    array->size = num_elems;
    return array;
}

static void *OME_allocate_data(size_t size)
{
    return OME_allocate(size, 0, 0);
}

static void OME_initialize_heap(OME_Heap *heap)
{
    size_t heap_size = 0x10000;
    char *heap_base = mmap(NULL, heap_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (heap_base == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }

    size_t relocs_size = (heap_size >> 6) / sizeof(OME_Heap_Relocation);
    heap->base = heap_base;
    heap->pointer = heap_base;
    heap->limit = heap_base + heap_size - relocs_size * sizeof(OME_Heap_Relocation);
    heap->relocs = (OME_Heap_Relocation *) heap->limit;
    heap->size = heap_size;
    heap->relocs_size = relocs_size;

    //printf("reloc buffer size: %lu bytes\n", relocs_size * sizeof(OME_Heap_Relocation));
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

builtin_code_main = r'''
#define OME_STACK_SIZE 256

int main(const int argc, const char *const *argv)
{
    OME_argv = malloc(sizeof(OME_Array) + sizeof(OME_Value[argc]));
    OME_argv->size = argc;
    for (int i = 0; i < argc; i++) {
        size_t len = strlen(argv[i]);
        OME_String *arg = malloc(sizeof(OME_String) + len + 1);
        arg->size = len;
        memcpy(arg->data, argv[i], len + 1);
        OME_argv->elems[i] = OME_tag_pointer(OME_Tag_String, arg);
    }

    OME_Value stack[OME_STACK_SIZE];
    OME_Context main_context = {
        .stack_pointer = &stack[0],
        .stack_limit = &stack[OME_STACK_SIZE],
        .stack_base = &stack[0],
        .callstack_base = NULL,
        .traceback = (OME_Traceback_Entry const **) &stack[OME_STACK_SIZE],
        .stdin = stdin,
        .stdout = stdout,
        .stderr = stderr,
    };

    OME_initialize_heap(&main_context.heap);
    OME_context = &main_context;
    OME_Value value = OME_message_main__0(OME_toplevel(OME_False));
    if (OME_is_error(value)) {
        OME_print_traceback(stderr, value);
    }
    OME_context = NULL;
    return OME_is_error(value) ? 1 : 0;
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
