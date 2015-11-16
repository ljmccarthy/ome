class CodeEmitter(object):
    def __init__(self):
        self.output = []

    def __call__(self, format, *args):
        self.output.append('\t' + format % args)

    def label(self, name):
        self.output.append('%s:' % name)

    def comment(self, format, *args):
        self.output.append('\t; ' + format % args)

class ProcedureCodeEmitter(CodeEmitter):
    def __init__(self, label):
        self.header_output = []
        self.prelude_output = [label + ':']
        self.output = []
        self.tail_emitters = []

    def header_comment(self, format, *args):
        self.header_output.append('; ' + format % args)

    def prelude(self, format, *args):
        self.prelude_output.append('\t' + format % args)

    def tail_emitter(self, label):
        emitter = CodeEmitter()
        emitter.label(label)
        self.tail_emitters.append(emitter)
        return emitter

    def get_output(self):
        lines = self.header_output[:]
        lines.extend(self.prelude_output)
        lines.extend(self.output)
        for emitter in self.tail_emitters:
            lines.extend(emitter.output)
        lines.append('')
        return '\n'.join(lines)
