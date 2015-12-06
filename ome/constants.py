# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

NUM_BITS = 64
NUM_TAG_BITS = 17
NUM_DATA_BITS = NUM_BITS - NUM_TAG_BITS
NUM_EXPONENT_BITS = 8
NUM_SIGNIFICAND_BITS = NUM_DATA_BITS - NUM_EXPONENT_BITS

GC_SIZE_BITS = 8  # Maximum object size 2^8-1 = 255 slots (~2 KB)
GC_SIZE_MASK = (1 << GC_SIZE_BITS) - 1
NUM_GC_HEADER_FLAGS = 1
MAX_SMALL_OBJECT_SIZE = GC_SIZE_MASK

# Tag with all 1 bits is reserved (for untagged negative integers)
MAX_TAG = 2**(NUM_TAG_BITS-1) - 2  # Highest bit of tag is error bit
MIN_CONSTANT_TAG = 2**NUM_TAG_BITS
MAX_CONSTANT_TAG = 2**32 - MIN_CONSTANT_TAG - 1

MIN_INT = -2**(NUM_DATA_BITS-1)
MAX_INT = 2**(NUM_DATA_BITS-1) - 1
MIN_EXPONENT = -2**(NUM_EXPONENT_BITS-1)
MAX_EXPONENT = 2**(NUM_EXPONENT_BITS-1) - 1
MIN_SIGNIFICAND = -2**(NUM_SIGNIFICAND_BITS-1)
MAX_SIGNIFICAND = 2**(NUM_SIGNIFICAND_BITS-1) - 1
MAX_ARRAY_SIZE = 2**GC_SIZE_BITS - 1

MASK_TAG = (1 << NUM_TAG_BITS) - 1
MASK_DATA = (1 << NUM_DATA_BITS) - 1
MASK_INT = (1 << NUM_DATA_BITS) - 1
MASK_EXPONENT = (1 << NUM_EXPONENT_BITS) - 1
MASK_SIGNIFICAND = (1 << NUM_SIGNIFICAND_BITS) - 1

# Tags up to 255 are reserved for non-pointer data types
Tag_Boolean = 0
Tag_Constant = 1
Tag_Small_Integer = 2
Tag_Small_Decimal = 3
Tag_String = 256
Tag_Array = 257
Tag_String_Buffer = 258
Tag_User = 259          # First ID for user-defined blocks
Constant_Empty = 0      # The empty block
Constant_BuiltIn = 1    # Block for built-in methods
Constant_NotUnderstoodError = 2
Constant_TypeError = 3
Constant_IndexError = 4
Constant_OverflowError = 5
Constant_DivideByZeroError = 6
Constant_User = 7       # First ID for user-defined constant blocks

def constant_to_tag(constant):
    return constant + MIN_CONSTANT_TAG

def encode_tagged_value(value, tag):
    assert (value & MASK_DATA) == value
    assert (tag & MASK_TAG) == tag
    return (tag << NUM_DATA_BITS) | value

def error_tag(tag):
    return tag | (1 << (NUM_TAG_BITS - 1))

def encode_constant(constant):
    return encode_tagged_value(constant, Tag_Constant)

def encode_error_constant(constant):
    return encode_tagged_value(constant, error_tag(Tag_Constant))

def encode_gc_header(num_slots, num_scan_slots):
    assert (num_slots & GC_SIZE_MASK) == num_slots
    assert (num_scan_slots & GC_SIZE_MASK) == num_slots
    return (num_scan_slots << (GC_SIZE_BITS + 1)) | (num_slots << 1) | 1

class OmeError(Exception):
    pass

class OmeFileError(OmeError):
    _format = '\x1b[1m{0}: \x1b[31merror:\x1b[0m {1}'

    def __init__(self, filename, message):
        super(OmeFileError, self).__init__(self._format.format(filename, message))
