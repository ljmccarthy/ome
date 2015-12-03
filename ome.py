#!/usr/bin/env python3
#
# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import sys
from ome.compiler import compile_file, Error

def main():
    if len(sys.argv) != 2:
        sys.exit('usage: python ome.py <infile.ome>')
    else:
        try:
            compile_file(sys.argv[1])
        except Error as e:
            sys.exit(str(e))

if __name__ == '__main__':
    if sys.version_info[0] < 3:
        sys.exit('Please run in Python 3')
    main()
