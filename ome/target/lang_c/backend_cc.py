# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

class CCArgsBuilder(object):
    all = []
    release = []
    debug = []
    release_link = []
    debug_link = []

    def __call__(self, build_options):
        args = []
        if not build_options.link:
            args.append('-c')
        args.extend(self.all)
        args.extend(self.debug if build_options.debug else self.release)
        if build_options.link:
            args.extend(self.release_link if build_options.debug else self.debug_link)
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
