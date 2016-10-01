# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

class CodeEmitter(object):
    def __init__(self, target_type):
        self.target_type = target_type
        self.output = []

    def __call__(self, format, *args):
        self.output.append('\t' + format % args)

    def label(self, name):
        self.output.append(self.target_type.define_label_format.format(name))

    def comment(self, format, *args):
        self.output.append('\t' + self.target_type.comment_format.format(format % args))

class ProcedureCodeEmitter(CodeEmitter):
    def __init__(self, name, target_type):
        super(ProcedureCodeEmitter, self).__init__(target_type)
        self.name = name
        self.header_output = []
        self.output = []
        self.tail_emitters = []

    def header_comment(self, format, *args):
        self.header_output.append(self.target_type.comment_format.format(format % args))

    def tail_emitter(self, label):
        emitter = CodeEmitter(self.target_type)
        emitter.label(label)
        self.tail_emitters.append(emitter)
        return emitter

    def get_output(self):
        lines = self.header_output[:]
        lines.append(self.target_type.begin_procedure_format.format(self.name))
        lines.extend(self.output)
        for emitter in self.tail_emitters:
            lines.extend(emitter.output)
        lines.append(self.target_type.end_procedure_format)
        return '\n'.join(lines)
