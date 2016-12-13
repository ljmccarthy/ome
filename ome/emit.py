# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import io
from contextlib import contextmanager

class CodeEmitter(object):
    def __init__(self, indent=' ' * 4, indent_level=0):
        self._output = []
        self._indent = indent
        self._indent_level = indent_level
        self._indent_str = self._indent * indent_level

    def indent(self):
        self._indent_level += 1
        self._indent_str = self._indent * self._indent_level

    def dedent(self):
        self._indent_level -= 1
        self._indent_str = self._indent * self._indent_level

    @contextmanager
    def indented(self):
        self.indent()
        try:
            yield
        finally:
            self.dedent()

    def __call__(self, line):
        self._output.append(self._indent_str + line)

    def unindented(self, line):
        self._output.append(line)

    def write_to(self, buf):
        for line in self._output:
            buf.write(line)
            buf.write('\n')

class ProcedureCodeEmitter(CodeEmitter):
    def __init__(self, indent=' ' * 4):
        super(ProcedureCodeEmitter, self).__init__(indent)
        self._end_output = []
        self._tail_emitters = []

    def tail_emitter(self, label):
        emitter = CodeEmitter(self._indent, self._indent_level)
        emitter.label(label)
        self._tail_emitters.append(emitter)
        return emitter

    def end(self, line):
        self._end_output.append(self._indent_str + line)

    def get_output(self):
        buf = io.StringIO()
        self.write_to(buf)
        for emitter in self._tail_emitters:
            emitter.write_to(buf)
        for line in self._end_output:
            buf.write(line)
            buf.write('\n')
        return buf.getvalue()

class MethodCode(object):
    def __init__(self, instructions, num_args):
        self.instructions = instructions
        self.num_args = num_args

    def generate_target_code(self, label, target):
        emit = ProcedureCodeEmitter(indent=target.indent)
        codegen = target.ProcedureCodegen(emit)
        codegen.optimise(self)
        codegen.begin(label, self.num_args)
        for ins in self.instructions:
            codegen.pre_instruction(ins)
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

    def allocate_large_integer(self, string):
        return self.program.data_table.allocate_large_integer(string)

    def get_tag(self, tag_name):
        return self.program.ids.tags[tag_name]

    def get_constant(self, constant_name):
        return self.program.ids.constants[constant_name]

    def make_message_label(self, symbol):
        return self.program.target.make_message_label(symbol)

    def make_lookup_label(self, symbol):
        return self.program.target.make_lookup_label(symbol)

    def make_method_label(self, tag, symbol):
        return self.program.target.make_method_label(tag, symbol)

    def get_code(self):
        return MethodCode(self.instructions, self.num_args)
