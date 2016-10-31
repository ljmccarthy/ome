/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

#method Boolean string
{
    OME_STATIC_STRING(s_false, "False");
    OME_STATIC_STRING(s_true, "True");
    return OME_tag_pointer(OME_Tag_String, OME_untag_unsigned(self) ? &s_true : &s_false);
}

#method Boolean or: rhs
{
    return OME_untag_unsigned(self) ? self : rhs;
}

#method Boolean and: rhs
{
    return OME_untag_unsigned(self) ? rhs : self;
}

#method Boolean if: block
{
    if (OME_untag_unsigned(self)) {
        return @message("then")(block);
    }
    else {
        return @message("else")(block);
    }
}

#method Boolean then: block
{
    if (OME_untag_unsigned(self)) {
        @message("do")(block);
    }
    return OME_Empty;
}

#method Boolean else: block
{
    if (!OME_untag_unsigned(self)) {
        @message("do")(block);
    }
    return OME_Empty;
}
