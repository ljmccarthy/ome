# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import glob
import hashlib
import os
import sys
import time
from . import build
from . import compiler
from . import optimise
from .build_options import get_build_options_from_command
from .build_shell import BuildShell
from .command import argparser
from .error import OmeError
from .ome_ast import BuiltInBlock, format_sexpr
from .package import SourcePackageBuilder
from .terminal import stderr
from .util import get_terminal_width, get_cache_dir, find_executable
from .version import version

def get_backend_tool(args):
    tools = {}
    for tool in args.backend_tool:
        if '=' not in tool:
            raise OmeError('--backend-tool {} does not specify tool path'.format(tool))
        name, command = tool.split('=', 1)
        name = name.upper()
        if not os.path.isabs(command):
            command = find_executable(command)
            if not command:
                raise OmeError('executable not found: {}'.format(command))
        tools[name] = command
    return tools

class OmeApp(object):
    def __init__(self, args):
        self.start = time.time()
        self.args = args
        self.package_dir = os.path.join(get_cache_dir('ome'), 'libs')
        self.target = build.get_target(self.args.target)
        self.options = get_build_options_from_command(self.args)
        self.shell = BuildShell(self.args.show_build_commands)

    def initialize_backend(self):
        self.backend = build.get_backend(self.target, self.args.platform, self.args.backend, get_backend_tool(self.args))
        self.prefix_dir = self.get_prefix_dir(self.backend.tools)
        self.options.include_dirs.append(os.path.join(self.prefix_dir, 'include'))
        self.options.library_dirs.append(os.path.join(self.prefix_dir, 'lib'))

    def get_prefix_dir(self, tools):
        s = '\0'.join('{}={}'.format(*tool) for tool in sorted(tools.items()))
        m = hashlib.md5()
        m.update(s.encode('utf8'))
        return os.path.join(self.package_dir, m.hexdigest())

    def print_verbose(self, *args):
        if self.args.verbose:
            print('ome:', *args)

    def print_version(self):
        print('ome version {}.{}.{}'.format(*version))
        sys.exit()

    def check_args(self):
        if self.args.backend_tool and not self.args.backend:
            raise OmeError('--backend must be specified when --backend-tool is used')
        if len(self.args.file) == 0:
            raise OmeError('no input files')
        if len(self.args.file) > 1:
            raise OmeError('too many input files')
        self.args.infile = self.args.file[0]

    def get_output(self):
        if not self.args.output:
            self.args.output = self.backend.output_name(self.args.infile, self.options)
            if self.args.infile == self.args.output:
                raise OmeError('input file name is same as output')
        return self.args.output

    def print_ast(self, filename):
        ast = compiler.parse_file(filename)
        print(format_sexpr(ast.sexpr(), max_width=get_terminal_width()))

    def print_resolved_ast(self, filename):
        builtin_block = BuiltInBlock(self.target.get_builtin().methods)
        ast = compiler.parse_file(filename)
        ast = ast.resolve_free_vars(builtin_block)
        ast = ast.resolve_block_refs(builtin_block)
        print(format_sexpr(ast.sexpr(), max_width=get_terminal_width()))

    def print_intermediate_code(self, filename):
        ast = compiler.parse_file(filename)
        program = compiler.Program(ast, self.target, '', self.options)
        for block in sorted(program.block_list, key=lambda block: block.tag_id):
            for method in sorted(block.methods, key=lambda method: method.symbol):
                print('{}:'.format(self.target.make_method_label(block.tag_id, method.symbol)))
                code = method.generate_code(program)
                code.instructions = optimise.eliminate_aliases(code.instructions)
                code.instructions = optimise.move_constants_to_usage_points(code.instructions, code.num_args)
                optimise.renumber_locals(code.instructions, code.num_args)
                for ins in code.instructions:
                    print('    ' + str(ins))

    def print_target_code(self, filename):
        code = compiler.compile_file(filename, self.target, self.options)
        print(code.decode(self.target.encoding))

    def print_command(self, filename):
        if self.args.print_ast:
            self.print_ast(filename)
        elif self.args.print_resolved_ast:
            self.print_resolved_ast(filename)
        elif self.args.print_intermediate_code:
            self.print_intermediate_code(filename)
        elif self.args.print_target_code:
            self.print_target_code(filename)
        else:
            return
        sys.exit()

    def build_packages(self):
        libraries = []
        if self.backend.build_packages and self.target.packages:
            self.print_verbose('building packages')
            sources_dir = os.path.join(self.package_dir, 'sources')
            package_builder = SourcePackageBuilder(sources_dir, self.prefix_dir, self.backend)
            package_builder.build_packages(self.target.packages)
            libraries = glob.glob(os.path.join(self.prefix_dir, 'lib', '*' + self.backend.lib_extension))
            self.options.objects.extend(libraries)
        return libraries

    def main(self):
        stderr.reset()

        if self.args.version:
            self.print_version()

        self.check_args()
        self.print_command(self.args.infile)
        self.initialize_backend()
        output = self.get_output()

        self.print_verbose('using target {}'.format(self.target.name))
        self.print_verbose('using backend {} {}'.format(self.backend.name, self.backend.version))

        self.build_packages()

        self.print_verbose('compiling {}'.format(self.args.infile))
        compile_start = time.time()
        input = compiler.compile_file(self.args.infile, self.target, self.options)
        self.print_verbose('frontend compilation completed in %.2fs' % (time.time() - compile_start))

        self.print_verbose('building output', output)
        build_start = time.time()
        self.backend.build_string(self.shell, input, output, self.options)
        self.print_verbose('backend build completed in %.2fs' % (time.time() - build_start))

        self.print_verbose('completed in %.2fs' % (time.time() - self.start))

def main():
    try:
        app = OmeApp(argparser.parse_args())
        app.main()
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()
