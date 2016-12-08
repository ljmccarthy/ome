/*
    ome - Object Message Expressions
    Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>
*/

static OME_Large_Integer *OME_make_large_integer(mp_int *n)
{
    OME_Large_Integer *out = OME_allocate_data(sizeof(OME_Large_Integer) + n->used * sizeof(mp_digit));
    out->size = n->used;
    out->sign = n->sign;
    memcpy(out->digits, n->dp, n->used * sizeof(mp_digit));
    return out;
}

static void OME_mp_init_from_small_integer(mp_int *out, mp_digit digits[1], OME_Value value)
{
    intptr_t n = OME_untag_signed(value);
    out->used = 1;
    out->alloc = 1;
    out->sign = n >= 0 ? MP_ZPOS : MP_NEG;
    out->dp = digits;
    digits[0] = n >= 0 ? n : -n;
}

static void OME_mp_init_from_large_integer(mp_int *out, OME_Value value)
{
    OME_Large_Integer *n = OME_untag_pointer(value);
    out->used = n->size;
    out->alloc = n->size;
    out->sign = n->sign;
    out->dp = n->digits;
}

static int OME_is_small_integer(intptr_t n)
{
    return OME_MIN_SMALL_INTEGER <= n && n <= OME_MAX_SMALL_INTEGER;
}

static OME_Value OME_inequality(int cmp)
{
    return cmp < 0 ? OME_Less : (cmp > 0 ? OME_Greater : OME_Equal);
}

OME_NOINLINE
static OME_Value OME_integer_binop(OME_Value _a, OME_Value _b, int (*mp_binop)(mp_int *a, mp_int *b, mp_int *c))
{
    static mp_digit small_min_digits[1] = {-OME_MIN_SMALL_INTEGER};
    static mp_digit small_max_digits[1] = {OME_MAX_SMALL_INTEGER};
    static mp_int small_min = {1, 0, MP_NEG, small_min_digits};
    static mp_int small_max = {1, 0, MP_ZPOS, small_max_digits};

    mp_int a, b, c;
    mp_digit a_digits[1], b_digits[1];

    switch (OME_get_tag(_a)) {
        case OME_Tag_Small_Integer:
            OME_mp_init_from_small_integer(&a, a_digits, _a);
            break;
        case OME_Tag_Large_Integer:
            OME_mp_init_from_large_integer(&a, _a);
            break;
        default:
            return OME_error(OME_Type_Error);
    }

    switch (OME_get_tag(_b)) {
        case OME_Tag_Small_Integer:
            OME_mp_init_from_small_integer(&b, b_digits, _b);
            break;
        case OME_Tag_Large_Integer:
            OME_mp_init_from_large_integer(&b, _b);
            break;
        default:
            return OME_error(OME_Type_Error);
    }

    mp_init(&c);
    mp_binop(&a, &b, &c);

    if (mp_cmp(&c, &small_min) >= 0 && mp_cmp(&c, &small_max) <= 0) {
        intptr_t result = c.sign == MP_ZPOS ? c.dp[0] : -c.dp[0];
        mp_clear(&c);
        return OME_tag_integer(result);
    }

    OME_Large_Integer *result = OME_make_large_integer(&c);
    mp_clear(&c);
    return OME_tag_pointer(OME_Tag_Large_Integer, result);
}

static int mp_quotient(mp_int *a, mp_int *b, mp_int *c)
{
    return mp_div(a, b, c, NULL);
}

static int mp_remainder(mp_int *a, mp_int *b, mp_int *c)
{
    return mp_div(a, b, NULL, c);
}

#method Small-Integer show
{
    char buf[64];
    int size = snprintf(buf, sizeof(buf), "%" PRIdPTR, OME_untag_signed(self));
    OME_String *string = OME_allocate_string(size);
    memcpy(string->data, buf, size);
    return OME_tag_pointer(OME_Tag_String, string);
}

#method Large-Integer show
{
    OME_LOCALS(1);
    OME_SAVE_LOCAL(0, self);
    mp_int n;
    OME_mp_init_from_large_integer(&n, self);
    int size;
    mp_radix_size(&n, 10, &size);
    OME_String *string = OME_allocate_string(size);
    OME_LOAD_LOCAL(0, self);
    n.dp = ((OME_Large_Integer *) OME_untag_pointer(self))->digits;
    mp_toradix(&n, string->data, 10);
    OME_RETURN(OME_tag_pointer(OME_Tag_String, string));
}

#method Small-Integer equals: rhs
{
    return OME_boolean(OME_equal(self, rhs));
}

#method Large-Integer equals: rhs
{
    if (OME_get_tag(rhs) != OME_Tag_Large_Integer) {
        return OME_False;
    }
    mp_int l, r;
    OME_mp_init_from_large_integer(&l, self);
    OME_mp_init_from_large_integer(&r, rhs);
    return OME_boolean(mp_cmp(&l, &r) == 0);
}

#method Small-Integer compare: rhs
{
    switch (OME_get_tag(rhs)) {
        case OME_Tag_Small_Integer: {
            intptr_t l = OME_untag_signed(self);
            intptr_t r = OME_untag_signed(rhs);
            return l < r ? OME_Less : (l > r ? OME_Greater : OME_Equal);
        }
        case OME_Tag_Large_Integer: {
            mp_int l, r;
            mp_digit l_digits[1];
            OME_mp_init_from_small_integer(&l, l_digits, self);
            OME_mp_init_from_large_integer(&r, rhs);
            return OME_inequality(mp_cmp(&l, &r));
        }
        default:
            return OME_error(OME_Type_Error);
    }
}

#method Large-Integer compare: rhs
{
    switch (OME_get_tag(rhs)) {
        case OME_Tag_Small_Integer: {
            mp_int l, r;
            mp_digit r_digits[1];
            OME_mp_init_from_large_integer(&l, self);
            OME_mp_init_from_small_integer(&r, r_digits, rhs);
            return OME_inequality(mp_cmp(&l, &r));
        }
        case OME_Tag_Large_Integer: {
            mp_int l, r;
            OME_mp_init_from_large_integer(&l, self);
            OME_mp_init_from_large_integer(&r, rhs);
            return OME_inequality(mp_cmp(&l, &r));
        }
        default:
            return OME_error(OME_Type_Error);
    }
}

#method Small-Integer + rhs
{
    intptr_t result = OME_untag_signed(self) + OME_untag_signed(rhs);
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer && OME_is_small_integer(result))) {
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_add);
}

#method Small-Integer - rhs
{
    intptr_t result = OME_untag_signed(self) - OME_untag_signed(rhs);
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer && OME_is_small_integer(result))) {
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_sub);
}

#method Small-Integer * rhs
{
    __int128_t result = (__int128_t) OME_untag_signed(self) * OME_untag_signed(rhs);
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer
        && OME_MIN_SMALL_INTEGER <= result && result <= OME_MAX_SMALL_INTEGER)) {
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_mul);
}

#method Small-Integer quotient: rhs
{
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer)) {
        intptr_t divisor = OME_untag_signed(rhs);
        if (OME_UNLIKELY(divisor == 0)) {
            return OME_error(OME_Divide_By_Zero);
        }
        intptr_t result = OME_untag_signed(self) / divisor;
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_quotient);
}

#method Small-Integer remainder: rhs
{
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer)) {
        intptr_t divisor = OME_untag_signed(rhs);
        if (OME_UNLIKELY(divisor == 0)) {
            return OME_error(OME_Divide_By_Zero);
        }
        intptr_t result = OME_untag_signed(self) % divisor;
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_remainder);
}

#method Small-Integer modulo: rhs
{
    if (OME_LIKELY(OME_get_tag(rhs) == OME_Tag_Small_Integer)) {
        intptr_t divisor = OME_untag_signed(rhs);
        if (OME_UNLIKELY(divisor == 0)) {
            return OME_error(OME_Divide_By_Zero);
        }
        if (divisor < 0) divisor = -divisor;
        intptr_t result = OME_untag_signed(self) % (divisor < 0 ? -divisor : divisor);
        if (result < 0) result += divisor;
        return OME_tag_integer(result);
    }
    return OME_integer_binop(self, rhs, mp_mod);
}

#method Large-Integer + rhs
{
    return OME_integer_binop(self, rhs, mp_add);
}

#method Large-Integer - rhs
{
    return OME_integer_binop(self, rhs, mp_sub);
}

#method Large-Integer * rhs
{
    return OME_integer_binop(self, rhs, mp_mul);
}

#method Large-Integer quotient: rhs
{
    if (OME_get_tag(rhs) == OME_Tag_Small_Integer && OME_untag_signed(rhs) == 0) {
        return OME_error(OME_Divide_By_Zero);
    }
    return OME_integer_binop(self, rhs, mp_quotient);
}

#method Large-Integer remainder: rhs
{
    if (OME_get_tag(rhs) == OME_Tag_Small_Integer && OME_untag_signed(rhs) == 0) {
        return OME_error(OME_Divide_By_Zero);
    }
    return OME_integer_binop(self, rhs, mp_remainder);
}

#method Large-Integer modulo: rhs
{
    if (OME_get_tag(rhs) == OME_Tag_Small_Integer && OME_untag_signed(rhs) == 0) {
        return OME_error(OME_Divide_By_Zero);
    }
    return OME_integer_binop(self, rhs, mp_mod);
}
