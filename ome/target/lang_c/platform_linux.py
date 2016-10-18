# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ...ast import BuiltInMethod
from .builtin import *
from .codegen import *

platform = ('C', 'Linux')

def get_assembler_args(outfile):
    return ['gcc', '-c', '-x', 'c', '-std=c99', '-Wall', '-Wno-unused', '-', '-o', outfile]

def get_linker_args(infile, outfile):
    return ['gcc', '-Wl,--strip-all', '-Wl,--gc-sections', '-o', outfile, infile]
