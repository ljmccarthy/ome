# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import platform
import subprocess
from .error import OmeError
from .ome_types import CompileOptions
from .target import target_map

def get_target(target_name):
    target_name = target_name.lower()
    if target_name not in target_map:
        raise OmeError("unknown target '{}'".format(target_name))
    return target_map[target_name]

def get_backend_version(backend):
    if not hasattr(backend, 'version') and hasattr(backend, 'version_args'):
        reason = 'could not get version number'
        args = list(backend.version_args)
        args[0] = backend.tools[args[0]]
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            outs, errs = process.communicate()
            if process.returncode == 0:
                m = backend.version_re.match(outs.decode('ascii'))
                if m:
                    backend.version = m.group(1)
                    return
        except OSError as e:
            reason = str(e)
        except UnicodeDecodeError:
            pass
        raise OmeError("backend '{}' is not available: {}".format(backend.name, reason))

def _get_backend(target, backend_name, backend_tools):
    return target.backends[backend_name](backend_tools)

def get_backend(target, platform, backend_name=None, backend_tools={}):
    platform = platform.lower()
    if backend_name is None:
        for backend_name in target.backend_preference:
            backend = _get_backend(target, backend_name, backend_tools)
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
        backend = _get_backend(target, backend_name, backend_tools)
        if hasattr(backend, 'supported_platforms') and platform not in backend.supported_platforms:
            raise OmeError("backend '{}' does not support platform '{}'".format(backend.name, platform))
        get_backend_version(backend)
        return backend

platform_defines = {
    'linux':  [
        ('OME_PLATFORM_POSIX', ''),
        ('_GNU_SOURCE', ''),
        ('_LARGEFILE_SOURCE', ''),
        ('_FILE_OFFSET_BITS', '64'),
    ],
    'darwin': [
        ('OME_PLATFORM_POSIX', '')
    ],
}

class BuildOptions(CompileOptions):
    def __init__(self, platform=platform.system(), variant='release',
                  link=False, static=False, use_musl=False, musl_path=None,
                  verbose=False, verbose_backend=False,
                  include_dirs=(), library_dirs=(), libraries=(), objects=(),
                  defines=()):
        self.platform = platform.lower()
        self.variant = variant
        self.link = link
        self.static = static
        self.use_musl = use_musl
        self.musl_path = musl_path
        self.verbose = verbose
        self.verbose_backend = verbose_backend
        self.include_dirs = list(include_dirs)
        self.library_dirs = list(library_dirs)
        self.libraries = list(libraries)
        self.objects = list(objects)
        self.defines = list(defines)
        if self.debug:
            self.defines.append(('DEBUG', ''))
            self.defines.append(('_DEBUG', ''))
        else:
            self.defines.append(('NDEBUG', ''))

    @property
    def debug(self):
        return self.variant == 'debug'

    @property
    def release(self):
        return self.variant == 'release'

    def set_ome_defines(self, debug_gc=False, gc_stats=False, traceback=True, source_traceback=True):
        self.traceback = traceback
        self.source_traceback = source_traceback
        self.defines.append(('OME_PLATFORM', self.platform))
        self.defines.append(('OME_PLATFORM_' + self.platform.upper(), ''))
        self.defines.extend(platform_defines.get(self.platform, []))
        if debug_gc:
            self.defines.append(('OME_GC_DEBUG', ''))
        if gc_stats:
            self.defines.append(('OME_GC_STATS', ''))
        if not traceback:
            self.defines.append(('OME_NO_TRACEBACK', ''))
        if not source_traceback:
            self.defines.append(('OME_NO_SOURCE_TRACEBACK', ''))

def get_build_options_from_command(command_args):
    options = BuildOptions(
        platform = command_args.platform,
        variant = 'debug' if command_args.debug else ('fast' if command_args.fast else 'release'),
        link = not command_args.make_object,
        static = command_args.static,
        use_musl = command_args.use_musl,
        musl_path = command_args.musl_path,
        verbose = command_args.verbose,
        verbose_backend = command_args.verbose_backend,
        include_dirs = command_args.include_dir,
        library_dirs = command_args.library_dir,
        libraries = command_args.link)
    options.set_ome_defines(
        debug_gc = command_args.debug_gc,
        gc_stats = command_args.gc_stats,
        traceback = not command_args.no_traceback,
        source_traceback = not command_args.no_source_traceback)
    return options
