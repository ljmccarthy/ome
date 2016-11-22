# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import re
import subprocess
import time
from .error import OmeError
from .ome_types import CompileOptions
from .target import target_map

def get_target(target_name):
    target_name = target_name.lower()
    if target_name not in target_map:
        raise OmeError("unknown target '{}'".format(target_name))
    return target_map[target_name]

def get_backend_version(backend):
    if not hasattr(backend, 'version') and hasattr(backend, 'command'):
        reason = 'could not get version number'
        args = [backend.command] + backend.version_args
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            outs, errs = process.communicate()
            if process.returncode == 0:
                m = re.match(backend.version_re, outs.decode('ascii'))
                if m:
                    backend.version = m.group(1)
                    return
        except OSError as e:
            reason = str(e)
        except UnicodeDecodeError:
            pass
        raise OmeError("backend '{}' is not available: {}".format(backend.name, reason))

def get_backend(target, platform, backend_name=None, backend_command=None):
    platform = platform.lower()
    if backend_name is None:
        for backend_name in target.backend_preference:
            backend = target.backends[backend_name]
            backend = backend(backend_command or backend.default_command)
            if not hasattr(backend, 'supported_platforms') or platform in backend.supported_platforms:
                try:
                    get_backend_version(backend)
                    return backend
                except OmeError:
                    pass
        raise OmeError("could not find a working backend for target '{}' for platform '{}'".format(target.name, platform))
    else:
        backend_name = backend_name.lower()
        if backend_name not in target.backends:
            raise OmeError("unknown backend '{}' for target '{}'".format(backend_name, target.name))
        backend = target.backends[backend_name]
        backend = backend(backend_command or backend.default_command)
        get_backend_version(backend)
        return backend

def run_shell_command(args, input=None, output=None):
    process = subprocess.Popen(args,
        stdin = input and subprocess.PIPE,
        stdout = output and subprocess.PIPE)
    outs, errs = process.communicate(input)
    if process.returncode != 0:
        raise OmeError('command failed with return code {}'.format(process.returncode))
    return outs

def get_args_list(args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    return args

class BuildShell(object):
    def __init__(self, show_commands=False):
        self.show_commands = show_commands

    def print_command(self, args):
        if self.show_commands:
            print(' '.join(args))

    def run(self, *args, input=None, output=None):
        args = get_args_list(args)
        self.print_command(args)
        return run_shell_command(args, input, output)

platform_aliases = {
    'linux': ['posix'],
}

class BuildOptions(CompileOptions):
    def __init__(self, target, options):
        self.target = target
        self.platform = options.platform.lower()
        self.variant = 'debug' if options.debug else ('fast' if options.fast else 'release')
        self.debug = options.debug
        self.release = not options.debug and not options.fast
        self.link = not options.make_object
        self.static = options.static
        self.verbose = options.verbose
        self.verbose_backend = options.verbose_backend
        self.traceback = not options.no_traceback
        self.source_traceback = not options.no_source_traceback
        self.use_musl = options.use_musl
        self.musl_path = options.musl_path
        self.shell = BuildShell(options.show_build_commands)
        self.include_dirs = options.include_dir[:]
        self.library_dirs = options.library_dir[:]
        self.libraries = options.link[:]
        self.objects = []
        self.defines = [
            ('OME_PLATFORM', self.platform),
            ('OME_PLATFORM_' + self.platform.upper(), ''),
        ]
        for platform_alias in platform_aliases.get(self.platform):
            self.defines.append(('OME_PLATFORM_' + platform_alias.upper(), ''))
        if not options.debug:
            self.defines.append(('NDEBUG', ''))
        if options.debug_gc:
            self.defines.append(('OME_GC_DEBUG', ''))
        if options.gc_stats:
            self.defines.append(('OME_GC_STATS', ''))
        if options.no_traceback:
            self.defines.append(('OME_NO_TRACEBACK', ''))
        if options.no_source_traceback:
            self.defines.append(('OME_NO_SOURCE_TRACEBACK', ''))

    def make_output(self, input, outfile, backend):
        if hasattr(backend, 'supported_platforms') and self.platform not in backend.supported_platforms:
            raise OmeError("backend '{}' does not support platform '{}'".format(backend.name, self.platform))
        backend.make_output(self.shell, input, outfile, self)
