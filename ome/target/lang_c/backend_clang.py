# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import os
from .backend_cc import get_cc_args

clang = 'clang'

clang_args = [
    '-x', 'c',
    '-std=c99',
    '-Wall',
    '-Wextra',
    '-Wno-unused',
    '-Wno-unused-parameter',
]

clang_release_args = [
    '-O3',
]

clang_debug_args = [
    '-ggdb',
]

clang_release_link_args = [
    '-Wl,--strip-all',
    '-Wl,--gc-sections',
]

def get_clang_args(build_options):
    args = []
    if not build_options.link:
        args.append('-c')
    args.extend(clang_args)
    if build_options.debug:
        args.extend(clang_debug_args)
    else:
        args.extend(clang_release_args)
        if build_options.link:
            args.extend(clang_release_link_args)
    get_cc_args(build_options, args)
    return args

class ClangBuilder(object):
    name = 'Clang'
    default_command = 'clang'
    supported_platforms = frozenset(['Linux'])
    version_args = ['--version']
    version_re = 'clang version (\d+\.\d+\.\d+)'

    def __init__(self, command):
        self.command = command

    def executable_name(self, infile):
        return os.path.splitext(infile)[0]

    def object_name(self, infile):
        return os.path.splitext(infile)[0] + '.o'

    def make_executable(self, shell, code, outfile, build_options):
        build_args = get_clang_args(build_options)
        shell.run([self.command] + build_args + ['-', '-o', outfile], input=code)
        if not build_options.debug:
            shell.run('strip', '-R', '.comment', outfile)

    def make_object(self, shell, code, outfile, build_options):
        build_args = get_clang_args(build_options)
        shell.run([self.command] + build_args + ['-', '-o', outfile], input=code)
