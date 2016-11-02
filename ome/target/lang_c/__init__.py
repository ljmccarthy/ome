# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from .backend_clang import ClangBuilder
from .backend_gcc import GCCBuilder
from .builtin import *
from .codegen import *

name = 'C'

backends = {
    'clang': ClangBuilder,
    'gcc': GCCBuilder,
}

backend_preference = ['clang', 'gcc']
