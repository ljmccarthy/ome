/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

#constant Stack-Overflow
#constant Not-Understood
#constant Type-Error
#constant Index-Error
#constant Size-Error
#constant Overflow
#constant Divide-By-Zero

#message == rhs
{
    if (@lookup("equals:")(self)) {
        OME_Value eq = @message("equals:")(self, rhs);
        if (OME_is_boolean(eq) || OME_is_error(eq)) { return eq; }
        return OME_error(OME_Type_Error);
    }
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Equal)) { return OME_True; }
    if (OME_equal(cmp, OME_Less) || OME_equal(cmp, OME_Greater)) { return OME_False; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

#message != rhs
{
    if (@lookup("equals:")(self)) {
        OME_Value eq = @message("equals:")(self, rhs);
        if (OME_is_true(eq)) { return OME_False; }
        if (OME_is_false(eq)) { return OME_True; }
        if (OME_is_error(eq)) { return eq; }
        return OME_error(OME_Type_Error);
    }
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Equal)) { return OME_False; }
    if (OME_equal(cmp, OME_Less) || OME_equal(cmp, OME_Greater)) { return OME_True; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

#message < rhs
{
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Less)) { return OME_True; }
    if (OME_equal(cmp, OME_Greater) || OME_equal(cmp, OME_Equal)) { return OME_False; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

#message <= rhs
{
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Less) || OME_equal(cmp, OME_Equal)) { return OME_True; }
    if (OME_equal(cmp, OME_Greater)) { return OME_False; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

#message > rhs
{
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Greater)) { return OME_True; }
    if (OME_equal(cmp, OME_Less) || OME_equal(cmp, OME_Equal)) { return OME_False; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

#message >= rhs
{
    OME_Value cmp = @message("compare:")(self, rhs);
    if (OME_equal(cmp, OME_Greater) || OME_equal(cmp, OME_Equal)) { return OME_True; }
    if (OME_equal(cmp, OME_Less)) { return OME_False; }
    if (OME_is_error(cmp)) { return cmp; }
    return OME_error(OME_Type_Error);
}

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
    return OME_print(stdout, value);
}

#method BuiltIn print-line: value
{
    OME_Value result = OME_print(stdout, value);
    fputc('\n', stdout);
    return result;
}
