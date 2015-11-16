# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import io
import os
import re
import struct
import subprocess
import sys

from .ast import Method, Sequence, TopLevelBlock
from .constants import *
from .emit import ProcedureCodeEmitter
from .instructions import LOAD_STRING
from .labels import *
from .parser import Parser
from .target_x86_64 import Target_x86_64

def generate_assembly_code(emit, code, target_type, data_table):
    target = target_type(emit)
    target.emit_enter(code.num_stack_slots)
    for ins in code.instructions:
        if isinstance(ins, LOAD_STRING):
            ins.data_label = data_table.allocate_string(ins.string)
        ins.emit(target)
    target.emit_leave(code.num_stack_slots)

def split_tag_range(target, label_format, tags, exit_label, min_tag, max_tag):
    target.emit.comment('[0x%x..0x%x]', min_tag, max_tag)
    if len(tags) == 1:
        tag = tags[0]
        if min_tag == tag and max_tag == tag:
            target.emit_jump(label_format % tag)
        else:
            target.emit_dispatch_compare_eq(tag, label_format % tag, exit_label)
    else:
        middle = len(tags) // 2
        middle_label = '.tag_ge_%X' % tags[middle]
        target.emit_dispatch_compare_gte(tags[middle], middle_label)
        split_tag_range(target, label_format, tags[:middle], exit_label, min_tag, tags[middle] - 1)
        target.emit.label(middle_label)
        split_tag_range(target, label_format, tags[middle:], exit_label, tags[middle], max_tag)

def generate_dispatcher(symbol, tags, target_type):
    tags = sorted(tags)
    any_constant_tags = any(tag > MAX_TAG for tag in tags)
    emit = ProcedureCodeEmitter(make_send_label(symbol))
    target = target_type(emit)
    target.emit_dispatch(any_constant_tags)
    split_tag_range(target, make_call_label_format(symbol), tags, '.not_understood', 0, 1 << NUM_DATA_BITS)
    return emit.get_output()

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
            padding = b'\0' * (8 - (len(string) & 7))  # nul termination padding
            data = struct.pack('Q', len(string)) + string.encode('utf8') + padding
            self.string_offsets[string] = self.append_data(data)
        return '(OME_data+%s)' % self.string_offsets[string]

    def generate_assembly(self, f):
        f.write('align 8\nOME_data:\n')
        for data in self.data:
             f.write('\tdb ' + ','.join('%d' % byte for byte in data) + '\n')
        f.write('.end:\n')

class Program(object):
    def __init__(self, ast, target_type):
        self.toplevel_method = ast
        self.toplevel_block = ast.expr
        if isinstance(self.toplevel_block, Sequence):
            self.toplevel_block = self.toplevel_block.statements[-1]

        self.target_type = target_type
        self.block_list = []
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = DataTable()

        if 'main' not in self.toplevel_block.symbols:
            raise Error('Error: No main method defined')

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
        emit = ProcedureCodeEmitter(label)
        code = method.generate_code(self.target_type)
        generate_assembly_code(emit, code, self.target_type, self.data_table)
        return emit.get_output()

    def compile_method(self, method, tag):
        return self._compile_method(method, make_call_label(tag, method.symbol))

    def build_code_table(self):
        methods = {}
        for method in self.target_type.builtin_methods:
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
            print('MESSAGE %s {' % symbol)
            for tag, code in methods:
                print('    TAG $%X {' % tag)
                for i, instruction in enumerate(code.instructions):
                    if instruction.label:
                        print('    .%s:' % instruction.label)
                    print('        %s' % instruction)
                print('    }')
            print('}')

    def generate_assembly(self, f):
        f.write('bits 64\n\nsection .text\n\n')

        main_label = make_call_label(get_block_tag(self.toplevel_block), 'main')
        env = {
            'MAIN': main_label,
            'NUM_TAG_BITS': NUM_TAG_BITS,
            'NUM_DATA_BITS': NUM_DATA_BITS,
        }
        f.write(self.target_type.builtin_code.format(**env))
        f.write(self._compile_method(self.toplevel_method, 'OME_toplevel'))
        f.write('\n')

        for symbol, methods in self.code_table:
            tags = [tag for tag, code in methods]
            f.write(generate_dispatcher(symbol, tags, self.target_type))
            f.write('\n')
            for tag, code in methods:
                f.write(code)
                f.write('\n')

        f.write('section .rodata\n\n')
        self.data_table.generate_assembly(f)
        f.write('\n')
        f.write(self.target_type.builtin_data)

def parse_file(filename):
    with open(filename) as f:
        source = f.read()
    return Parser(source, filename).toplevel()

def compile_file_to_assembly(filename, target_type):
    toplevel = TopLevelBlock(target_type)
    ast = parse_file(filename)
    ast = Method('', [], ast)
    ast = ast.resolve_free_vars(toplevel)
    ast = ast.resolve_block_refs(toplevel)
    program = Program(ast, target_type)
    #program.print_code_table()
    out = io.StringIO()
    program.generate_assembly(out)
    return out.getvalue().encode('utf8')

def run_assembler(input, outfile):
    p = subprocess.Popen(['yasm', '-f', 'elf64', '-o', outfile, '-'], stdin=subprocess.PIPE)
    p.communicate(input)

def run_linker(infile, outfile):
    p = subprocess.Popen(['ld', '-s', '-o', outfile, infile])
    p.communicate()

def compile_file(filename, target_type=Target_x86_64):
    asm = compile_file_to_assembly(filename, target_type)
    exe_file = os.path.splitext(filename)[0]
    obj_file = exe_file + '.o'
    run_assembler(asm, obj_file)
    run_linker(obj_file, exe_file)
