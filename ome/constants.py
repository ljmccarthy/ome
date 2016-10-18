# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

NUM_BITS = 64
NUM_TAG_BITS = 20
NUM_DATA_BITS = NUM_BITS - NUM_TAG_BITS
NUM_EXPONENT_BITS = 8
NUM_SIGNIFICAND_BITS = NUM_DATA_BITS - NUM_EXPONENT_BITS
ERROR_BIT = 1 << (NUM_TAG_BITS - 1)

HEAP_ALIGNMENT_SHIFT = 4
HEAP_ALIGNMENT = 1 << HEAP_ALIGNMENT_SHIFT
HEAP_SIZE_BITS = 10  # 2^10-1 = 1024 slots (8 KB)
MAX_HEAP_OBJECT_SIZE = 2**HEAP_SIZE_BITS

# Tag with all 1 bits is reserved (for untagged negative integers)
MAX_TAG = 2**(NUM_TAG_BITS-1) - 2  # Highest bit of tag is error bit
MIN_CONSTANT_TAG = 2**NUM_TAG_BITS
MAX_CONSTANT_TAG = 2**32 - MIN_CONSTANT_TAG - 1

MIN_SMALL_INTEGER = -2**(NUM_DATA_BITS-1)
MAX_SMALL_INTEGER = 2**(NUM_DATA_BITS-1) - 1
MIN_EXPONENT = -2**(NUM_EXPONENT_BITS-1)
MAX_EXPONENT = 2**(NUM_EXPONENT_BITS-1) - 1
MIN_SIGNIFICAND = -2**(NUM_SIGNIFICAND_BITS-1)
MAX_SIGNIFICAND = 2**(NUM_SIGNIFICAND_BITS-1) - 1

MASK_TAG = (1 << NUM_TAG_BITS) - 1
MASK_DATA = (1 << NUM_DATA_BITS) - 1
MASK_EXPONENT = (1 << NUM_EXPONENT_BITS) - 1
MASK_SIGNIFICAND = (1 << NUM_SIGNIFICAND_BITS) - 1

# Tags < 256 are reserved for non-heap data types
Tag_Boolean = 0
Tag_Constant = 1
Tag_Small_Integer = 2
Tag_Small_Decimal = 3

# Tags >= 256 are reserved for heap data types
Tag_String = 256
Tag_Array = 257
Tag_String_Buffer = 258
Tag_User = 259          # First ID for user-defined blocks

Constant_Empty = 0      # The empty block
Constant_BuiltIn = 1    # Block for built-in methods
Constant_Stack_Overflow = 2
Constant_Not_Understood = 3
Constant_Type_Error = 4
Constant_Index_Error = 5
Constant_Overflow = 6
Constant_Divide_By_Zero = 7
Constant_User = 8       # First ID for user-defined constant blocks

def constant_to_tag(constant):
    return constant + MIN_CONSTANT_TAG

class OmeError(Exception):
    _format = '\x1b[1m{0}: \x1b[31merror:\x1b[0m {1}'

    def __init__(self, message, filename='ome'):
        self.message = message
        self.filename = filename

    def __str__(self):
        return self._format.format(self.filename, self.message)
