# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .backend_clang import ClangBuilder
from .backend_gcc import GCCBuilder
from .builtin import *
from .codegen import *

target_id = ('c', 'linux')

default_builder = 'clang'

builders = {
    'clang': ClangBuilder(),
    'gcc': GCCBuilder(),
}
