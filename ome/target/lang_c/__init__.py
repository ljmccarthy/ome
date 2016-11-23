# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from .backend_clang import ClangBuilder
from .backend_gcc import GCCBuilder
from .backend_file import FileBuilder
from .builtin import *
from .codegen import *
from .packages import packages

name = 'C'

backends = {
    'clang': ClangBuilder,
    'gcc': GCCBuilder,
    'file': FileBuilder,
}

backend_preference = ['clang', 'gcc']
