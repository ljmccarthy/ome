# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import sys
import time
from . import build
from . import compiler
from . import optimise
from .ast import BuiltInBlock
from .command import command_args, print_verbose
from .error import OmeError
from .terminal import stderr
from .version import version

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
        options = build.BuildOptions(target, command_args)
        backend = build.get_backend(target, command_args.platform, command_args.backend, command_args.backend_command)

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
            print(ast)
            sys.exit()

        if command_args.print_resolved_ast:
            builtin_block = BuiltInBlock(target.get_builtin().methods)
            ast = ast.resolve_free_vars(builtin_block)
            ast = ast.resolve_block_refs(builtin_block)
            print(ast)
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

        print_verbose('building output', outfile)
        build_start_time = time.time()
        options.make_output(input, outfile, backend)
        build_time = time.time() - build_start_time
        print_verbose('backend build completed in %.2fs' % build_time)

        total_time = time.time() - start_time
        print_verbose('completed in %.2fs' % total_time)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    main()
