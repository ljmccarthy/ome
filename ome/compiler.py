# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import io
import os
import re
import struct
import subprocess
import sys

from .ast import Method, Sequence, BuiltInBlock
from .constants import *
from .dispatcher import generate_dispatcher
from .instructions import LOAD_STRING
from .labels import *
from .parser import Parser
from .target_x86_64 import Target_x86_64

def encode_string_data(string):
    """Add 32-bit length header and nul termination/alignment padding."""
    string = string.encode('utf8')
    string = struct.pack('I', len(string)) + string
    padding = b'\0' * (8 - (len(string) & 7))
    return string + padding

class DataTable(object):
    def __init__(self):
        self.size = 0
        self.data = []
        self.string_offsets = {}

    def append_data(self, data):
        offset = self.size
        self.data.append(data)
        self.size += len(data)
        return offset

    def allocate_string(self, string):
        if string not in self.string_offsets:
            data = encode_string_data(string)
            self.string_offsets[string] = self.append_data(data)
        return '(OME_data+%s)' % self.string_offsets[string]

    def generate_assembly(self, out):
        out.write('align 8\nOME_data:\n')
        for data in self.data:
             out.write('\tdb ' + ','.join('%d' % byte for byte in data) + '\n')
        out.write('.end:\n')

class Program(object):
    def __init__(self, ast, builtin, target_type):
        self.builtin = builtin
        self.toplevel_method = ast
        self.toplevel_block = ast.expr

        if isinstance(self.toplevel_block, Sequence):
            self.toplevel_block = self.toplevel_block.statements[-1]

        if 'main' not in self.toplevel_block.symbols:
            raise Error('Error: No main method defined')

        self.target_type = target_type
        self.block_list = []
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = DataTable()

        ast.collect_blocks(self.block_list)
        self.allocate_tag_ids()
        self.allocate_constant_tag_ids()
        self.build_code_table()

    def allocate_tag_ids(self):
        tag = Tag_User
        for block in self.block_list:
            if not block.is_constant:
                block.tag = tag
                tag += 1
        if tag > MAX_TAG:
            raise Error('Exhausted all tag IDs, your program is too big!')

    def allocate_constant_tag_ids(self):
        constant_tag = Constant_User
        for block in self.block_list:
            if block.is_constant:
                block.constant_tag = constant_tag
                constant_tag += 1

    def _compile_method(self, method, label):
        code = method.generate_code(self.target_type)
        code.allocate_data(self.data_table)
        return code.generate_assembly(label, self.target_type)

    def compile_method(self, method, tag):
        return self._compile_method(method, make_call_label(tag, method.symbol))

    def build_code_table(self):
        methods = {}

        builtin_tag = constant_to_tag(Constant_BuiltIn)
        for method in self.target_type.builtin_methods:
            if method.tag != builtin_tag or method.symbol in self.builtin.called:
                if method.symbol not in methods:
                    methods[method.symbol] = []
                label = make_call_label(method.tag, method.symbol)
                code = '%s:\n%s' % (label, method.code)
                methods[method.symbol].append((method.tag, code))

        for block in self.block_list:
            for method in block.methods:
                if method.symbol not in methods:
                    methods[method.symbol] = []
                tag = get_block_tag(block)
                code = self.compile_method(method, tag)
                methods[method.symbol].append((tag, code))

        for symbol in sorted(methods.keys()):
            self.code_table.append((symbol, methods[symbol]))
        methods.clear()

    def print_code_table(self):
        for symbol, methods in self.code_table:
            for tag, code in methods:
                print(code)

    def generate_assembly(self, out):
        out.write('bits 64\n\nsection .text\n\n')

        main_label = make_call_label(get_block_tag(self.toplevel_block), 'main')
        env = {
            'MAIN': main_label,
            'NUM_TAG_BITS': NUM_TAG_BITS,
            'NUM_DATA_BITS': NUM_DATA_BITS,
        }
        out.write(self.target_type.builtin_code.format(**env))
        out.write(self._compile_method(self.toplevel_method, 'OME_toplevel'))
        out.write('\n')

        for symbol, methods in self.code_table:
            tags = [tag for tag, code in methods]
            out.write(generate_dispatcher(symbol, tags, self.target_type))
            out.write('\n')
            for tag, code in methods:
                out.write(code)
                out.write('\n')

        out.write('section .rodata\n\n')
        self.data_table.generate_assembly(out)
        out.write('\n')
        out.write(self.target_type.builtin_data)

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).toplevel()

def compile_file_to_assembly(filename, target_type):
    builtin = BuiltInBlock(target_type)
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(builtin)
    ast = ast.resolve_block_refs(builtin)
    program = Program(ast, builtin, target_type)
    #program.print_code_table()
    out = io.StringIO()
    program.generate_assembly(out)
    return out.getvalue().encode('utf8')

def run_assembler(input, outfile):
    p = subprocess.Popen(['yasm', '-f', 'elf64', '-o', outfile, '-'], stdin=subprocess.PIPE)
    p.communicate(input)
    if p.returncode != 0:
        sys.exit(p.returncode)

def run_linker(infile, outfile):
    p = subprocess.Popen(['ld', '-s', '-o', outfile, infile])
    p.communicate()
    if p.returncode != 0:
        sys.exit(p.returncode)

def compile_file(filename, target_type=Target_x86_64):
    asm = compile_file_to_assembly(filename, target_type)
    exe_file = os.path.splitext(filename)[0]
    obj_file = exe_file + '.o'
    run_assembler(asm, obj_file)
    run_linker(obj_file, exe_file)
