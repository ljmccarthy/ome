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
    ]
    variant_cc_args = {
        'release': ['-O3', '-fomit-frame-pointer'],
        'fast': ['-O0'],
        'debug': ['-O0', '-ggdb']
    }
    variant_link_args = {
        'release': [
            '-Wl,--strip-all',
            '-Wl,--gc-sections',
        ]
    }

    def get_musl_args(self, build_options, musl_path):
        if not build_options.static:
            raise OmeError('to use musl with clang please specify --static or --backend-command=musl-clang')
        args = []
        tail_args = []
        args.append('-B' + musl_path)
        args.append('-static-libgcc')
        args.append('-nostdinc')
        args.append('--sysroot')
        args.append(musl_path)
        args.append('-isystem')
        args.append(os.path.join(musl_path, 'include'))
        args.append('-L-user-start')
        if build_options.libraries:
            args.append('-l-user-start')
            tail_args.append('-l-user-end')
        tail_args.append('-L' + os.path.join(musl_path, 'lib'))
        tail_args.append('-L-user-end')
        return args, tail_args

class ClangBuilder(CCBuilder):
    name = 'clang'
    default_command = 'clang'
    supported_platforms = frozenset(['linux'])
    version_args = ['--version']
    version_re = 'clang version (\d+\.\d+\.\d+)'
    get_build_args = ClangArgsBuilder()
