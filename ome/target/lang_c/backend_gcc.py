# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os
from .backend_cc import CCArgsBuilder

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

get_gcc_args = GCCArgsBuilder()

class GCCBuilder(object):
    name = 'GCC'
    default_command = 'gcc'
    supported_platforms = frozenset(['Linux'])
    version_args = ['--version']
    version_re = 'gcc \(GCC\) (\d+\.\d+\.\d+)'

    def __init__(self, command):
        self.command = command

    def executable_name(self, infile):
        return os.path.splitext(infile)[0]

    def object_name(self, infile):
        return os.path.splitext(infile)[0] + '.o'

    def make_executable(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options, '-', outfile)
        shell.run([self.command] + build_args, input=code)
        if not build_options.debug:
            shell.run('strip', '-R', '.comment', outfile)

    def make_object(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options, '-', outfile)
        shell.run([self.command] + build_args, input=code)
