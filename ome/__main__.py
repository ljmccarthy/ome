# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from .error import OmeError

def main():
    if len(sys.argv) != 2:
        sys.exit('usage: ome <infile.ome>')
    else:
        try:
            from .compiler import compile_file
            compile_file(sys.argv[1])
        except OmeError as e:
            sys.exit(str(e))

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('Please use Python 3')
    main()
