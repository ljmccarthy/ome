# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .emit import ProcedureCodeEmitter

class Label(object):
    def __init__(self, name, location):
        self.name = name
        self.location = location

class MethodCodeBuilder(object):
    def __init__(self, num_args, num_locals, data_table):
        self.num_args = num_args + 1  # self is arg 0
        self.num_locals = num_args + num_locals + 1
        self.data_table = data_table
        self.instructions = []
        self.dest = self.add_temp()

    def add_temp(self):
        local = self.num_locals
        self.num_locals += 1
        return local

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def get_code(self):
        return MethodCode(self.instructions, self.num_args)

class MethodCode(object):
    def __init__(self, instructions, num_args):
        self.instructions = instructions
        self.num_args = num_args

    def generate_target_code(self, label, target_type):
        emit = ProcedureCodeEmitter(target_type)
        codegen = target_type.ProcedureCodegen(emit)
        codegen.optimise(self)
        codegen.begin(label, self.num_args, self.instructions)
        for ins in self.instructions:
            ins.emit(codegen)
        codegen.end()
        return emit.get_output()
