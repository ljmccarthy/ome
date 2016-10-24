# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .constants import *
from .emit import ProcedureCodeEmitter
from .labels import *

class DispatcherGenerator(object):
    def __init__(self, name, symbol, tags, target, codegen_class):
        tags = sorted(tags)
        self.num_args = symbol_arity(symbol)
        self.emit = ProcedureCodeEmitter(target)
        self.codegen = codegen_class(self.emit)
        self.codegen.begin(name, self.num_args)
        if tags:
            any_constant_tags = any(tag > MIN_CONSTANT_TAG for tag in tags)
            self.codegen.emit_dispatch(any_constant_tags)
            self.split_tag_range(make_method_label_format(symbol), tags, 0, 1 << NUM_DATA_BITS)
            self.codegen.end()
        else:
            self.codegen.end_empty_dispatch()

    def split_tag_range(self, label_format, tags, min_tag, max_tag):
        #self.emit.comment('[0x{:x}..0x{:x}]'.format(min_tag, max_tag))
        if len(tags) == 1:
            tag = tags[0]
            if min_tag == tag and max_tag == tag:
                self.codegen.emit_call_method(label_format.format(tag), self.num_args)
            else:
                self.codegen.emit_maybe_call_method(label_format.format(tag), self.num_args, tag)
        else:
            middle = len(tags) // 2
            middle_label = 'tag_{}'.format(tags[middle])
            self.codegen.emit_compare_gte(tags[middle], middle_label)
            self.split_tag_range(label_format, tags[:middle], min_tag, tags[middle] - 1)
            self.emit.label(middle_label)
            self.split_tag_range(label_format, tags[middle:], tags[middle], max_tag)

def generate_dispatcher(symbol, tags, target):
    """
    Generate assembly code for dispatching messages. This is implemented as
    a binary search with compare and conditional jump instructions until the
    method for the tag is found.
    """
    gen = DispatcherGenerator(make_message_label(symbol), symbol, tags, target, target.DispatchCodegen)
    return gen.emit.get_output()

def generate_lookup_dispatcher(symbol, tags, target):
    gen = DispatcherGenerator(make_lookup_label(symbol), symbol, tags, target, target.LookupDispatchCodegen)
    return gen.emit.get_output()
