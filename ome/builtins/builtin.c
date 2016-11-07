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

#method BuiltIn error: value
{
    OME_reset_traceback();
    return OME_error(value);
}

#method BuiltIn catch: block
{
    OME_Value result = @message("do")(block);
    OME_reset_traceback();
    return OME_strip_error(result);
}

#method BuiltIn try: block
{
    OME_LOCALS(1);
    OME_SAVE_LOCAL(0, block);
    OME_Method_0 catch0_method = NULL;
    OME_Method_1 catch1_method = @lookup("catch:")(block);
    if (!catch1_method) {
        catch0_method = @lookup("catch")(block);
        if (!catch0_method) {
            OME_ERROR(Not_Understood);
        }
    }
    OME_Value result = @message("do")(block);
    if (OME_is_error(result)) {
        OME_reset_traceback();
        OME_LOAD_LOCAL(0, block);
        if (catch1_method) {
            OME_RETURN(catch1_method(block, OME_strip_error(result)));
        }
        else {
            OME_RETURN(catch0_method(block));
        }
    }
    OME_RETURN(result);
}

#method BuiltIn for: block
{
    OME_LOCALS(1);
    OME_SAVE_LOCAL(0, block);
    OME_Method_0 while_method = @lookup("while")(block);
    OME_Method_0 do_method = @lookup("do")(block);
    if (!while_method || !do_method) {
        OME_ERROR(Not_Understood);
    }
    while (1) {
        OME_Value cond = while_method(block);
        OME_RETURN_ERROR(cond);
        OME_LOAD_LOCAL(0, block);
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
        OME_SAVE_LOCAL(0, block);
    }
}

#method BuiltIn argv
{
    return OME_tag_pointer(OME_Tag_Array, OME_argv);
}

#method BuiltIn print: value
{
    OME_print_value(stdout, value);
    return OME_Empty;
}

#method BuiltIn print-line: value
{
    OME_print_value(stdout, value);
    fputc('\n', stdout);
    return OME_Empty;
}
