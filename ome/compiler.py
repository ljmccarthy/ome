# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import io
from . import constants
from .dispatcher import generate_dispatcher, generate_lookup_dispatcher
from .error import OmeError
from .idalloc import IdAllocator
from .ome_ast import Block, BuiltInBlock, Method, Send, Sequence
from .ome_types import CompileOptions, TraceBackInfo
from .parser import Parser
from .terminal import stderr

default_compile_options = CompileOptions()

def collect_nodes_of_type(ast, node_type):
    nodes = []
    def append_block(node):
        if isinstance(node, node_type):
            nodes.append(node)
    ast.walk(append_block)
    return nodes

def make_send_traceback_info(send, index):
    ps = send.parse_state
    line_unstripped = ps.current_line.rstrip()
    line = line_unstripped.lstrip()
    column = ps.column - (len(line_unstripped) - len(line))
    underline = send.symbol.find(':') + 1
    if underline < 1:
        underline = max(len(send.symbol), 1)
    return TraceBackInfo(
        index = index,
        method_name = send.method.symbol,
        stream_name = ps.stream_name,
        source_line = line,
        line_number = ps.line_number,
        column = column,
        underline = underline)

class Program(object):
    def __init__(self, ast, target, filename='', options=default_compile_options):
        self.target = target
        self.filename = filename
        self.options = options
        self.code_table = []  # list of (symbol, [list of (tag, method)])
        self.data_table = target.DataTable()
        self.traceback_table = {}
        self.builtin = target.get_builtin()
        self.ids = IdAllocator(self.builtin)

        self.builtin_block = BuiltInBlock(self.builtin.methods)
        self.builtin_block.tag_id = self.ids.tags['BuiltIn']
        self.builtin_block.constant_id = self.ids.constants['BuiltIn']

        ast = Method('', [], ast)
        ast = ast.resolve_free_vars(self.builtin_block)
        ast = ast.resolve_block_refs(self.builtin_block)
        self.toplevel_method = ast
        self.send_list = collect_nodes_of_type(ast, Send)
        self.block_list = collect_nodes_of_type(ast, Block)
        self.ids.allocate_block_ids(self.block_list)

        self.message('allocated {} tag IDs, {} constant IDs'.format(
            self.ids.num_tag_ids, self.ids.num_constant_ids))

        toplevel_block = ast.expr
        if isinstance(toplevel_block, Sequence):
            toplevel_block = self.toplevel_block.statements[-1]
        if 'main' not in toplevel_block.symbols:
            self.error('no main method defined')

        if self.options.traceback:
            self.compile_traceback_info()

        self.find_used_methods()
        self.build_code_table()

    def message(self, message):
        if self.options.verbose:
            print('ome:', message)

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
                    tbinfo = make_send_traceback_info(send, len(self.traceback_table))
                    self.traceback_table[key] = tbinfo
                send.traceback_info = tbinfo

    def find_used_methods(self):
        self.sent_messages = set(['main', 'string'])
        self.sent_messages.update(
            send.symbol for send in self.send_list if send.receiver and not send.receiver_block)

        called_methods = set(
            (send.receiver_block.tag_id, send.symbol) for send in self.send_list
            if send.receiver_block and send.symbol not in self.sent_messages)

        for method in self.builtin.messages:
            if method.sent_messages and method.symbol in self.sent_messages:
                self.sent_messages.update(method.sent_messages)

        for symbol in list(self.sent_messages):
            if symbol in self.builtin.defaults:
                self.sent_messages.update(self.builtin.defaults[symbol].sent_messages)

        for method in self.builtin.methods:
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

        for method in self.builtin.methods:
            method_tag = self.ids.tags[method.tag_name]
            if self.should_include_method(method, method_tag):
                if method.symbol not in methods:
                    methods[method.symbol] = []
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
        for name in self.ids.tag_names:
            self.target.emit_constant(out, 'Tag_' + name.replace('-', '_'), self.ids.tags[name])
        self.target.emit_constant(out, 'Pointer_Tag', self.ids.pointer_tag_id)
        for name in self.ids.constant_names:
            self.target.emit_constant(out, 'Constant_' + name.replace('-', '_'), self.ids.constants[name])
        out.write('\n')
        self.target.emit_builtin_header(out, self.builtin)
        out.write('\n')

    def emit_data(self, out):
        self.data_table.emit(out)
        out.write('\n')
        if self.options.traceback:
            traceback_entries = sorted(self.traceback_table.values(), key=lambda tb: tb.index)
            self.target.emit_traceback_table(out, traceback_entries, self.options.source_traceback)
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

    def emit_dispatcher(self, out, symbol, tags):
        has_default_method = symbol in self.builtin.defaults
        if has_default_method:
            out.write(self.target.generate_default_method(self.builtin.defaults[symbol]))
            out.write('\n')
        out.write(generate_dispatcher(symbol, tags, has_default_method, self.target))
        out.write('\n')
        out.write(generate_lookup_dispatcher(symbol, tags, has_default_method, self.target))
        out.write('\n')

    def emit_code_definitions(self, out):
        self.target.emit_builtin_code(out)
        out.write('\n')
        for s in self.builtin.code:
            out.write(s)

        dispatchers = set()
        for method in self.builtin.messages:
            if method.symbol in self.sent_messages:
                out.write(method.generate_target_code(self.target.make_message_label(method.symbol), self.target))
                out.write('\n')
                dispatchers.add(method.symbol)

        for symbol, methods in self.code_table:
            for tag, code in methods:
                out.write(code.generate_target_code(self.target.make_method_label(tag, symbol), self.target))
                out.write('\n')
            if symbol in self.sent_messages:
                tags = [tag for tag, code in methods]
                self.emit_dispatcher(out, symbol, tags)
                dispatchers.add(symbol)

        optional_messages = frozenset(['return', 'catch', 'catch:'])
        for symbol in sorted(self.sent_messages):
            if symbol not in dispatchers:
                if symbol not in optional_messages and symbol not in self.builtin.defaults:
                    self.warning("no methods defined for message '%s'" % symbol)
                self.emit_dispatcher(out, symbol, [])

    def emit_toplevel(self, out):
        code = self.toplevel_method.generate_code(self)
        out.write(code.generate_target_code('OME_toplevel', self.target))
        out.write('\n')
        self.target.emit_builtin_main(out)

    def emit_program_text(self, out):
        self.emit_constants(out)
        self.emit_data(out)
        self.emit_code_declarations(out)
        self.emit_code_definitions(out)
        self.emit_toplevel(out)

    def get_program_text(self):
        out = io.BytesIO()
        text_out = io.TextIOWrapper(out, encoding=self.target.encoding, write_through=True)
        self.emit_program_text(text_out)
        return out.getvalue()

def parse_string(string, filename='<string>'):
    return Parser(string, filename).toplevel()

def parse_file(filename):
    try:
        with open(filename) as f:
            source = f.read()
    except FileNotFoundError:
        raise OmeError('file does not exist', filename)
    except UnicodeDecodeError as e:
        raise OmeError('utf-8 decoding failed at position {0.start}: {0.reason}'.format(e), filename)
    except Exception as e:
        raise OmeError(str(e), filename)
    return parse_string(source, filename)

def compile_ast(ast, target, filename, options):
    return Program(ast, target, filename, options).get_program_text()

def compile_string(string, target, filename='<string>', options=default_compile_options):
    return compile_ast(parse_string(string, filename), target, filename, options)

def compile_file(filename, target, options=default_compile_options):
    return compile_ast(parse_file(filename), target, filename, options)
