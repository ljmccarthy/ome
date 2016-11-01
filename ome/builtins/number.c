/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

#method Small-Integer string
{
    intptr_t n = OME_untag_signed(self);
    OME_String *s = OME_allocate_data(32);
    s->size = snprintf(s->data, 31 - sizeof(OME_String), "%" PRIdPTR, n);
    return OME_tag_pointer(OME_Tag_String, s);
}

#method Small-Integer + rhs
{
    intptr_t result = OME_untag_signed(self) + OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
}

#method Small-Integer - rhs
{
    intptr_t result = OME_untag_signed(self) - OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
}

#method Small-Integer × rhs
{
    __int128_t result = (__int128_t) OME_untag_signed(self) * OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error_constant(OME_Constant_Overflow);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, (intptr_t) result);
}

#method Small-Integer mod: rhs
{
    intptr_t result = OME_untag_signed(self) % OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_tag_signed(OME_Tag_Small_Integer, result);
}

#method Small-Integer == rhs
{
    uintptr_t result = OME_untag_signed(self) == OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_False;
    }
    return OME_boolean(result);
}

#method Small-Integer < rhs
{
    uintptr_t result = OME_untag_signed(self) < OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_boolean(result);
}

#method Small-Integer ≤ rhs
{
    uintptr_t result = OME_untag_signed(self) <= OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error_constant(OME_Constant_Type_Error);
    }
    return OME_boolean(result);
}
