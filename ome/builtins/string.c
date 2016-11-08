/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

#pointer Byte-Array

#method String string
{
    return self;
}

#method String + rhs
{
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, rhs);
    if (OME_get_tag(rhs) != OME_Tag_String) {
        OME_ERROR(Type_Error);
    }
    OME_RETURN(OME_concat(_OME_local_stack, 2));
}

#method String utf8-bytes
{
    return OME_retag(OME_Tag_Byte_Array, self);
}

#method Byte-Array size
{
    return OME_tag_integer(OME_untag_string(self)->size);
}

#method Byte-Array at: index
{
    intptr_t u_index = OME_untag_signed(index);
    if (OME_get_tag(index) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    OME_String *string = OME_untag_pointer(self);
    if (u_index < 0 || u_index >= string->size) {
        return OME_error(OME_Index_Error);
    }
    return OME_tag_integer(string->data[u_index]);
}
