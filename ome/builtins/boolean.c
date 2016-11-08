/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

#method True not
{
    return OME_False;
}

#method False not
{
    return OME_True;
}

#method True or: rhs
{
    return self;
}

#method False or: rhs
{
    return rhs;
}

#method True and: rhs
{
    return rhs;
}

#method False and: rhs
{
    return self;
}

#method True if: block
{
    return @message("then")(block);
}

#method False if: block
{
    return @message("else")(block);
}

#method True then: block
{
    return @message("do")(block);
}

#method False then: block
{
    return OME_Empty;
}

#method True else: block
{
    return OME_Empty;
}

#method False else: block
{
    return @message("do")(block);
}
