/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

#method Array size
{
    OME_Array *array = OME_untag_pointer(self);
    return OME_tag_signed(OME_Tag_Small_Integer, array->size);
}

#method Array at: t_index
{
    OME_Array *array = OME_untag_pointer(self);
    intptr_t index = OME_untag_signed(t_index);
    if (OME_get_tag(t_index) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (index < 0 || index >= array->size) {
        return OME_error(OME_Index_Error);
    }
    return array->elems[index];
}

#method Array each: block
{
    OME_ENTER(2);
    stack[0] = self;
    stack[1] = block;
    OME_Method_1 item_method = @lookup("item:")(block);
    if (!item_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *array = OME_untag_pointer(self);
    size_t size = array->size;
    for (size_t index = 0; index < size; index++) {
        OME_RETURN_ERROR(item_method(block, array->elems[index]));
        self = stack[0];
        block = stack[1];
        array = OME_untag_pointer(self);
    }
    OME_RETURN(OME_Empty);
}

#method Array enumerate: block
{
    OME_ENTER(2);
    stack[0] = self;
    stack[1] = block;
    OME_Method_2 item_index_method = @lookup("item:index:")(block);
    if (!item_index_method) {
        OME_ERROR(Not_Understood);
    }
    OME_Array *array = OME_untag_pointer(self);
    size_t size = array->size;
    for (size_t index = 0; index < size; index++) {
        OME_Value t_index = OME_tag_signed(OME_Tag_Small_Integer, index);
        OME_RETURN_ERROR(item_index_method(block, array->elems[index], t_index));
        self = stack[0];
        block = stack[1];
        array = OME_untag_pointer(self);
    }
    OME_RETURN(OME_Empty);
}
