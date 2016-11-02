# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from .command import command_args
from .error import OmeError
from .terminal import stdout, stderr

def main():
    stderr.reset()
    try:
        from . import compiler
        target = compiler.get_target(command_args.target.lower())
        build_options = compiler.BuildOptions(target)
        backend = compiler.get_backend(target, command_args.backend)
        if command_args.verbose:
            print('ome: using target {}'.format(target.name))
            print('ome: using backend {}'.format(backend.name))
        for filename in command_args.filename:
            if command_args.verbose:
                stdout.write('ome: compiling {}\n'.format(filename))
            build_options.make_executable(filename, backend)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('ome: error: please use python 3.x')
    main()
