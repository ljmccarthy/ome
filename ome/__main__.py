# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from .command import command_args
from .error import OmeError
from .terminal import stderr

def main():
    stderr.reset()
    try:
        from . import compiler
        target = compiler.get_target(command_args.target)
        build_options = compiler.BuildOptions(target)
        backend = compiler.get_backend(target, command_args.backend)
        if command_args.verbose:
            print('ome: using target {}'.format(target.name))
            print('ome: using backend {} {}'.format(backend.name, backend.version))
        for filename in command_args.filename:
            if command_args.verbose:
                print('ome: compiling {}'.format(filename))
            if command_args.print_code:
                print(compiler.compile_file(filename, target).decode(target.encoding))
            else:
                build_options.make_executable(filename, backend)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('ome: error: please use python 3.x')
    main()
