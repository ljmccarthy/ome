/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

#pointer Byte-Array

#method String string
{
    return self;
}

#method String show
{
    OME_String *string = OME_untag_string(self);
    size_t size = 2;
    for (size_t i = 0; i < string->size; i++) {
        int c = string->data[i];
        if ((7 <= c && c <= 13) || c == 27 || c == '\'' || c == '$' || c == '\\') {
            size += 2;
        }
        else if (c < 32 || c == 127) {
            size += 4;
        }
        else {
            size++;
        }
    }

    OME_LOCALS(1);
    OME_SAVE_LOCAL(0, self);
    OME_String *show_string = OME_allocate_string(size);
    OME_LOAD_LOCAL(0, self);
    string = OME_untag_string(self);

    char *out = show_string->data;
    *out++ = '\'';
    for (size_t i = 0; i < string->size; i++) {
        int c = string->data[i];
        if (7 <= c && c <= 13) {
            *out++ = '\\';
            *out++ = "abtnvfr"[c - 7];
        }
        else if (c == 27) {
            *out++ = '\\';
            *out++ = 'e';
        }
        else if (c == '\'' || c == '$' || c == '\\') {
            *out++ = '\\';
            *out++ = c;
        }
        else if (c < 32 || c == 127) {
            *out++ = '\\';
            *out++ = 'x';
            *out++ = "0123456789abcdef"[(c >> 4) & 0xF];
            *out++ = "0123456789abcdef"[c & 0xF];
        }
        else {
            *out++ = c;
        }
    }
    *out++ = '\'';

    OME_RETURN(OME_tag_pointer(OME_Tag_String, show_string));
}

#method String + rhs
{
    if (OME_get_tag(rhs) != OME_Tag_String) {
        return OME_error(OME_Type_Error);
    }
    OME_LOCALS(2);
    OME_SAVE_LOCAL(0, self);
    OME_SAVE_LOCAL(1, rhs);
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
    if (OME_get_tag(index) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    intptr_t u_index = OME_untag_signed(index);
    OME_String *string = OME_untag_pointer(self);
    if (u_index < 0 || u_index >= string->size) {
        return OME_error(OME_Index_Error);
    }
    return OME_tag_integer(string->data[u_index]);
}

#method String equals: rhs
{
    if (OME_get_tag(rhs) != OME_Tag_String) {
        return OME_False;
    }
    OME_String *l = OME_untag_pointer(self);
    OME_String *r = OME_untag_pointer(rhs);
    if (l->size != r->size) {
        return OME_False;
    }
    if (l->size == 0) {
        return OME_True;
    }
    return OME_boolean(memcmp(l->data, r->data, l->size) == 0);
}

#method String compare: rhs
{
    OME_String *l = OME_untag_pointer(self);
    OME_String *r = OME_untag_pointer(rhs);
    if (l->size == 0) {
        return r->size == 0 ? OME_Equal : OME_Less;
    }
    if (r->size == 0) {
        return OME_Greater;
    }
    size_t size = l->size < r->size ? l->size : r->size;
    int cmp = memcmp(l->data, r->data, size);
    if (cmp != 0) {
        return cmp < 0 ? OME_Less : OME_Greater;
    }
    if (l->size != r->size) {
        return l->size < r->size ? OME_Less : OME_Greater;
    }
    return OME_Equal;
}
