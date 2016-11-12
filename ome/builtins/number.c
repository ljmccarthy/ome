/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

#method Small-Integer string
{
    intptr_t n = OME_untag_signed(self);
    OME_String *s = OME_allocate_data(32);
    s->size = snprintf(s->data, 31 - sizeof(OME_String), "%" PRIdPTR, n);
    return OME_tag_pointer(OME_Tag_String, s);
}

#method Small-Integer equals: rhs
{
    return OME_boolean(OME_equal(self, rhs));
}

#method Small-Integer compare: rhs
{
    intptr_t l = OME_untag_signed(self);
    intptr_t r = OME_untag_signed(rhs);
    return l < r ? OME_Less : (l > r ? OME_Greater : OME_Equal);
}

#method Small-Integer + rhs
{
    intptr_t result = OME_untag_signed(self) + OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error(OME_Overflow);
    }
    return OME_tag_integer(result);
}

#method Small-Integer - rhs
{
    intptr_t result = OME_untag_signed(self) - OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error(OME_Overflow);
    }
    return OME_tag_integer(result);
}

#method Small-Integer * rhs
{
    __int128_t result = (__int128_t) OME_untag_signed(self) * OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    if (result < OME_MIN_SMALL_INTEGER || result > OME_MAX_SMALL_INTEGER) {
        return OME_error(OME_Overflow);
    }
    return OME_tag_integer(result);
}

#method Small-Integer / rhs
{
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    intptr_t divisor = OME_untag_signed(rhs);
    if (divisor == 0) {
        return OME_error(OME_Divide_By_Zero);
    }
    intptr_t result = OME_untag_signed(self) / divisor;
    return OME_tag_integer(result);
}

#method Small-Integer mod: rhs
{
    intptr_t result = OME_untag_signed(self) % OME_untag_signed(rhs);
    if (OME_get_tag(rhs) != OME_Tag_Small_Integer) {
        return OME_error(OME_Type_Error);
    }
    return OME_tag_integer(result);
}
