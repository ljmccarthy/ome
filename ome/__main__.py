# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import sys
from . import build
from .command import command_args, print_verbose
from .compiler import compile_file
from .error import OmeError
from .terminal import stderr
from .version import version

def main():
    stderr.reset()
    try:
        if command_args.version:
            print('ome version {}.{}.{}'.format(*version))
            sys.exit()

        if command_args.backend_command and not command_args.backend:
            raise OmeError('--backend must be specified with --backend-command')

        target = build.get_target(command_args.target)
        options = build.BuildOptions(target, command_args)
        backend = build.get_backend(target, command_args.platform, command_args.backend, command_args.backend_command)

        print_verbose('ome: using target {}'.format(target.name))
        print_verbose('ome: using backend {} {}'.format(backend.name, backend.version))

        if len(command_args.file) == 0:
            raise OmeError('no input files')
        if len(command_args.file) > 1:
            raise OmeError('too many input files')

        filename = command_args.file[0]
        outfile = command_args.output or backend.output_name(filename, options)
        print_verbose('ome: compiling {}'.format(filename))
        input = compile_file(filename, target, options)
        if command_args.print_code:
            print(input.decode(target.encoding))
        else:
            options.make_output(input, outfile, backend)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    main()
