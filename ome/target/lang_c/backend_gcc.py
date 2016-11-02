# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

from .backend_cc import CCArgsBuilder, CCBuilder

class GCCArgsBuilder(CCArgsBuilder):
    all = [
        '-x', 'c',
        '-std=c99',
        '-Wall',
        '-Wextra',
        '-Wno-unused',
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

class GCCBuilder(CCBuilder):
    name = 'GCC'
    default_command = 'gcc'
    supported_platforms = frozenset(['Linux'])
    version_args = ['--version']
    version_re = 'gcc \(GCC\) (\d+\.\d+\.\d+)'
    get_build_args = GCCArgsBuilder()
