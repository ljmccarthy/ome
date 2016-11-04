/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.
*/

#constant Stack-Overflow
#constant Not-Understood
#constant Type-Error
#constant Index-Error
#constant Overflow
#constant Divide-By-Zero

#method BuiltIn argv
{
    return OME_tag_pointer(OME_Tag_Array, OME_argv);
}

#method BuiltIn print: value
{
    OME_print_value(stdout, value);
    return OME_Empty;
}

#method BuiltIn for: block
{
    OME_ENTER(1);
    stack[0] = block;
    OME_Method_0 while_method = @lookup("while")(block);
    OME_Method_0 do_method = @lookup("do")(block);
    if (!while_method || !do_method) {
        OME_ERROR(Not_Understood);
    }
    while (1) {
        OME_Value cond = while_method(block);
        OME_RETURN_ERROR(cond);
        block = stack[0];
        if (OME_is_false(cond)) {
            OME_Method_0 return_method = @lookup("return")(block);
            if (return_method) {
                OME_RETURN(return_method(block));
            }
            OME_RETURN(OME_Empty);
        }
        if (!OME_is_true(cond)) {
            OME_ERROR(Type_Error);
        }
        OME_RETURN_ERROR(do_method(block));
        block = stack[0];
    }
}
