# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from io import StringIO
from contextlib import contextmanager

class CodeEmitter(object):
    def __init__(self, target, indent_level=0):
        self.target = target
        self.output = []
        self.indent_level = indent_level
        self.indent_str = target.indent * indent_level

    def indent(self):
        self.indent_level += 1
        self.indent_str = self.target.indent * self.indent_level

    def dedent(self):
        self.indent_level -= 1
        self.indent_str = self.target.indent * self.indent_level

    @contextmanager
    def indented(self):
        self.indent()
        try:
            yield
        finally:
            self.dedent()

    def __call__(self, line):
        self.output.append(self.indent_str + line)

    def label(self, name):
        self.output.append(self.target.define_label_format.format(name))

    def comment(self, comment):
        comment = self.target.comment_format.format(comment)
        self.output.append(self.indent_str + comment)

    def write_to(self, buf):
        for line in self.output:
            buf.write(line)
            buf.write('\n')

class ProcedureCodeEmitter(CodeEmitter):
    def __init__(self, target):
        super(ProcedureCodeEmitter, self).__init__(target)
        self.end_output = []
        self.tail_emitters = []

    def tail_emitter(self, label):
        emitter = CodeEmitter(self.target, self.indent_level)
        emitter.label(label)
        self.tail_emitters.append(emitter)
        return emitter

    def end(self, line):
        self.end_output.append(self.indent_str + line)

    def get_output(self):
        buf = StringIO()
        self.write_to(buf)
        for emitter in self.tail_emitters:
            emitter.write_to(buf)
        for line in self.end_output:
            buf.write(line)
            buf.write('\n')
        return buf.getvalue()

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

class MethodCodeBuilder(object):
    def __init__(self, num_args, num_locals, program):
        self.num_args = num_args + 1  # self is arg 0
        self.num_locals = num_args + num_locals + 1
        self.program = program
        self.instructions = []

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
