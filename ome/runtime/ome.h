#define _GNU_SOURCE
#include <stddef.h>
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
    size_t num_allocated;
    size_t num_collections;
};

struct OME_Context {
    OME_Value *stack_pointer;
    OME_Value *const stack_limit;
    OME_Value *const stack_base;
    uint32_t *traceback;
    void *const callstack_base;
    OME_Heap heap;
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