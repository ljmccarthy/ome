/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

#method Array show
{
    OME_STATIC_STRING(empty, "[]");

    OME_Array *array = OME_untag_pointer(self);
    size_t array_size = array->size;
    if (array_size == 0) {
        return OME_tag_pointer(OME_Tag_String, &empty);
    }

    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_Value *strings = OME_allocate_slots(array_size);
    OME_Value t_strings = OME_tag_pointer(OME_Pointer_Tag, strings);
    OME_SAVE_LOCAL(1, t_strings);
    OME_LOAD_LOCAL(0, self);
    array = OME_untag_pointer(self);

    size_t size = 2 + 2 * (array_size - 1);
    for (size_t i = 0; i < array_size; i++) {
        OME_Value s = @message("show")(array->elems[i]);
        OME_RETURN_ERROR(s);
        if (OME_get_tag(s) != OME_Tag_String) {
            OME_RETURN(OME_error(OME_Type_Error));
        }
        OME_LOAD_LOCAL(0, self);
        OME_LOAD_LOCAL(1, t_strings);
        array = OME_untag_pointer(self);
        strings = OME_untag_pointer(t_strings);
        strings[i] = s;
        size += OME_untag_string(s)->size;
    }

    OME_FORGET_LOCAL(0);

    OME_String *output = OME_allocate_string(size);
    char *cur = output->data;
    OME_LOAD_LOCAL(1, t_strings);
    strings = OME_untag_pointer(t_strings);

    *cur++ = '[';
    for (size_t i = 0; i < array_size; i++) {
        if (i > 0) {
            *cur++ = ';';
            *cur++ = ' ';
        }
        OME_String *s = OME_untag_pointer(strings[i]);
        memcpy(cur, s->data, s->size);
        cur += s->size;
    }
    *cur++ = ']';

    OME_RETURN(OME_tag_pointer(OME_Tag_String, output));
}

#method Array size
{
    OME_Array *array = OME_untag_pointer(self);
    return OME_tag_integer(array->size);
}

#method Array at: index
{
    OME_Array *array = OME_untag_pointer(self);
    intptr_t u_index = OME_untag_signed(index);
    if (OME_get_tag(index) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (u_index < 0 || u_index >= array->size) {
        return OME_error(OME_Index_Error);
    }
    return array->elems[u_index];
}

#method Array each: block
{
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, block);
    OME_Method_1 item_method = @lookup("item:")(block);
    if (!item_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *array = OME_untag_pointer(self);
    size_t size = array->size;
    for (size_t index = 0; index < size; index++) {
        OME_RETURN_ERROR(item_method(block, array->elems[index]));
        OME_LOAD_LOCAL(0, self);
        OME_LOAD_LOCAL(1, block);
        array = OME_untag_pointer(self);
    }
    OME_RETURN(OME_Empty);
}

#method Array enumerate: block
{
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, block);
    OME_Method_2 item_index_method = @lookup("item:index:")(block);
    if (!item_index_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *array = OME_untag_pointer(self);
    size_t size = array->size;
    for (size_t index = 0; index < size; index++) {
        OME_Value t_index = OME_tag_integer(index);
        OME_RETURN_ERROR(item_index_method(block, array->elems[index], t_index));
        OME_LOAD_LOCAL(0, self);
        OME_LOAD_LOCAL(1, block);
        array = OME_untag_pointer(self);
    }
    OME_RETURN(OME_Empty);
}

#method Array + rhs
{
    if (OME_get_tag(rhs) != OME_Tag_Array) {
        return OME_error(OME_Type_Error);
    }
    size_t lsize = OME_untag_array(self)->size;
    size_t rsize = OME_untag_array(rhs)->size;
    if (rsize == 0) {
        return self;
    }
    if (lsize == 0) {
        return rhs;
    }
    size_t size = lsize + rsize;
    if (size > UINT32_MAX) {
        return OME_error(OME_Size_Error);
    }
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, rhs);
    OME_Array *dst = OME_allocate_array(size);
    OME_LOAD_LOCAL(0, self);
    OME_LOAD_LOCAL(1, rhs);
    OME_Array *src1 = OME_untag_pointer(self);
    OME_Array *src2 = OME_untag_pointer(rhs);
    memcpy(dst->elems, src1->elems, src1->size * sizeof(OME_Value));
    memcpy(dst->elems + src1->size, src2->elems, src2->size * sizeof(OME_Value));
    OME_RETURN(OME_tag_pointer(OME_Tag_Array, dst));
}

static int OME_qsort_compare(const void *pi, const void *pj)
{
    OME_Value OME_message_compare__1(OME_Value, OME_Value);

    OME_CALLBACK_LOCALS();
    OME_Value error;
    OME_LOAD_LOCAL(1, error);
    if (OME_is_error(error)) {
        return 0;
    }
    uint32_t i = *(const uint32_t *) pi;
    uint32_t j = *(const uint32_t *) pj;
    OME_Value t_array;
    OME_LOAD_LOCAL(0, t_array);
    OME_Array *array = OME_untag_pointer(t_array);
    OME_Value a = array->elems[i];
    OME_Value b = array->elems[j];
    OME_Value cmp = OME_message_compare__1(a, b);
    if (OME_is_error(cmp)) {
        OME_SAVE_LOCAL(1, cmp);
        return 0;
    }
    if (OME_equal(cmp, OME_Less)) return -1;
    if (OME_equal(cmp, OME_Greater)) return 1;
    if (OME_equal(cmp, OME_Equal)) return 0;
    OME_SAVE_LOCAL(1, OME_error(OME_Type_Error));
    return 0;
}

#method Array sorted
{
    // @message("compare:")

    OME_Array *array = OME_untag_pointer(self);
    uint32_t size = array->size;
    if (size < 2) {
        return self;
    }

    OME_Value error = OME_False;
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, error);

    uint32_t *indices = malloc(sizeof(uint32_t) * size);
    for (uint32_t i = 0; i < size; i++) {
        indices[i] = i;
    }

    OME_PUSH_CALLBACK_LOCALS();
    qsort(indices, size, sizeof(uint32_t), OME_qsort_compare);
    OME_POP_CALLBACK_LOCALS();

    OME_LOAD_LOCAL(1, error);
    if (OME_is_error(error)) {
        free(indices);
        OME_RETURN(error);
    }

    OME_Array *result = OME_allocate_array(size);
    OME_LOAD_LOCAL(0, self);
    array = OME_untag_pointer(self);

    for (uint32_t i = 0; i < size; i++) {
        result->elems[i] = array->elems[indices[i]];
    }

    free(indices);
    OME_RETURN(OME_tag_pointer(OME_Tag_Array, result));
}
