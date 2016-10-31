# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import os

gcc = 'gcc'

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
    args = [gcc]
    if not build_options.link:
        args.append('-c')
    args.extend(gcc_args)
    if build_options.debug:
        args.extend(gcc_debug_args)
    else:
        args.extend(gcc_release_args)
        if build_options.link:
            args.extend(gcc_release_link_args)
    for name, value in build_options.defines:
        args.append('-D{}={}'.format(name, value) if value else '-D' + name)
    for include_dir in build_options.include_dirs:
        args.append('-I' + include_dir)
    for lib_dir in build_options.lib_dirs:
        args.append('-L' + lib_dir)
    for dynamic_lib in build_options.dynamic_libs:
        args.append('-l' + dynamic_lib)
    for static_lib in build_options.static_libs:
        args.append(static_lib)
    return args

class GCCBuilder(object):
    def executable_name(self, infile):
        return os.path.splitext(infile)[0]

    def object_name(self, infile):
        return os.path.splitext(infile)[0] + '.o'

    def make_executable(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options)
        shell.run(build_args + ['-', '-o', outfile], input=code)
        if not build_options.debug:
            shell.run('strip', '-R', '.comment', outfile)

    def make_object(self, shell, code, outfile, build_options):
        build_args = get_gcc_args(build_options)
        shell.run(build_args + ['-', '-o', outfile], input=code)
