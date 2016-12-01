# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import glob
import hashlib
import os
import platform
import sys
import time
from . import build
from . import compiler
from . import optimise
from .build_shell import BuildShell
from .command import argparser
from .error import OmeError
from .ome_ast import BuiltInBlock, format_sexpr
from .package import SourcePackageBuilder
from .terminal import stderr
from .util import get_terminal_width, get_cache_dir
from .version import version

class OmeApp(object):
    def __init__(self, args):
        self.start = time.time()
        self.args = args
        self.package_dir = os.path.join(get_cache_dir('ome'), 'libs')
        self.target = build.get_target(args.target)
        self.backend = build.get_backend(self.target, args.platform, args.backend, args.backend_command)
        self.prefix_dir = self.get_prefix_dir(self.backend.command)
        self.options = build.get_build_options_from_command(args)
        self.options.include_dirs.append(os.path.join(self.prefix_dir, 'include'))
        self.options.library_dirs.append(os.path.join(self.prefix_dir, 'lib'))
        self.shell = BuildShell(args.show_build_commands)
        self.verbose = args.verbose

    def get_prefix_dir(self, command):
        m = hashlib.md5()
        m.update(command.encode('utf8'))
        return os.path.join(self.package_dir, m.hexdigest())

    def print_verbose(self, *args):
        if self.verbose:
            print('ome:', *args)

    def print_version(self):
        print('ome version {}.{}.{}'.format(*version))
        sys.exit()

    def check_args(self):
        if self.args.backend_command and not self.args.backend:
            raise OmeError('--backend must be specified with --backend-command')
        if len(self.args.file) == 0:
            raise OmeError('no input files')
        if len(self.args.file) > 1:
            raise OmeError('too many input files')
        self.args.infile = self.args.file[0]
        if not self.args.output:
            self.args.output = self.backend.output_name(self.args.infile, self.options)
            if self.args.infile == self.args.output:
                raise OmeError('input file name is same as output')

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
        if self.target.packages:
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

        self.print_verbose('using target {}'.format(self.target.name))
        self.print_verbose('using backend {} {}'.format(self.backend.name, self.backend.version))

        self.build_packages()

        self.print_verbose('compiling {}'.format(self.args.infile))
        compile_start = time.time()
        input = compiler.compile_file(self.args.infile, self.target, self.options)
        self.print_verbose('frontend compilation completed in %.2fs' % (time.time() - compile_start))

        self.print_verbose('building output', self.args.output)
        build_start = time.time()
        self.backend.build_string(self.shell, input, self.args.output, self.options)
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
