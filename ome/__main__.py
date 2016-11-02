# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from argparse import ArgumentParser
from .error import OmeError
from .terminal import stdout, stderr

argparser = ArgumentParser('ome', add_help=False)
argparser.add_argument('filename', nargs='+')
argparser.add_argument('--verbose', '-v', action='store_true')

def main():
    args = argparser.parse_args()
    stderr.reset()
    try:
        from .compiler import make_executable
        for filename in args.filename:
            if args.verbose:
                stdout.write('ome: compiling {}\n'.format(filename))
            make_executable(filename)
    except OmeError as error:
        error.write_ansi(stderr)
        stderr.reset()
        sys.exit(1)

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('ome: error: please use python 3.x')
    main()
