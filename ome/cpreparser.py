# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import re
from .baseparser import BaseParser
from .labels import make_message_label, make_lookup_label
from .parser import re_name, re_keyword, re_operator
from .types import BuiltInMethod

re_name_or_operator = re.compile(re_name.pattern + '|' + re_operator.pattern)
re_empty_lines = re.compile(r'(?: *(?:\r\n|\r|\n))+')
re_command = re.compile(r'^\s*#\s*(constant|opaque|pointer|method)', re.M)
re_space_to_eol = re.compile(r'\s*$', re.M)
re_start_method = re.compile(r'^{', re.M)
re_end_method = re.compile(r'^}', re.M)
re_c_name = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
re_method_ref = re.compile(r'@(message|lookup)')

def remove_empty_lines(s):
    return re_empty_lines.sub('\n', s.strip())

class CMethodRefParser(BaseParser):
    make_label = {'message': make_message_label, 'lookup': make_lookup_label}

    def parse(self):
        refs = []
        code = []
        for leading, m in self.search_iter(re_method_ref):
            command = m.group(1)
            code.append(leading)
            self.expect_token('(', 'expected (')
            self.expect_token('"', 'expected "')
            m = self.match(re_name_or_operator)
            if m:
                symbol = m.group()
            else:
                m = self.expect_match(re_keyword, 'expected message signature')
                symbol = [m.group()]
                while True:
                    while self.match(','):
                        symbol.append(',')
                    m = self.match(re_keyword)
                    if not m:
                        break
                    symbol.append(m.group())
                symbol = ''.join(symbol)
            self.expect_match('"', 'expected "')
            self.expect_token(')', 'expected )')
            refs.append(symbol)
            code.append(self.make_label[command](symbol))
        code.append(self.trailing())
        code = ''.join(code)
        return refs, code

class CPreParser(BaseParser):
    """
    Pre-parse C source code with extra pre-processing directives:

        #constant Constant-Type
        #opaque Opaque-Type
        #pointer Pointer-Type
        #method Foo-Type bar: x baz: y
        {
            OME_Method_0 string_method = @lookup("string")(self);
            @method("bar:")(x);
        }
    """

    def method(self, tag_name):
        argnames = ['self']
        m = self.token(re_name)
        if m:
            symbol = m.group()
        else:
            m = self.token(re_operator)
            if m:
                symbol = m.group()
                m = self.expect_token(re_c_name, 'expected argument name')
                argnames.append(m.group())
            else:
                m = self.expect_token(re_keyword, 'expected method signature')
                symbol = [m.group()]
                while True:
                    m = self.expect_token(re_c_name, 'expected argument name')
                    argnames.append(m.group())
                    while self.token(','):
                        m = self.expect_token(re_c_name, 'expected argument name')
                        argnames.append(m.group())
                        symbol.append(',')
                    m = self.token(re_keyword)
                    if not m:
                        break
                    symbol.append(m.group())
                symbol = ''.join(symbol)
        self.expect_token(re_start_method, 'expected { at start of line')
        line_number = self.line_number
        leading, m = self.search(re_end_method)
        if not m:
            self.error('reached end of file while parsing method')
        refparser = CMethodRefParser(leading, self.stream_name)
        refparser.line_number = line_number
        refs, code = refparser.parse()
        return BuiltInMethod(tag_name, symbol, argnames, refs, code)

    def parse(self, builtin):
        unparsed = []
        tag_names = {
            'constant': builtin.constant_names,
            'opaque': builtin.opaque_names,
            'pointer': builtin.pointer_names
        }
        for leading, m in self.search_iter(re_command):
            unparsed.append(leading)
            command = m.group(1)
            m = self.expect_token(re_name, 'expected type name after #{}'.format(command))
            name = m.group()
            if command == 'method':
                builtin.methods.append(self.method(name))
            else:
                if not self.match(re_space_to_eol):
                    self.error('unexpected tokens after #{} {}'.format(command, name))
                tag_names[command].append(name)
        unparsed.append(self.trailing())
        self.unparsed = remove_empty_lines(''.join(unparsed))
