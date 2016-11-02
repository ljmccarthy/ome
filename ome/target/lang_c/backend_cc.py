# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os

class CCArgsBuilder(object):
    all = []
    release = []
    debug = []
    release_link = []
    debug_link = []

    def __call__(self, build_options, infile, outfile):
        args = []
        if build_options.verbose:
            args.append('-v')
        if not build_options.link:
            args.append('-c')
        args.extend(self.all)
        args.extend(self.debug if build_options.debug else self.release)
        if build_options.link:
            args.extend(self.debug_link if build_options.debug else self.release_link)
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
        args.append(infile)
        args.append('-o')
        args.append(outfile)
        return args

class CCBuilder(object):
    def __init__(self, command):
        self.command = command

    def executable_name(self, infile):
        return os.path.splitext(infile)[0]

    def object_name(self, infile):
        return os.path.splitext(infile)[0] + '.o'

    def make_executable(self, shell, code, outfile, build_options):
        build_args = self.get_build_args(build_options, '-', outfile)
        shell.run([self.command] + build_args, input=code)
        if not build_options.debug:
            shell.run('strip', '-R', '.comment', outfile)

    def make_object(self, shell, code, outfile, build_options):
        build_args = self.get_build_args(build_options, '-', outfile)
        shell.run([self.command] + build_args, input=code)
