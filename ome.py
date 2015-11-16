# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from ome.compiler import compile_file, Error

def main():
    if len(sys.argv) != 2:
        sys.stderr.write('usage: python ome.py <infile.ome>')
    else:
        try:
            compile_file(sys.argv[1])
        except Error as e:
            sys.stderr.write('%s\n' % e)
            sys.exit(1)

if __name__ == '__main__':
    main()
