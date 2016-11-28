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
from .command import command_args, print_verbose
from .error import OmeError
from .ome_ast import BuiltInBlock, format_sexpr
from .package import SourcePackageBuilder
from .terminal import stderr
from .version import version

if platform.system() == 'Darwin':
    package_dir = os.path.expanduser(os.path.join('~', 'Library', 'Caches' 'ome', 'libs'))
else:
    package_dir = os.path.expanduser(os.path.join('~', '.cache', 'ome', 'libs'))

def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80

def get_prefix_dir(command):
    m = hashlib.md5()
    m.update(command.encode('utf8'))
    return os.path.join(package_dir, m.hexdigest())

def main():
    start_time = time.time()
    stderr.reset()
    try:
        if command_args.version:
            print('ome version {}.{}.{}'.format(*version))
            sys.exit()

        if command_args.backend_command and not command_args.backend:
            raise OmeError('--backend must be specified with --backend-command')

        compile_start_time = time.time()

        target = build.get_target(command_args.target)
        backend = build.get_backend(target, command_args.platform, command_args.backend, command_args.backend_command)

        prefix_dir = get_prefix_dir(backend.command)
        options = build.BuildOptions(target, command_args)
        options.include_dirs.append(os.path.join(prefix_dir, 'include'))
        options.library_dirs.append(os.path.join(prefix_dir, 'lib'))

        print_verbose('using target {}'.format(target.name))
        print_verbose('using backend {} {}'.format(backend.name, backend.version))

        if len(command_args.file) == 0:
            raise OmeError('no input files')
        if len(command_args.file) > 1:
            raise OmeError('too many input files')

        filename = command_args.file[0]
        outfile = command_args.output or backend.output_name(filename, options)
        print_verbose('compiling {}'.format(filename))

        ast = compiler.parse_file(filename)
        if command_args.print_ast:
            print(format_sexpr(ast.sexpr(), max_width=get_terminal_width()))
            sys.exit()

        if command_args.print_resolved_ast:
            builtin_block = BuiltInBlock(target.get_builtin().methods)
            ast = ast.resolve_free_vars(builtin_block)
            ast = ast.resolve_block_refs(builtin_block)
            print(format_sexpr(ast.sexpr(), max_width=get_terminal_width()))
            sys.exit()

        if command_args.print_intermediate_code:
            program = compiler.Program(ast, target, filename, options)
            for block in sorted(program.block_list, key=lambda block: block.tag_id):
                for method in sorted(block.methods, key=lambda method: method.symbol):
                    print('{}:'.format(target.make_method_label(block.tag_id, method.symbol)))
                    code = method.generate_code(program)
                    code.instructions = optimise.eliminate_aliases(code.instructions)
                    code.instructions = optimise.move_constants_to_usage_points(code.instructions, code.num_args)
                    optimise.renumber_locals(code.instructions, code.num_args)
                    for ins in code.instructions:
                        print('    ' + str(ins))
            sys.exit()

        input = compiler.compile_ast(ast, target, filename, options)
        compile_time = time.time() - compile_start_time
        print_verbose('frontend compilation completed in %.2fs' % compile_time)

        if command_args.print_target_code:
            print(input.decode(target.encoding))
            sys.exit()

        if target.packages:
            print_verbose('building packages')
            sources_dir = os.path.join(package_dir, 'sources')
            package_builder = SourcePackageBuilder(sources_dir, prefix_dir, backend)
            package_builder.build_packages(target.packages)
            for lib in glob.glob(os.path.join(prefix_dir, 'lib', '*' + backend.lib_extension)):
                options.objects.append(lib)

        print_verbose('building output', outfile)
        build_start_time = time.time()
        shell = BuildShell(command_args.show_build_commands)
        backend.make_output(shell, input, outfile, options)
        build_time = time.time() - build_start_time
        print_verbose('backend build completed in %.2fs' % build_time)

        total_time = time.time() - start_time
        print_verbose('completed in %.2fs' % total_time)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()
