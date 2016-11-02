# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import io
import platform
import subprocess
import sys

from . import constants
from .ast import Block, BuiltInBlock, Method, Send, Sequence
from .command import command_args
from .dispatcher import generate_dispatcher, generate_lookup_dispatcher
from .error import OmeError
from .idalloc import IdAllocator
from .labels import *
from .parser import Parser
from .target import target_map
from .terminal import stderr
from .types import TraceBackInfo

def collect_nodes_of_type(ast, node_type):
    nodes = []
    def append_block(node):
        if isinstance(node, node_type):
            nodes.append(node)
    ast.walk(append_block)
    return nodes

class Program(object):
    def __init__(self, filename, ast, target):
        self.filename = filename
        self.target = target
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = target.DataTable()
        self.traceback_table = {}
        self.ids = IdAllocator()

        self.builtin_methods = target.get_builtin_methods()
        self.builtin_block = BuiltInBlock()
        self.builtin_block.tag_id = self.ids.tags['BuiltIn']
        self.builtin_block.constant_id = self.ids.constants['BuiltIn']
        self.builtin_block.add_methods(self.builtin_methods)

        ast = Method('', [], ast)
        ast = ast.resolve_free_vars(self.builtin_block)
        ast = ast.resolve_block_refs(self.builtin_block)
        self.toplevel_method = ast
        self.block_list = collect_nodes_of_type(ast, Block)
        self.send_list = collect_nodes_of_type(ast, Send)
        self.ids.allocate_ids(self.block_list)

        toplevel_block = ast.expr
        if isinstance(toplevel_block, Sequence):
            toplevel_block = self.toplevel_block.statements[-1]
        if 'main' not in toplevel_block.symbols:
            self.error('no main method defined')

        self.compile_traceback_info()
        self.find_used_methods()
        self.build_code_table()

    def error(self, message):
        raise OmeError(message, self.filename)

    def warning(self, message):
        stderr.bold()
        stderr.write('{}: '.format(self.filename))
        stderr.colour('magenta')
        stderr.write('warning: ')
        stderr.reset()
        stderr.write(message + '\n')

    def compile_traceback_info(self):
        for send in self.send_list:
            if send.parse_state:
                ps = send.parse_state
                key = (ps.stream_name, ps.line_number, ps.column)
                if key in self.traceback_table:
                    tbinfo = self.traceback_table[key]
                else:
                    line_unstripped = ps.current_line.rstrip()
                    line = line_unstripped.lstrip()
                    column = ps.column - (len(line_unstripped) - len(line))
                    underline = send.symbol.find(':') + 1
                    if underline < 1:
                        underline = max(len(send.symbol), 1)
                    tbinfo = TraceBackInfo(
                        index = len(self.traceback_table),
                        method_name = send.method.symbol,
                        stream_name = ps.stream_name,
                        source_line = line,
                        line_number = ps.line_number,
                        column = column,
                        underline = underline)
                    self.traceback_table[key] = tbinfo
                send.traceback_info = tbinfo

    def find_used_methods(self):
        self.sent_messages = set(['main', 'string'])
        self.sent_messages.update(
            send.symbol for send in self.send_list if send.receiver and not send.receiver_block)

        called_methods = set(
            (send.receiver_block.tag_id, send.symbol) for send in self.send_list
            if send.receiver_block and send.symbol not in self.sent_messages)

        for method in self.builtin_methods:
            if method.tag_name not in self.ids.tags:
                raise OmeError("Unknown tag name '{}' in built-in method '{}'".format(method.tag_name, method.symbol))
            method_tag = self.ids.tags[method.tag_name]
            if method.sent_messages and (method.symbol in self.sent_messages or (method_tag, method.symbol) in called_methods):
                self.sent_messages.update(method.sent_messages)

        self.called_methods = set(
            (send.receiver_block.tag_id, send.symbol) for send in self.send_list
            if send.receiver_block and send.symbol not in self.sent_messages)

    def should_include_method(self, method, tag):
        return method.symbol in self.sent_messages or (tag, method.symbol) in self.called_methods

    def build_code_table(self):
        methods = {}

        for method in self.builtin_methods:
            if self.should_include_method(method, self.builtin_block.tag_id):
                if method.symbol not in methods:
                    methods[method.symbol] = []
                method_tag = self.ids.tags[method.tag_name]
                methods[method.symbol].append((method_tag, method))

        for block in self.block_list:
            for method in block.methods:
                if self.should_include_method(method, block.tag_id):
                    if method.symbol not in methods:
                        methods[method.symbol] = []
                    code = method.generate_code(self)
                    methods[method.symbol].append((block.tag_id, code))

        for symbol in sorted(methods.keys()):
            self.code_table.append((symbol, methods[symbol]))

    def emit_constants(self, out):
        for name, value in sorted(constants.__dict__.items()):
            if isinstance(value, int):
                self.target.emit_constant(out, name, value)
        for name, value in self.ids.tag_list:
            self.target.emit_constant(out, 'Tag_' + name.replace('-', '_'), value)
        self.target.emit_constant(out, 'Pointer_Tag', self.ids.pointer_tag_id)
        for name, value in self.ids.constant_list:
            self.target.emit_constant(out, 'Constant_' + name.replace('-', '_'), value)
        out.write('\n')
        self.target.emit_constant_declarations(out, self.ids.constant_list)

    def emit_data(self, out):
        self.data_table.emit(out)
        out.write('\n')
        traceback_entries = sorted(self.traceback_table.values(), key=lambda tb: tb.index)
        self.target.emit_traceback_table(out, traceback_entries)
        out.write('\n')

    def emit_code_declarations(self, out):
        methods_set = set()
        messages_set = set(self.sent_messages)
        for symbol, methods in self.code_table:
            messages_set.add(symbol)
            for tag, code in methods:
                methods_set.add((tag, symbol))
        self.target.emit_method_declarations(out, sorted(messages_set), sorted(methods_set))
        out.write('\n')

    def emit_code_definitions(self, out):
        self.target.emit_builtin_code(out)
        out.write('\n')

        dispatchers = set()
        for symbol, methods in self.code_table:
            for tag, code in methods:
                out.write(code.generate_target_code(make_method_label(tag, symbol), self.target))
                out.write('\n')
            if symbol in self.sent_messages:
                tags = [tag for tag, code in methods]
                out.write(generate_dispatcher(symbol, tags, self.target))
                out.write('\n')
                out.write(generate_lookup_dispatcher(symbol, tags, self.target))
                out.write('\n')
                dispatchers.add(symbol)

        optional_messages = ['return']
        for symbol in sorted(self.sent_messages):
            if symbol not in dispatchers:
                if symbol not in optional_messages:
                    self.warning("no methods defined for message '%s'" % symbol)
                out.write(generate_dispatcher(symbol, [], self.target))
                out.write('\n')
                out.write(generate_lookup_dispatcher(symbol, [], self.target))
                out.write('\n')

    def emit_toplevel(self, out):
        code = self.toplevel_method.generate_code(self)
        out.write(code.generate_target_code('OME_toplevel', self.target))
        self.target.emit_toplevel(out)

    def emit_program_text(self, out):
        self.emit_constants(out)
        self.emit_data(out)
        self.emit_code_declarations(out)
        self.emit_code_definitions(out)
        self.emit_toplevel(out)

def parse_file(filename):
    try:
        with open(filename) as f:
            source = f.read()
    except FileNotFoundError:
        raise OmeError('file does not exist: ' + filename)
    except UnicodeDecodeError as e:
        raise OmeError('utf-8 decoding failed at position {0.start}: {0.reason}'.format(e), filename)
    except Exception as e:
        raise OmeError(str(e), filename)
    return Parser(source, filename).toplevel()

def compile_file(filename, target):
    ast = parse_file(filename)
    program = Program(filename, ast, target)
    out = io.BytesIO()
    text_out = io.TextIOWrapper(out, encoding=target.encoding, write_through=True)
    program.emit_program_text(text_out)
    code = out.getvalue()
    if command_args.print_code:
        print(code.decode('utf8'))
        sys.exit(0)
    return code

def run_shell_command(args, input=None, output=None):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    process = subprocess.Popen(args,
        stdin = input and subprocess.PIPE,
        stdout = output and subprocess.PIPE)
    outs, errs = process.communicate(input)
    if process.returncode != 0:
        raise OmeError('command failed with return code {}'.format(process.returncode))
    return outs

class BuildShell(object):
    def run(self, *args, input=None):
        run_shell_command(args, input)

    def run_output(self, *args, input=None):
        return run_shell_command(args, input, True)

shell = BuildShell()

class BuildOptions(object):
    def __init__(self, target, debug=False, link=True):
        self.target = target
        self.debug = debug
        self.link = link
        self.include_dirs = []
        self.lib_dirs = []
        self.dynamic_libs = []
        self.static_libs = []
        self.platform = platform.system()
        self.defines = [
            ('OME_PLATFORM', self.platform),
            ('OME_PLATFORM_' + self.platform.upper(), ''),
        ]
        if not debug:
            self.defines.append(('NDEBUG', ''))

    def make_executable(self, filename, backend):
        if self.platform not in backend.supported_platforms:
            raise OmeError("backend '{}' does not support platform {}".format(backend.name, self.platform))
        outfile = backend.executable_name(filename)
        code = compile_file(filename, self.target)
        backend.make_executable(shell, code, outfile, self)

def get_target(target_name):
    if target_name not in target_map:
        raise OmeError("unknown target '{}'".format(target_name))
    return target_map[target_name]

def get_backend(target, backend_name=None):
    if backend_name is None:
        backend_name = target.backend_preference[0]
    if backend_name not in target.backends:
        raise OmeError("unknown backend '{}' for target '{}'".format(backend_name, target.name))
    return target.backends[backend_name]()
