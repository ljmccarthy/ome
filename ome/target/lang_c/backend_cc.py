# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os
import platform
import tempfile
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

    def __call__(self, build_options, infile, outfile, linking):
        args = []
        tail_args = []
        if build_options.use_musl:
            musl_path = find_musl_path(build_options.musl_path)
            args, tail_args = self.get_musl_args(build_options, musl_path, linking)
        args.append('-pipe')
        if build_options.verbose_backend:
            args.append('-v')
        if not linking:
            args.append('-c')
            args.extend(self.cc_args)
            args.extend(self.variant_cc_args.get(build_options.variant, []))
            for name, value in build_options.defines:
                args.append('-D{}={}'.format(name, value) if value else '-D' + name)
            for include_dir in build_options.include_dirs:
                args.append('-I' + include_dir)
            args.append(infile)
        else:
            args.append('-static' if build_options.static else '-pie')
            args.extend(self.link_args)
            args.extend(self.variant_link_args.get(build_options.variant, []))
            args.append(infile)
            for obj in build_options.objects:
                args.append(obj)
            for lib_dir in build_options.library_dirs:
                args.append('-L' + lib_dir)
            for lib in build_options.libraries:
                args.append('-l' + lib)
        args.extend(tail_args)
        args.append('-o')
        args.append(outfile)
        return args

class CCBuilder(object):
    obj_extension = '.o'
    lib_extension = '.a'
    exe_extension = ''

    def __init__(self, command):
        self.command = command

    def output_name(self, infile, build_options):
        return os.path.splitext(infile)[0] + (self.exe_extension if build_options.link else self.obj_extension)

    def make_output(self, shell, code, outfile, build_options):
        if build_options.link:
            with tempfile.NamedTemporaryFile(prefix='.ome-build-{}.'.format(os.getuid()), suffix='.o') as objfile:
                objfile = objfile.name
                shell.run([self.command] + self.get_build_args(build_options, '-', objfile, False), input=code)
                if build_options.link:
                    shell.run([self.command] + self.get_build_args(build_options, objfile, outfile, True))
                    if build_options.release and platform.system() == 'Linux':
                        shell.run('strip', '-R', '.comment', outfile)
        else:
            shell.run([self.command] + self.get_build_args(build_options, '-', outfile, False), input=code)
