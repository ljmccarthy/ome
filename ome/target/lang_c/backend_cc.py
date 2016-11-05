# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os
from ...error import OmeError

def find_musl_path(path):
    if path:
        return path
    path = os.environ.get('MUSL_PATH')
    if path:
        return path
    for path in ['/usr/local/lib/musl', '/usr/lib/musl']:
        if os.path.isdir(path):
            return path
    raise OmeError('could not find musl path, please specify with --musl-path')

class CCArgsBuilder(object):
    all = []
    release = []
    debug = []
    release_link = []
    debug_link = []

    def get_musl_args(self, built_options, musl_path):
        raise OmeError("musl is not supported for this backend")

    def __call__(self, build_options, infile, outfile):
        args = []
        tail_args = []
        if build_options.use_musl:
            musl_path = find_musl_path(build_options.musl_path)
            args, tail_args = self.get_musl_args(build_options, musl_path)
        if build_options.verbose:
            args.append('-v')
        if not build_options.link:
            args.append('-c')
        if build_options.static:
            args.append('-static')
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
        args.extend(tail_args)
        return args

class CCBuilder(object):
    def __init__(self, command):
        self.command = command

    def output_name(self, infile, build_options):
        outfile = os.path.splitext(infile)[0]
        if not build_options.link:
            outfile += '.o'
        return outfile

    def make_output(self, shell, code, outfile, build_options):
        build_args = self.get_build_args(build_options, '-', outfile)
        shell.run([self.command] + build_args, input=code)
        if not (build_options.debug or build_options.link):
            shell.run('strip', '-R', '.comment', outfile)
