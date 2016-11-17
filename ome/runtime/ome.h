#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>

typedef uint32_t OME_Tag;
typedef union OME_Value OME_Value;
typedef struct OME_Traceback_Entry OME_Traceback_Entry;
typedef union OME_Header OME_Header;
typedef struct OME_Big_Object OME_Big_Object;
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
#ifndef OME_NO_SOURCE_TRACEBACK
    const char *source_line;
#endif
    uint32_t line_number;
#ifndef OME_NO_SOURCE_TRACEBACK
    uint32_t column;
    uint32_t underline;
#endif
};

union OME_Header {
    uint64_t bits;
    struct {
        uint32_t mark_next;  // heap index of next object in the mark stack
        uint32_t size        : OME_HEAP_SIZE_BITS; // size in words not including header
        uint32_t scan_offset : OME_HEAP_SIZE_BITS; // word offset from where to scan
        uint32_t scan_size   : OME_HEAP_SIZE_BITS; // number of words to scan
    };
};

struct OME_Big_Object {
    void *body;
    size_t mark : 1;
    size_t scan_offset : sizeof(size_t) * 8 - 1;
    size_t scan_size;
    size_t size;
};

struct OME_Heap_Relocation {
    uint32_t src;
    uint32_t diff;
};

struct OME_Heap {
    char *pointer;
    char *base;
    union {
        char *limit;
        OME_Big_Object *big_objects;
    };
    union {
        OME_Big_Object *big_objects_end;
        OME_Heap_Relocation *relocs;
    };
    OME_Heap_Relocation *relocs_end;
    unsigned long *bitmap;
    size_t size;
    size_t relocs_size;
    size_t bitmap_size;
    size_t reserved_size;
    clock_t latency;
    size_t mark_size;
    uint32_t mark_list;
#ifdef OME_GC_STATS
    size_t num_collections;
    clock_t mark_time;
    clock_t compact_time;
    clock_t resize_time;
#endif
};

struct OME_Context {
    OME_Value *stack_pointer;
    union {
        OME_Value *stack_limit;
        uint32_t *traceback;
    };
    OME_Value *stack_base;
    union {
        OME_Value *stack_end;
        uint32_t *traceback_end;
    };
    OME_Value *callback_stack;
    OME_Heap heap;
    clock_t start_time;
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

static OME_Value OME_retag(OME_Tag tag, OME_Value value)
{
    return (OME_Value) {._udata = value._udata, ._utag = tag};
}

static OME_Value OME_tag_integer(intptr_t n)
{
    return OME_tag_signed(OME_Tag_Small_Integer, n);
}

static uintptr_t OME_untag_unsigned(OME_Value value)
{
    return (uintptr_t) value._udata;
}

static intptr_t OME_untag_signed(OME_Value value)
{
    return (intptr_t) value._sdata;
}

static void *OME_untag_pointer(OME_Value value)
{
    return (void *) ((uintptr_t) value._udata << OME_HEAP_ALIGNMENT_SHIFT);
}

static OME_Value *OME_untag_slots(OME_Value value)
{
    return OME_untag_pointer(value);
}

static OME_String *OME_untag_string(OME_Value value)
{
    return OME_untag_pointer(value);
}

static OME_Array *OME_untag_array(OME_Value value)
{
    return OME_untag_pointer(value);
}

static OME_Tag OME_get_tag(OME_Value value)
{
    return (OME_Tag) value._utag;
}

static OME_Value OME_error(OME_Value value)
{
    return (OME_Value) {._udata = value._udata, ._utag = value._utag | OME_ERROR_BIT};
}

static OME_Value OME_strip_error(OME_Value value)
{
    return (OME_Value) {._udata = value._udata, ._utag = value._utag & ~OME_ERROR_BIT};
}

static int OME_is_error(OME_Value value)
{
    return (value._utag & OME_ERROR_BIT) != 0;
}

static int OME_is_pointer(OME_Value value)
{
    return OME_get_tag(value) >= OME_Pointer_Tag;
}

static size_t OME_heap_align(uintptr_t size)
{
    return (size + OME_HEAP_ALIGNMENT - 1) & ~(OME_HEAP_ALIGNMENT - 1);
}

static int OME_is_header_aligned(void *header)
{
    return (((uintptr_t) header + sizeof(OME_Header)) & 0xF) == 0;
}

static int OME_equal(OME_Value a, OME_Value b)
{
    return a._bits == b._bits;
}

static OME_Value OME_boolean(int boolean)
{
    return OME_tag_unsigned(OME_Tag_Constant, boolean ? OME_Constant_True : OME_Constant_False);
}

static int OME_is_false(OME_Value value)
{
    return OME_equal(value, OME_boolean(0));
}

static int OME_is_true(OME_Value value)
{
    return OME_equal(value, OME_boolean(1));
}

static int OME_is_boolean(OME_Value value)
{
    return OME_is_false(value) || OME_is_true(value);
}

static OME_Value OME_get_slot(OME_Value slots, unsigned int index)
{
    return OME_untag_slots(slots)[index];
}

static OME_Value OME_set_slot(OME_Value slots, unsigned int index, OME_Value value)
{
    return OME_untag_slots(slots)[index] = value;
}

#define OME_ALIGNED __attribute__((aligned(OME_HEAP_ALIGNMENT)))

#define OME_ENTER_OR_RETURN(stack_size, retval)\
    OME_Value * const _OME_local_stack = OME_context->stack_pointer;\
    do {\
        OME_Value * const _stack_next = &_OME_local_stack[(stack_size)+1];\
        if (_stack_next >= OME_context->stack_limit) {\
            return (retval);\
        }\
        OME_context->stack_pointer = _stack_next;\
    } while (0)

#define OME_LOCALS(stack_size)\
    OME_ENTER_OR_RETURN(stack_size, OME_error(OME_Stack_Overflow))

#define OME_SAVE_LOCAL(stack_slot, name)\
    do { _OME_local_stack[stack_slot] = name; } while (0)

#define OME_FORGET_LOCAL(stack_slot)\
    do { _OME_local_stack[stack_slot] = OME_boolean(0); } while (0)

#define OME_LOAD_LOCAL(stack_slot, name)\
    do { name = _OME_local_stack[stack_slot]; } while (0)

#define OME_LEAVE\
    do { OME_context->stack_pointer = _OME_local_stack; } while (0)

#define OME_RETURN(retval)\
    do {\
        OME_Value _OME_return_value = (retval);\
        OME_context->stack_pointer = _OME_local_stack;\
        return _OME_return_value;\
    } while (0)

#define OME_ERROR(error)\
    OME_RETURN(OME_error(OME_##error))

#define OME_RETURN_ERROR(value)\
    do {\
        OME_Value _OME_maybe_error = (value);\
        if (OME_is_error(_OME_maybe_error)) {\
            OME_RETURN(_OME_maybe_error);\
        }\
    } while (0)

#define OME_PUSH_CALLBACK_LOCALS()\
    OME_Value *_OME_prev_callback_stack = OME_context->callback_stack;\
    do { OME_context->callback_stack = _OME_local_stack; } while (0)

#define OME_POP_CALLBACK_LOCALS()\
    do { OME_context->callback_stack = _OME_prev_callback_stack; } while (0)

#define OME_CALLBACK_LOCALS()\
    OME_Value * const _OME_local_stack = OME_context->callback_stack

#define OME_STATIC_STRING(name, string)\
    static const OME_String name OME_ALIGNED = {sizeof(string)-1, {string}}

static __thread OME_Context *OME_context;
static OME_Array *OME_argv;
static uint64_t OME_cycles_per_ms;
