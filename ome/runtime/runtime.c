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

static void OME_append_traceback(uint32_t entry)
{
    uint32_t *traceback = &OME_context->traceback[-1];
    if ((void *) traceback >= (void *) OME_context->stack_pointer) {
        *traceback = entry;
        OME_context->traceback = traceback;
    }
}

static void OME_reset_traceback(void)
{
    size_t size = (char *) OME_context->stack_limit - (char *) OME_context->traceback;
    memset(OME_context->traceback, 0, size);
    OME_context->traceback = (uint32_t *) OME_context->stack_limit;
}

static void OME_print_traceback(FILE *out, OME_Value error)
{
    uint32_t *cur = OME_context->traceback;
    uint32_t *end = (uint32_t *) OME_context->stack_limit;

    if (cur < end) {
        fputs("Traceback (most recent call last):\n", out);
    }
    for (; cur < end; cur++) {
        OME_Traceback_Entry const *tb = &OME_traceback_table[*cur];
        fprintf(out, "  File \"%s\", line %d, in |%s|\n    %s\n    ",
                tb->stream_name, tb->line_number, tb->method_name, tb->source_line);
        for (uint32_t i = 0; i < tb->column; i++) {
            fputc(' ', out);
        }
        for (uint32_t i = 0; i < tb->underline; i++) {
            fputc('^', out);
        }
        fputc('\n', out);
    }
    fputs("Error: ", out);
    OME_print_value(out, OME_strip_error(error));
    fputc('\n', out);
    fflush(out);
}

static void OME_set_heap_base(OME_Heap *heap, char *heap_base, size_t size)
{
    size_t relocs_size = (size >> 6) / sizeof(OME_Heap_Relocation);
    heap->base = heap_base;
    heap->pointer = heap_base;
    heap->limit = heap_base + size - relocs_size * sizeof(OME_Heap_Relocation);
    heap->relocs = (OME_Heap_Relocation *) heap->limit;
    heap->size = size;
    heap->relocs_size = relocs_size;

    //printf("reloc buffer size: %lu bytes\n", relocs_size * sizeof(OME_Heap_Relocation));
}

static void OME_initialize_heap(OME_Heap *heap)
{
    size_t heap_size = 0x10000;
    char *heap_base = mmap(NULL, heap_size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    if (heap_base == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }
    OME_set_heap_base(heap, heap_base, heap_size);
}

static void OME_adjust_slots(OME_Heap *heap, OME_Value *start, OME_Value *end, ptrdiff_t diff)
{
    //printf("adjust slots from %p to %p\n", start, end);
    for (OME_Value *slot = start; slot < end; slot++) {
        OME_Tag tag = OME_get_tag(*slot);
        if (tag >= OME_Pointer_Tag) {
            char *body = OME_untag_pointer(*slot);
            if (body >= heap->base && body < heap->limit) {
                //printf("  changing field at %p from %p to %p\n", slot, body, body + diff);
                *slot = OME_tag_pointer(tag, body + diff);
            }
        }
    }
}

static void OME_move_heap(OME_Heap *heap, char *new_heap, size_t new_size)
{
    ptrdiff_t diff = new_heap - heap->base;
    ptrdiff_t pointer_offset = heap->pointer - heap->base;
    OME_Header *end = (OME_Header *) (new_heap + pointer_offset);

    //printf("moving heap from %p to %p (%ld)\n", heap->base, new_heap, diff);

    OME_adjust_slots(heap, OME_context->stack_base, OME_context->stack_pointer, diff);

    for (OME_Header *cur = (OME_Header *) new_heap; cur < end; cur += cur->size + 1) {
        if (cur->marked && cur->scan_size > 0) {
            OME_Value *slot = (OME_Value *) (cur + 1) + cur->scan_offset;
            OME_adjust_slots(heap, slot, slot + cur->scan_size, diff);
        }
    }
    OME_set_heap_base(heap, new_heap, new_size);
    heap->pointer += pointer_offset;
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

static uintptr_t OME_find_relocation(char *body, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    uint32_t index = (body - heap->base) / OME_HEAP_ALIGNMENT;
    //printf("  searching for %u...", index);
    OME_Heap_Relocation *reloc = heap->relocs;
    for (OME_Heap_Relocation *next_reloc = reloc + 1; next_reloc < end_relocs; reloc = next_reloc++) {
        if (next_reloc->src > index) {
            break;
        }
    }
    //printf(" %s %u (%u)\n", reloc->src <= index ? "found" : "not found", reloc->src, reloc->diff);
    return reloc->src <= index ? (uintptr_t) reloc->diff * OME_HEAP_ALIGNMENT : 0;
}

static void OME_relocate_slots(OME_Value *slot, OME_Value *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (; slot < end; slot++) {
        OME_Tag tag = OME_get_tag(*slot);
        if (tag >= OME_Pointer_Tag) {
            char *body = OME_untag_pointer(*slot);
            if (body >= heap->base && body < heap->limit) {
                uintptr_t diff = OME_find_relocation(body, heap, end_relocs);
                if (diff) {
                    //printf("changing field at %p from %p to %p\n", slot, body, body - diff);
                    *slot = OME_tag_pointer(tag, body - diff);
                }
            }
        }
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

static void OME_relocate_compacted(OME_Header *start, OME_Header *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (OME_Header *cur = start; cur < end; cur += cur->size + 1) {
        OME_relocate_object(cur, heap, end_relocs);
    }
}

static void OME_relocate_uncompacted(OME_Header *start, OME_Header *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (OME_Header *cur = start; cur < end; cur += cur->size + 1) {
        if (cur->marked && cur->scan_size > 0) {
            OME_relocate_object(cur, heap, end_relocs);
        }
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
            relocs_cur++;
            //printf("reloc src=%p dest=%p size=%u reloc=%u-%u\n", src, dest, size, relocs_cur->src, relocs_cur->diff);
            if (relocs_cur + 1 >= relocs_end) {
                // relocation buffer full, apply relocations now and reset
                //printf("relocation buffer full!\n");
                relocs_cur->src = ((char *) cur + sizeof(OME_Header) - heap->base) / OME_HEAP_ALIGNMENT;
                relocs_cur->diff = 0;
                relocs_cur++;
                OME_relocate_stack(heap, relocs_cur);
                OME_relocate_compacted((OME_Header *) heap->base, cur, heap, relocs_cur);
                OME_relocate_uncompacted(cur, end, heap, relocs_cur);
                relocs_cur = heap->relocs;
            }
        }
        dest = dest_next;
    }

    heap->pointer = dest;
    //printf("memset %p %p %ld\n", heap->pointer, heap->limit, heap->limit - heap->pointer);
    if (heap->pointer < heap->limit) {
        memset(heap->pointer, 0, heap->limit - heap->pointer);
    }

    relocs_cur->src = (heap->limit - heap->base) / OME_HEAP_ALIGNMENT;
    relocs_cur->diff = 0;
    relocs_cur++;
    OME_relocate_stack(heap, relocs_cur);
    OME_relocate_compacted((OME_Header *) heap->base, (OME_Header *) heap->pointer, heap, relocs_cur);
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

static OME_Header *OME_reserve_allocation(OME_Heap *heap, size_t object_size)
{
    size_t alloc_size = object_size + sizeof(OME_Header);
    size_t padded_size = alloc_size + sizeof(OME_Header);

    if (heap->pointer + padded_size >= heap->limit) {
        OME_collect();
        size_t used = heap->pointer - heap->base;
        size_t total = heap->limit - heap->base;
        if (heap->pointer + padded_size >= heap->limit || used > total / 2) {
            size_t new_size = heap->size * 2;
            char *new_heap = mremap(heap->base, heap->size, new_size, MREMAP_MAYMOVE);
            if (new_heap == MAP_FAILED) {
                perror("mremap");
                exit(1);
            }
            if (new_heap != heap->base) {
                OME_move_heap(heap, new_heap, new_size);
            }
        }
    }

    OME_Header *header = (OME_Header *) heap->pointer;
    if (!OME_is_header_aligned(header)) {
        header->bits = 0;
        header++;
    }
    heap->pointer = (char *) header + alloc_size;
    return header;
}

static void *OME_allocate(uint32_t object_size, uint32_t scan_offset, uint32_t scan_size)
{
    OME_Heap *heap = &OME_context->heap;
    object_size = (object_size + 7) & ~7;

    OME_Header *header = OME_reserve_allocation(heap, object_size);
    header->marked = 0;
    header->size = object_size / sizeof(OME_Header);
    header->scan_offset = scan_offset;
    header->scan_size = scan_size;
    heap->num_allocated++;

    void *body = header + 1;
    //assert(OME_untag_pointer(OME_tag_pointer(OME_Pointer_Tag, body)) == body);
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

static void OME_initialize(int argc, const char *const *argv)
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
}

#define OME_STACK_SIZE 256

static int OME_thread_main(void)
{
    OME_Value stack[OME_STACK_SIZE];
    OME_Context context = {
        .stack_pointer = &stack[0],
        .stack_limit = &stack[OME_STACK_SIZE],
        .stack_base = &stack[0],
        .callstack_base = NULL,
        .traceback = (uint32_t *) &stack[OME_STACK_SIZE],
    };

    OME_initialize_heap(&context.heap);
    OME_context = &context;

    OME_Value value = OME_message_main__0(OME_toplevel(OME_False));
    if (OME_is_error(value)) {
        OME_print_traceback(stderr, value);
    }
    return OME_is_error(value) ? 1 : 0;
}
