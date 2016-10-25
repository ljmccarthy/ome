# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

NUM_BITS = 64
NUM_TAG_BITS = 17
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

Tag_Constant = 1
Constant_BuiltIn = 1

# Tags < 256 are reserved for non-heap data types
integer_type_names = [
    'Boolean',
    'Constant',
    'Small-Integer',
    'Small-Decimal',
]

# Tags >= 256 are reserved for heap data types
pointer_type_names = [
    'String',
    'String-Buffer',
    'Byte-Array',
    'Byte-Array-Mutable',
    'Byte-Array-Buffer',
    'Array',            # immutable
    'Array-Mutable',    # mutable, fixed-size
    'Array-Buffer',     # mutable, resizable
]

constant_names = [
    'Empty',                # The empty block
    'BuiltIn',              # Block for built-in methods
    'Stack-Overflow',
    'Not-Understood',
    'Type-Error',
    'Index-Error',
    'Overflow',
    'Divide-By-Zero',
]

def constant_to_tag(constant):
    return constant + MIN_CONSTANT_TAG

if __name__ == '__main__':
    for name in integer_type_names + pointer_type_names:
        print('Tag_{} = {}'.format(name.replace('-', '_'), type_tag[name]))
    for name in constant_names:
        print('Constant_{} = {}'.format(name.replace('-', '_'), constant_value[name]))
