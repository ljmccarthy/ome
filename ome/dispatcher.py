# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .constants import *
from .emit import ProcedureCodeEmitter
from .labels import *

def split_tag_range(target, label_format, tags, exit_label, min_tag, max_tag):
    target.emit.comment('[0x%x..0x%x]', min_tag, max_tag)
    if len(tags) == 1:
        tag = tags[0]
        if min_tag == tag and max_tag == tag:
            target.emit_jump(label_format % tag)
        else:
            target.emit_dispatch_compare_eq(tag, label_format % tag, exit_label)
    else:
        middle = len(tags) // 2
        middle_label = '.tag_ge_%X' % tags[middle]
        target.emit_dispatch_compare_gte(tags[middle], middle_label)
        split_tag_range(target, label_format, tags[:middle], exit_label, min_tag, tags[middle] - 1)
        target.emit.label(middle_label)
        split_tag_range(target, label_format, tags[middle:], exit_label, tags[middle], max_tag)

def generate_dispatcher(symbol, tags, target_type):
    """
    Generate assembly code for dispatching messages. This is implemented as
    a binary search with compare and conditional jump instructions until the
    method for the tag is found.
    """
    tags = sorted(tags)
    any_constant_tags = any(tag > MIN_CONSTANT_TAG for tag in tags)
    emit = ProcedureCodeEmitter(make_send_label(symbol))
    target = target_type(emit)
    if tags:
        target.emit_dispatch(any_constant_tags)
        split_tag_range(target, make_call_label_format(symbol), tags, '.not_understood', 0, 1 << NUM_DATA_BITS)
    else:
        target.emit_empty_dispatch()
    return emit.get_output()
