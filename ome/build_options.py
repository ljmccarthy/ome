import platform
from .ome_types import CompileOptions

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

def get_build_options_from_command(args):
    options = BuildOptions(
        platform = args.platform,
        variant = 'debug' if args.debug else ('fast' if args.fast else 'release'),
        link = not args.make_object,
        static = args.static,
        use_musl = args.use_musl,
        musl_path = args.musl_path,
        verbose = args.verbose,
        verbose_backend = args.verbose_backend,
        include_dirs = args.include_dir,
        library_dirs = args.library_dir,
        libraries = args.library,
        defines = [d.split('=', 1) if '=' in d else (d, '') for d in args.define])
    options.set_ome_defines(
        debug_gc = args.debug_gc,
        gc_stats = args.gc_stats,
        traceback = not args.no_traceback,
        source_traceback = not args.no_source_traceback)
    return options
