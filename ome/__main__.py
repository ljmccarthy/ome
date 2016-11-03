# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import sys
from .command import command_args
from .error import OmeError
from .terminal import stderr
from .version import version

def print_verbose(*args, **kwargs):
    if command_args.verbose:
        print(*args, **kwargs)

def main():
    stderr.reset()
    try:
        if command_args.version:
            print('ome version {}.{}.{}'.format(*version))
            sys.exit()
        if not command_args.file:
            raise OmeError('no input files')
        from . import compiler
        target = compiler.get_target(command_args.target)
        platform = command_args.platform
        build_options = compiler.BuildOptions(target, command_args)
        backend = compiler.get_backend(target, platform, command_args.backend, command_args.backend_command)
        print_verbose('ome: using target {}'.format(target.name))
        print_verbose('ome: using backend {} {}'.format(backend.name, backend.version))
        print_verbose('ome: compiling {}'.format(command_args.file))
        if command_args.print_code:
            print(compiler.compile_file(command_args.file, target).decode(target.encoding))
        else:
            build_options.make_output(command_args.file, backend)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('ome: error: please use python 3.x')
    main()
