/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

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
