# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .emit import ProcedureCodeEmitter
from .optimise import *

class Label(object):
    def __init__(self, name, location):
        self.name = name
        self.location = location

class MethodCodeBuilder(object):
    def __init__(self, num_args, num_locals):
        self.num_args = num_args + 1  # self is arg 0
        self.num_locals = num_args + num_locals + 1
        self.instructions = []
        self.labels = []
        self.dest = self.add_temp()

    def add_temp(self):
        local = self.num_locals
        self.num_locals += 1
        return local

    def here(self):
        return len(self.instructions)

    def add_label(self):
        label = Label('.L%d' % len(self.labels), self.here())
        self.labels.append(label)
        return label

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def optimise(self, target_type):
        apply_labels_to_instructions(self.instructions, self.labels)
        self.instructions = eliminate_aliases(self.instructions)
        self.instructions = move_constants_to_usage_points(self.instructions, self.num_locals)
        self.instructions = eliminate_redundant_untags(self.instructions)
        self.num_locals = renumber_locals(self.instructions, self.num_args)
        self.instructions, self.num_stack_slots = allocate_registers(self.instructions, self.num_args, target_type)

    def allocate_data(self, data_table):
        for ins in self.instructions:
            if isinstance(ins, LOAD_STRING):
                ins.data_label = data_table.allocate_string(ins.string)

    def generate_assembly(self, label, target_type):
        emit = ProcedureCodeEmitter(label)
        target = target_type(emit)
        target.emit_enter(self.num_stack_slots)
        for ins in self.instructions:
            ins.emit(target)
        target.emit_leave(self.num_stack_slots)
        return emit.get_output()
