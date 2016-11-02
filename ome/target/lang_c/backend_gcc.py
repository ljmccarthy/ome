# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import os
from .backend_cc import get_cc_args

gcc_args = [
    '-x', 'c',
    '-std=c99',
    '-Wall',
    '-Wextra',
    '-Wno-unused',
]

gcc_release_args = [
    '-O3',
]

gcc_debug_args = [
    '-ggdb',
]

gcc_release_link_args = [
    '-Wl,--strip-all',
    '-Wl,--gc-sections',
]

def get_gcc_args(build_options):
    args = []
    if not build_options.link:
        args.append('-c')
    args.extend(gcc_args)
    if build_options.debug:
        args.extend(gcc_debug_args)
    else:
        args.extend(gcc_release_args)
        if build_options.link:
            args.extend(gcc_release_link_args)
    get_cc_args(build_options, args)
    return args

class GCCBuilder(object):
    name = 'GCC'
    supported_platforms = frozenset(['Linux'])
    version_args = ['--version']
    version_re = 'gcc \(GCC\) (\d+\.\d+\.\d+)'

    def __init__(self, command='gcc'):
        self.command = command

    def executable_name(self, infile):
        return os.path.splitext(infile)[0]

    def object_name(self, infile):
        return os.path.splitext(infile)[0] + '.o'

    def make_executable(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options)
        shell.run([self.command] + build_args + ['-', '-o', outfile], input=code)
        if not build_options.debug:
            shell.run('strip', '-R', '.comment', outfile)

    def make_object(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options)
        shell.run([self.command] + build_args + ['-', '-o', outfile], input=code)
