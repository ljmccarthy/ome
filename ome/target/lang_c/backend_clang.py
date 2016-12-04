# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os
from ...error import OmeError
from .backend_cc import CCArgsBuilder, CCBuilder

class ClangArgsBuilder(CCArgsBuilder):
    cc_args = [
        '-x', 'c',
        '-std=c99',
        '-Wall',
        '-Wextra',
        '-Wno-unused',
        '-Wno-unused-parameter',
        '-Wstrict-aliasing',
        '-fstrict-aliasing',
        '-fno-asynchronous-unwind-tables',
        '-fPIC',
        '-pthread',
        '-Qunused-arguments',
    ]
    link_args = [
        '-pthread',
        '-Qunused-arguments',
    ]
    variant_cc_args = {
        'release': ['-O3', '-fomit-frame-pointer'],
        'fast': ['-O0'],
        'debug': ['-O0', '-ggdb']
    }
    variant_link_args = {
        ('linux', 'release'): ['-Wl,--gc-sections']
    }

    def get_musl_args(self, build_options, musl_path, linking):
        if not build_options.static:
            raise OmeError('to use musl with clang please specify --static or --backend-command=musl-clang without --use-musl')
        args = []
        tail_args = []
        args.append('-B' + musl_path)
        args.append('--sysroot')
        args.append(musl_path)
        if linking:
            args.append('-static-libgcc')
            args.append('-L-user-start')
            tail_args.append('-L' + os.path.join(musl_path, 'lib'))
            tail_args.append('-L-user-end')
        else:
            args.append('-nostdinc')
            args.append('-isystem')
            args.append(os.path.join(musl_path, 'include'))
        return args, tail_args

class ClangBuilder(CCBuilder):
    name = 'clang'
    default_command = 'clang'
    supported_platforms = frozenset(['linux', 'darwin'])
    version_args = ['--version']
    version_re = '(?:clang|Apple LLVM) version (\d+\.\d+\.\d+)'
    get_build_args = ClangArgsBuilder()
