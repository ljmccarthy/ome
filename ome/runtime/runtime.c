#ifdef OME_GC_DEBUG
    #define OME_GC_ASSERT(e) assert(e)
    #define OME_GC_PRINT(...) printf("ome gc: " __VA_ARGS__)
#else
    #define OME_GC_ASSERT(e) do {} while (0)
    #define OME_GC_PRINT(...) do {} while (0)
#endif

#ifdef OME_GC_STATS
    #define OME_GC_TIMER_START() clock_t _OME_gc_start_time = clock()
    #define OME_GC_TIMER_END(timer) do { timer += clock() - _OME_gc_start_time; } while (0)
#else
    #define OME_GC_TIMER_START()
    #define OME_GC_TIMER_END(timer)
#endif

static OME_Value OME_print(FILE *out, OME_Value value)
{
    OME_LOCALS(1);
    OME_SAVE_LOCAL(0, value);
    OME_Value string = value;
    if (OME_get_tag(value) != OME_Tag_String) {
        OME_Method_0 string_method = OME_lookup_string__0(value);
        if (string_method) {
            string = string_method(value);
            OME_RETURN_ERROR(string);
        }
    }
    if (OME_get_tag(string) == OME_Tag_String) {
        OME_String *p_string = OME_untag_string(string);
        fwrite(p_string->data, 1, p_string->size, out);
    }
    else {
        OME_LOAD_LOCAL(0, value);
        fprintf(out, "#<%ld:%ld>", (long) OME_get_tag(value), (long) OME_untag_unsigned(value));
    }
    OME_RETURN(OME_Empty);
}

static void OME_append_traceback(uint32_t entry)
{
#ifndef OME_NO_TRACEBACK
    uint32_t *traceback = &OME_context->traceback[-1];
    if ((void *) traceback >= (void *) OME_context->stack_pointer) {
        *traceback = entry;
        OME_context->traceback = traceback;
    }
#endif
}

static void OME_reset_traceback(void)
{
#ifndef OME_NO_TRACEBACK
    size_t size = OME_context->stack_end - OME_context->stack_limit;
    memset(OME_context->traceback, 0, size);
    OME_context->traceback = OME_context->traceback_end;
#endif
}

static void OME_print_traceback(FILE *out, OME_Value error)
{
#ifndef OME_NO_TRACEBACK
    uint32_t *cur = OME_context->traceback;
    uint32_t *end = OME_context->traceback_end;

#ifdef OME_PLATFORM_POSIX
    const int use_ansi = isatty(fileno(out));
#else
    const int use_ansi = 0;
#endif

    if (cur < end) {
        fputs("Traceback (most recent call last):\n", out);
    }
    for (; cur < end; cur++) {
        OME_Traceback_Entry const *tb = &OME_traceback_table[*cur];
        fprintf(out, "  File \"%s\", line %d, in |%s|\n", tb->stream_name, tb->line_number, tb->method_name);
#ifndef OME_NO_SOURCE_TRACEBACK
        if (use_ansi) fputs("\x1b[1m", out);
        fprintf(out, "    %s\n    ", tb->source_line);
        for (uint32_t i = 0; i < tb->column; i++) fputc(' ', out);
        if (use_ansi) fputs("\x1b[31m", out);
        for (uint32_t i = 0; i < tb->underline; i++) fputc('^', out);
        if (use_ansi) fputs("\x1b[0m", out);
        fputc('\n', out);
#endif // OME_NO_SOURCE_TRACEBACK
    }
#endif // OME_NO_TRACEBACK
    fputs("Error: ", out);
    OME_print(out, OME_strip_error(error));
    fputc('\n', out);
    fflush(out);
}

static void *OME_memory_allocate(size_t size)
{
    void *p = mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    return p != MAP_FAILED ? p : NULL;
}

static void *OME_memory_reallocate(void *old_p, size_t old_size, size_t new_size)
{
    void *p = mremap(old_p, old_size, new_size, MREMAP_MAYMOVE);
    return p != MAP_FAILED ? p : NULL;
}

static void OME_memory_free(void *addr, size_t size)
{
    munmap(addr, size);
}

static void OME_set_heap_base(OME_Heap *heap, char *heap_base, size_t size)
{
    size &= ~(OME_HEAP_ALIGNMENT - 1);
    size_t relocs_size = (size >> 5) / sizeof(OME_Heap_Relocation);
    size_t nbits = 8 * sizeof(unsigned long);
    size_t bitmap_size = ((size / sizeof(OME_Header)) + nbits - 1) / nbits;
    size_t metadata_size = OME_heap_align(relocs_size * sizeof(OME_Heap_Relocation) + bitmap_size * sizeof(unsigned long));
    heap->base = heap_base;
    heap->pointer = heap_base;
    heap->limit = heap_base + size - metadata_size;
    heap->relocs = (OME_Heap_Relocation *) heap->limit;
    heap->bitmap = (unsigned long *) (heap->relocs + relocs_size);
    heap->size = size;
    heap->relocs_size = relocs_size;
    heap->bitmap_size = bitmap_size;

    OME_GC_PRINT("heap size: %lu bytes total, %lu bytes usable\n", size, size - metadata_size);
    OME_GC_PRINT("metadata size: %lu bytes\n", metadata_size);
    OME_GC_PRINT("reloc buffer size: %lu bytes\n", relocs_size * sizeof(OME_Heap_Relocation));
    OME_GC_PRINT("bitmap size: %lu bytes (%lu bits)\n", bitmap_size * 8, bitmap_size * nbits);
}

static void OME_initialize_heap(OME_Heap *heap)
{
    size_t heap_size = 0x8000;
    char *heap_base = OME_memory_allocate(heap_size);
    if (heap_base == MAP_FAILED) {
        perror("OME_memory_allocate");
        exit(1);
    }
    OME_set_heap_base(heap, heap_base, heap_size);
}

static void OME_mark_bitmap(OME_Heap *heap, OME_Header *header)
{
    const size_t index = ((char *) header - heap->base) / sizeof(OME_Header);
    const size_t nbits = 8 * sizeof(unsigned long);
    OME_GC_ASSERT(heap->base + (index * sizeof(OME_Header)) == (char *) header);
    OME_GC_ASSERT(index / nbits < heap->bitmap_size);
    heap->bitmap[index / nbits] |= 1UL << (index % nbits);
}

static int OME_is_marked(OME_Heap *heap, OME_Header *header)
{
    size_t index = ((char *) header - heap->base) / sizeof(OME_Header);
    const size_t nbits = 8 * sizeof(unsigned long);
    OME_GC_ASSERT(heap->base + (index * sizeof(OME_Header)) == (char *) header);
    OME_GC_ASSERT(index / nbits < heap->bitmap_size);
    return (heap->bitmap[index / nbits] & (1UL << (index % nbits))) != 0;
}

static void OME_adjust_slots(OME_Heap *heap, OME_Value *start, OME_Value *end, ptrdiff_t diff)
{
    //printf("adjust slots from %p to %p\n", start, end);
    for (OME_Value *slot = start; slot < end; slot++) {
        OME_Tag tag = OME_get_tag(*slot);
        char *body = OME_untag_pointer(*slot);
        if (tag >= OME_Pointer_Tag && body >= heap->base && body < heap->limit) {
            //printf("  changing field at %p from %p to %p\n", slot, body, body + diff);
            *slot = OME_tag_pointer(tag, body + diff);
        }
    }
}

static void OME_move_heap(OME_Heap *heap, char *new_heap, size_t new_size)
{
    ptrdiff_t diff = new_heap - heap->base;
    ptrdiff_t pointer_offset = heap->pointer - heap->base;
    OME_Header *end = (OME_Header *) (new_heap + pointer_offset);

    OME_GC_ASSERT(new_size > heap->size);

    if (diff != 0) {
        OME_GC_PRINT("moving heap from %p to %p (%ld)\n", heap->base, new_heap, diff);

        OME_adjust_slots(heap, OME_context->stack_base, OME_context->stack_pointer, diff);

        for (OME_Header *cur = (OME_Header *) new_heap; cur < end; cur += cur->size + 1) {
            if (cur->scan_size > 0) {
                OME_Value *slot = (OME_Value *) (cur + 1) + cur->scan_offset;
                OME_adjust_slots(heap, slot, slot + cur->scan_size, diff);
            }
        }
    }
    OME_set_heap_base(heap, new_heap, new_size);
    heap->pointer += pointer_offset;
}

static void OME_resize_heap(OME_Heap *heap, size_t new_size)
{
    OME_GC_ASSERT(new_size > heap->size);
    OME_GC_PRINT("resizing heap: %lu KB\n", new_size / 1024);
    char *new_heap = OME_memory_reallocate(heap->base, heap->size, new_size);
    if (!new_heap) {
        perror("OME_memory_reallocate");
        exit(1);
    }
    OME_move_heap(heap, new_heap, new_size);
}

static int OME_compare_big_object(const void *pa, const void *pb)
{
    const OME_Big_Object *a = pa;
    const OME_Big_Object *b = pb;
    return a->body < b->body ? -1 : (a->body > b->body ? 1 : 0);
}

static int OME_compare_big_object_mark(const void *pa, const void *pb)
{
    const OME_Big_Object *a = pa;
    const OME_Big_Object *b = pb;
    if (a->mark != b->mark) {
        return a->mark < b->mark ? -1 : 1;
    }
    return a->body < b->body ? -1 : (a->body > b->body ? 1 : 0);
}

static OME_Big_Object *OME_find_big_object(OME_Heap *heap, void *body)
{
    size_t num = heap->big_objects_end - heap->big_objects;
    OME_Big_Object key = {.body = body};
    return bsearch(&key, heap->big_objects, num, sizeof(OME_Big_Object), OME_compare_big_object);
}

static void OME_sort_big_objects(OME_Heap *heap)
{
    size_t num = heap->big_objects_end - heap->big_objects;
    qsort(heap->big_objects, num, sizeof(OME_Big_Object), OME_compare_big_object);
}

static void OME_free_big_objects(OME_Heap *heap)
{
    size_t num = heap->big_objects_end - heap->big_objects;
    qsort(heap->big_objects, num, sizeof(OME_Big_Object), OME_compare_big_object_mark);

    OME_Big_Object *big;
    for (big = heap->big_objects; big < heap->big_objects_end && !big->mark; big++) {
        OME_GC_PRINT("freeing big object %p (%ld bytes)\n", big->body, big->size);
        OME_memory_free(big->body, big->size);
    }
    heap->big_objects = big;
    OME_GC_PRINT("%ld big objects allocated after collection\n", heap->big_objects_end - heap->big_objects);
    for (; big < heap->big_objects_end; big++) {
        big->mark = 0;
    }
}

static void OME_mark_object(OME_Heap *heap, void *body, size_t scan_offset, size_t scan_size)
{
    OME_Value *cur = (OME_Value *) body + scan_offset;
    OME_Value *end = cur + scan_size;
    for (; cur < end; cur++) {
        if (OME_is_pointer(*cur)) {
            char *body = OME_untag_pointer(*cur);
            if (body >= heap->base && body <= heap->pointer) {
                OME_Header *header = (OME_Header *) body - 1;
                if (!OME_is_marked(heap, header)) {
                    OME_mark_bitmap(heap, header);
                    header->mark_next = heap->mark_list;
                    heap->mark_list = (body - heap->base) / OME_HEAP_ALIGNMENT;
                    //printf("marked %p %d\n", header, heap->mark_list);
                }
            }
            else {
                OME_Big_Object *big = OME_find_big_object(heap, body);
                if (big && !big->mark) {
                    //printf("marked big object %p\n", big->body);
                    big->mark = 1;
                    OME_mark_object(heap, big->body, big->scan_offset, big->scan_size);
                }
            }
        }
    }
}

#define OME_MARK_LIST_NULL 0xFFFFFFFF

static void OME_mark(OME_Heap *heap)
{
    OME_GC_TIMER_START();

    heap->mark_list = OME_MARK_LIST_NULL;
    memset(heap->bitmap, 0, heap->bitmap_size * sizeof(unsigned long));
    OME_sort_big_objects(heap);

    OME_mark_object(heap, OME_context->stack_base, 0, OME_context->stack_pointer - OME_context->stack_base);

    while (heap->mark_list != OME_MARK_LIST_NULL) {
        char *body = heap->base + (uintptr_t) heap->mark_list * OME_HEAP_ALIGNMENT;
        OME_Header *header = (OME_Header *) body - 1;
        heap->mark_list = header->mark_next;
        OME_mark_object(heap, body, header->scan_offset, header->scan_size);
    }

    OME_GC_TIMER_END(heap->mark_time);
}

static uintptr_t OME_find_relocation(char *body, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    uint32_t index = (body - heap->base) / OME_HEAP_ALIGNMENT;
    size_t num_relocs = end_relocs - heap->relocs;
    size_t lo = 0;
    size_t hi = num_relocs - 1;
    size_t i = 0;
    while (lo <= hi) {
        size_t mid = (lo + hi) / 2;
        if (mid >= num_relocs)
            break;

        uint32_t src = heap->relocs[mid].src;
        if (index < src) {
            hi = mid - 1;
        }
        else {
            lo = mid + 1;
            i = mid;
        }
    }
    if (i < num_relocs && heap->relocs[i].src <= index) {
        return (uintptr_t) heap->relocs[i].diff * OME_HEAP_ALIGNMENT;
    }
    return 0;
}

static void OME_relocate_slots(OME_Value *slot, OME_Value *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (; slot < end; slot++) {
        OME_Tag tag = OME_get_tag(*slot);
        char *body = OME_untag_pointer(*slot);
        if (tag >= OME_Pointer_Tag && body >= heap->base && body < heap->limit) {
            uintptr_t diff = OME_find_relocation(body, heap, end_relocs);
            if (diff) {
                //printf("changing field at %p from %p to %p\n", slot, body, body - diff);
                *slot = OME_tag_pointer(tag, body - diff);
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
        if (cur->scan_size > 0) {
            OME_relocate_object(cur, heap, end_relocs);
        }
    }
}

static void OME_relocate_uncompacted(OME_Header *start, OME_Header *end, OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (OME_Header *cur = start; cur < end; cur += cur->size + 1) {
        if (OME_is_marked(heap, cur) && cur->scan_size > 0) {
            OME_relocate_object(cur, heap, end_relocs);
        }
    }
}

static void OME_relocate_big_objects(OME_Heap *heap, OME_Heap_Relocation *end_relocs)
{
    for (OME_Big_Object *big = heap->big_objects; big < heap->big_objects_end; big++) {
        OME_Value *slot = (OME_Value *) big->body + big->scan_offset;
        OME_relocate_slots(slot, slot + big->scan_size, heap, end_relocs);
    }
}

static size_t OME_scan_bitmap(OME_Heap *heap, size_t start)
{
    const size_t nbits = 8 * sizeof(unsigned long);
    size_t start_bit = start % nbits;

    for (size_t bitmap_index = start / nbits; bitmap_index < heap->bitmap_size; bitmap_index++) {
        unsigned long bits = heap->bitmap[bitmap_index] >> start_bit;
        for (size_t bit_index = start_bit; bits && bit_index < nbits; bit_index++, bits >>= 1) {
            if (bits & 1UL) {
                return bitmap_index * nbits + bit_index;
            }
        }
        start_bit = 0;
    }
    return ~0UL;
}

static void OME_compact(OME_Heap *heap)
{
    OME_GC_TIMER_START();

    OME_free_big_objects(heap);

    char *dest = heap->base;
    OME_Header *end = (OME_Header *) heap->pointer;
    OME_Heap_Relocation *relocs_cur = heap->relocs;
    OME_Heap_Relocation *relocs_end = heap->relocs + heap->relocs_size;
    size_t end_index = (heap->pointer - heap->base) / sizeof(OME_Header);

    for (size_t index = 0; index < end_index; ) {
        index = OME_scan_bitmap(heap, index);
        if (index == ~0UL) {
            break;
        }
        char *src = heap->base + index * sizeof(OME_Header);
        OME_Header *cur = (OME_Header *) src;
        while (cur < end && (OME_is_marked(heap, cur) || (cur->size == 0 && OME_is_marked(heap, cur+1)))) {
            //printf("retain %p (%d bytes)\n", cur, cur->size * 8);
            cur += cur->size + 1;
        }
        uint32_t size = (char *) cur - src;
        if (!OME_is_header_aligned(dest)) {
            ((OME_Header *) dest)->bits = 0;
            dest += sizeof(OME_Header);
        }
        if (dest != src && size > 0) {
            memmove(dest, src, size);
            relocs_cur->src = (src + sizeof(OME_Header) - heap->base) / OME_HEAP_ALIGNMENT;
            relocs_cur->diff = (src - dest) / OME_HEAP_ALIGNMENT;
            relocs_cur++;
            //printf("reloc src=%p dest=%p size=%u reloc=%u-%u\n", src, dest, size, relocs_cur->src, relocs_cur->diff);
            if (relocs_cur + 1 >= relocs_end) {
                // relocation buffer full, apply relocations now and reset
                OME_GC_PRINT("relocation buffer full\n");
                relocs_cur->src = ((char *) cur + sizeof(OME_Header) - heap->base) / OME_HEAP_ALIGNMENT;
                relocs_cur->diff = 0;
                relocs_cur++;
                OME_relocate_stack(heap, relocs_cur);
                OME_relocate_compacted((OME_Header *) heap->base, (OME_Header *) (dest + size), heap, relocs_cur);
                OME_relocate_uncompacted(cur, end, heap, relocs_cur);
                OME_relocate_big_objects(heap, relocs_cur);
                relocs_cur = heap->relocs;
            }
        }
        dest += size;
        index = ((char *) cur - heap->base) / sizeof(OME_Header);
    }

    heap->pointer = dest;
    if (heap->pointer < heap->limit) {
        memset(heap->pointer, 0, heap->limit - heap->pointer);
    }

    relocs_cur->src = (heap->limit - heap->base) / OME_HEAP_ALIGNMENT;
    relocs_cur->diff = 0;
    relocs_cur++;
    OME_relocate_stack(heap, relocs_cur);
    OME_relocate_compacted((OME_Header *) heap->base, (OME_Header *) heap->pointer, heap, relocs_cur);
    OME_relocate_big_objects(heap, relocs_cur);

    OME_GC_TIMER_END(heap->compact_time);
}

static void OME_collect(OME_Heap *heap)
{
    OME_mark(heap);
    OME_compact(heap);
    OME_GC_PRINT("%lu bytes used after collection\n", heap->pointer - heap->base);

#ifdef OME_GC_STATS
    heap->num_collections++;
#endif
}

static void OME_collect_big_objects(OME_Heap *heap)
{
    OME_mark(heap);
    OME_GC_TIMER_START();
    OME_free_big_objects(heap);
    OME_GC_TIMER_END(heap->compact_time);
}

static void *OME_allocate(size_t object_size, uint32_t scan_offset, uint32_t scan_size)
{
    OME_Heap *heap = &OME_context->heap;
    object_size = (object_size + 7) & ~7;

    if (object_size > OME_MAX_HEAP_OBJECT_SIZE * sizeof(OME_Value)) {
        if (object_size > OME_MAX_BIG_OBJECT_SIZE * sizeof(OME_Value)) {
            fprintf(stderr, "ome: invalid object object size %ld\n", object_size);
            exit(1);
        }
        OME_Big_Object *big_object = &heap->big_objects[-1];
        if ((char *) big_object < heap->pointer) {
            OME_collect(heap);
            big_object = &heap->big_objects[-1];
            if ((char *) big_object < heap->pointer) {
                OME_resize_heap(heap, heap->size * 4);
                big_object = &heap->big_objects[-1];
            }
        }
        char *body = OME_memory_allocate(object_size);
        if (!body) {
            OME_GC_PRINT("allocation failed, collecting big objects\n");
            OME_collect_big_objects(heap);
            body = OME_memory_allocate(object_size);
            if (!body) {
                perror("OME_memory_allocate");
                exit(1);
            }
            big_object = &heap->big_objects[-1];
        }
        big_object->body = body;
        big_object->mark = 0;
        big_object->scan_offset = scan_offset;
        big_object->scan_size = scan_size;
        big_object->size = object_size;
        heap->big_objects = big_object;
        OME_GC_PRINT("allocated big object %p (%ld bytes)\n", big_object->body, big_object->size);
        OME_GC_ASSERT(OME_untag_pointer(OME_tag_pointer(OME_Pointer_Tag, body)) == body);
        return body;
    }

    size_t alloc_size = object_size + sizeof(OME_Header);
    size_t padded_size = alloc_size + sizeof(OME_Header);

    if (heap->pointer + padded_size >= heap->limit) {
        OME_collect(heap);
        size_t heap_size = heap->limit - heap->base;
        char *heap_quarter = heap->base + heap_size / 4;
        if (heap->pointer + padded_size >= heap_quarter) {
            OME_resize_heap(heap, heap->size * 4);
        }
    }

    OME_Header *header = (OME_Header *) heap->pointer;
    if (!OME_is_header_aligned(header)) {
        header->bits = 0;
        header++;
    }

    header->size = object_size / sizeof(OME_Value);
    header->scan_offset = scan_offset;
    header->scan_size = scan_size;

    heap->pointer = (char *) header + alloc_size;
    heap->num_allocated++;

    void *body = header + 1;
    OME_GC_ASSERT(OME_untag_pointer(OME_tag_pointer(OME_Pointer_Tag, body)) == body);
    return body;
}

static void *OME_allocate_slots(uint32_t num_slots)
{
    return OME_allocate(sizeof(OME_Value[num_slots]), 0, num_slots);
}

static OME_Array *OME_allocate_array(uint32_t num_elems)
{
    size_t size = sizeof(OME_Array) + sizeof(OME_Value[num_elems]);
    OME_Array *array = OME_allocate(size, offsetof(OME_Array, elems) / sizeof(OME_Value), num_elems);
    array->size = num_elems;
    return array;
}

static void *OME_allocate_data(size_t size)
{
    return OME_allocate(size, 0, 0);
}

static OME_String *OME_allocate_string(uint32_t size)
{
    OME_String *string = OME_allocate_data(sizeof(OME_String) + size + 1);
    string->size = size;
    return string;
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
            return OME_error(OME_Type_Error);
        }
        size += OME_untag_string(string)->size;
        if (size > UINT32_MAX) {
            return OME_error(OME_Size_Error);
        }
    }

    OME_String *output = OME_allocate_string(size);
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
        size_t alloc_size = sizeof(OME_String) + len + 1;
        OME_String *arg = malloc(alloc_size);
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
        .stack_pointer = stack,
        .stack_limit = stack + OME_STACK_SIZE,
        .stack_base = stack,
        .stack_end = stack + OME_STACK_SIZE,
        .callback_stack = NULL,
    };

    OME_initialize_heap(&context.heap);
    context.heap.mark_time = 0;
    context.heap.compact_time = 0;

#ifdef OME_GC_STATS
    clock_t start = clock();
#endif

    OME_context = &context;
    OME_Value value = OME_message_main__0(OME_toplevel(OME_False));
    if (OME_is_error(value)) {
        OME_print_traceback(stderr, value);
    }

#ifdef OME_GC_STATS
    clock_t time = clock() - start;
    clock_t gc_time = context.heap.mark_time + context.heap.compact_time;
    printf("collections:  %lu\n", context.heap.num_collections);
    printf("gc time:      %lu\n", gc_time);
    printf("- marking:    %lu\n", context.heap.mark_time);
    printf("- compacting: %lu\n", context.heap.compact_time);
    printf("mutator time: %lu\n", time - gc_time);
    printf("total time:   %lu\n", time);
    printf("gc overhead:  %lu%%\n", gc_time * 100 / time);
#endif

    return OME_is_error(value) ? 1 : 0;
}
