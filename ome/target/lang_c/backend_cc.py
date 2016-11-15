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
    cc_args = []
    link_args = []
    variant_cc_args = {'release': [], 'fast': [], 'debug': []}
    variant_link_args = {'release': [], 'fast': [], 'debug': []}

    def get_musl_args(self, build_options, musl_path):
        raise OmeError("musl is not supported for this backend")

    def __call__(self, build_options, infile, outfile):
        args = []
        tail_args = []
        if build_options.use_musl:
            musl_path = find_musl_path(build_options.musl_path)
            args, tail_args = self.get_musl_args(build_options, musl_path)
        if build_options.verbose_backend:
            args.append('-v')
        if not build_options.link:
            args.append('-c')
        if build_options.static:
            args.append('-static')
        args.extend(self.cc_args)
        args.extend(self.variant_cc_args.get(build_options.variant, []))
        if build_options.link:
            args.extend(self.link_args)
            args.extend(self.variant_link_args.get(build_options.variant, []))
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
        if build_options.release and build_options.link:
            shell.run('strip', '-R', '.comment', outfile)
