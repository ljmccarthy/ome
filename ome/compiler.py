# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import io
import os
import re
import struct
import subprocess
import sys

from .ast import Block, BuiltInBlock, Method, Send, Sequence
from .constants import *
from .dispatcher import generate_dispatcher
from .instructions import LOAD_STRING
from .labels import *
from .parser import Parser
from .target_x86_64 import Target_x86_64

class TraceBackInfo(object):
    def __init__(self, file_info, source_line):
        self.file_info = file_info
        self.source_line = source_line

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

def collect_nodes_of_type(ast, node_type):
    nodes = []
    def append_block(node):
        if isinstance(node, node_type):
            nodes.append(node)
    ast.walk(append_block)
    return nodes

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
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = DataTable()

        self.block_list = collect_nodes_of_type(ast, Block)
        self.allocate_tag_ids()
        self.allocate_constant_tag_ids()

        self.send_list = collect_nodes_of_type(ast, Send)
        self.find_used_methods()
        self.compile_traceback_info()

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
                block.tag = constant_to_tag(constant_tag)
                block.tag_constant = constant_tag
                constant_tag += 1
        if constant_tag > MAX_CONSTANT_TAG:
            raise Error('Exhausted all constant tag IDs, your program is too big!')

    def find_used_methods(self):
        self.sent_messages = set(['string'])
        self.sent_messages.update(
            send.symbol for send in self.send_list if not send.receiver_block)

        self.called_methods = set([
            (self.toplevel_block.tag, 'main'),
        ])
        self.called_methods.update(
            (send.receiver_block.tag, send.symbol) for send in self.send_list
            if send.receiver_block and send.symbol not in self.sent_messages)

        for method in self.target_type.builtin_methods:
            if method.sent_messages and self.should_include_method(method, self.builtin.tag):
                self.sent_messages.update(method.sent_messages)

    def compile_traceback_info(self):
        for send in self.send_list:
            if send.parse_state:
                ps = send.parse_state
                file_info = '\n  File "%s", line %s, in |%s|\n    ' % (
                    ps.stream_name, ps.line_number, send.method.symbol)
                send.traceback_info = TraceBackInfo(
                    file_info = self.data_table.allocate_string(file_info),
                    source_line = self.data_table.allocate_string(ps.current_line.strip()))

    def compile_method_with_label(self, method, label):
        code = method.generate_code()
        code.optimise(self.target_type)
        code.allocate_data(self.data_table)
        return code.generate_assembly(label, self.target_type)

    def compile_method(self, method, tag):
        return self.compile_method_with_label(method, make_call_label(tag, method.symbol))

    def should_include_method(self, method, tag):
        return method.symbol in self.sent_messages or (tag, method.symbol) in self.called_methods

    def build_code_table(self):
        methods = {}

        for method in self.target_type.builtin_methods:
            if self.should_include_method(method, self.builtin.tag):
                if method.symbol not in methods:
                    methods[method.symbol] = []
                label = make_call_label(method.tag, method.symbol)
                code = '%s:\n%s' % (label, method.code)
                methods[method.symbol].append((method.tag, code))

        for block in self.block_list:
            for method in block.methods:
                if self.should_include_method(method, block.tag):
                    if method.symbol not in methods:
                        methods[method.symbol] = []
                    code = self.compile_method(method, block.tag)
                    methods[method.symbol].append((block.tag, code))

        for symbol in sorted(methods.keys()):
            self.code_table.append((symbol, methods[symbol]))

        methods.clear()

    def generate_assembly(self, out):
        out.write('bits 64\n\nsection .text\n\n')

        env = {
            'MAIN': make_call_label(self.toplevel_block.tag, 'main'),
            'NUM_TAG_BITS': NUM_TAG_BITS,
            'NUM_DATA_BITS': NUM_DATA_BITS,
        }
        out.write(self.target_type.builtin_code.format(**env))
        out.write(self.compile_method_with_label(self.toplevel_method, 'OME_toplevel'))
        out.write('\n')

        dispatchers = set()
        for symbol, methods in self.code_table:
            if symbol in self.sent_messages:
                tags = [tag for tag, code in methods]
                out.write(generate_dispatcher(symbol, tags, self.target_type))
                out.write('\n')
                dispatchers.add(symbol)
            for tag, code in methods:
                out.write(code)
                out.write('\n')

        for symbol in self.sent_messages:
            if symbol not in dispatchers:
                sys.stderr.write("Warning: No methods defined for message '%s'\n" % symbol)
                out.write(generate_dispatcher(symbol, [], self.target_type))
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
    out = io.StringIO()
    program.generate_assembly(out)
    asm = out.getvalue()
    #print(asm)
    return asm.encode('utf8')

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
