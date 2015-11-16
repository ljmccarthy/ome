# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

NUM_BITS = 64
NUM_TAG_BITS = 20
NUM_DATA_BITS = NUM_BITS - NUM_TAG_BITS
NUM_EXPONENT_BITS = 8
NUM_SIGNIFICAND_BITS = NUM_DATA_BITS - NUM_EXPONENT_BITS
NUM_HEADER_USER_BITS = 32

MAX_TAG = 2**NUM_TAG_BITS - 1
MIN_INT = -2**(NUM_DATA_BITS-1)
MAX_INT = 2**(NUM_DATA_BITS-1) - 1
MIN_EXPONENT = -2**(NUM_EXPONENT_BITS-1)
MAX_EXPONENT = 2**(NUM_EXPONENT_BITS-1) - 1
MIN_SIGNIFICAND = -2**(NUM_SIGNIFICAND_BITS-1)
MAX_SIGNIFICAND = 2**(NUM_SIGNIFICAND_BITS-1) - 1
MAX_ARRAY_SIZE = 2**NUM_HEADER_USER_BITS - 1

MASK_TAG = (1 << NUM_TAG_BITS) - 1
MASK_DATA = (1 << NUM_DATA_BITS) - 1
MASK_INT = (1 << NUM_DATA_BITS) - 1
MASK_EXPONENT = (1 << NUM_EXPONENT_BITS) - 1
MASK_SIGNIFICAND = (1 << NUM_SIGNIFICAND_BITS) - 1

# Tags up to 255 are reserved for non-pointer data types
Tag_False = 0           # False is represented as all zero bits
Tag_True = 1            # True is represented as 1
Tag_Constant = 2
Tag_Small_Integer = 3
Tag_Small_Decimal = 4
Tag_String = 256
Tag_Array = 257
Tag_User = 258          # First ID for user-defined blocks
Constant_Empty = 0      # The empty block
Constant_TopLevel = 1   # Top-level block for built-ins
Constant_User = 2       # First ID for user-defined constant blocks

def constant_to_tag(constant):
    return constant + MAX_TAG + 1

def encode_tagged_value(value, tag):
    assert (value & MASK_DATA) == value
    assert (tag & MASK_TAG) == tag
    return (tag << NUM_DATA_BITS) | value

def get_block_tag(block):
    if hasattr(block, 'tag'):
        return block.tag
    else:
        return constant_to_tag(block.constant_tag)

class Error(Exception):
    pass
