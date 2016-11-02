# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from .backend_cc import CCArgsBuilder, CCBuilder

class ClangArgsBuilder(CCArgsBuilder):
    all = [
        '-x', 'c',
        '-std=c99',
        '-Wall',
        '-Wextra',
        '-Wno-unused',
        '-Wno-unused-parameter',
    ]
    release = [
        '-O3',
    ]
    debug = [
        '-ggdb',
    ]
    release_link = [
        '-Wl,--strip-all',
        '-Wl,--gc-sections',
    ]

class ClangBuilder(CCBuilder):
    name = 'Clang'
    default_command = 'clang'
    supported_platforms = frozenset(['Linux'])
    version_args = ['--version']
    version_re = 'clang version (\d+\.\d+\.\d+)'
    get_build_args = ClangArgsBuilder()
