# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from .emit import ProcedureCodeEmitter

class MethodCodeBuilder(object):
    def __init__(self, num_args, num_locals, program):
        self.num_args = num_args + 1  # self is arg 0
        self.num_locals = num_args + num_locals + 1
        self.program = program
        self.instructions = []
        self.dest = self.add_temp()

    def add_temp(self):
        local = self.num_locals
        self.num_locals += 1
        return local

    def add_instruction(self, instruction):
        self.instructions.append(instruction)

    def allocate_string(self, string):
        return self.program.data_table.allocate_string(string)

    def get_tag(self, tag_name):
        return self.program.ids.tags[tag_name]

    def get_constant(self, constant_name):
        return self.program.ids.constants[constant_name]

    def get_code(self):
        return MethodCode(self.instructions, self.num_args)

class MethodCode(object):
    def __init__(self, instructions, num_args):
        self.instructions = instructions
        self.num_args = num_args

    def generate_target_code(self, label, target):
        emit = ProcedureCodeEmitter(target)
        codegen = target.ProcedureCodegen(emit)
        codegen.optimise(self)
        codegen.begin(label, self.num_args, self.instructions)
        for ins in self.instructions:
            ins.emit(codegen)
        codegen.end()
        return emit.get_output()
