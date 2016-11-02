# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

def get_cc_args(build_options, all_args, release_args, debug_args, release_link_args=[]):
    args = []
    if not build_options.link:
        args.append('-c')
    args.extend(all_args)
    if build_options.debug:
        args.extend(debug_args)
    else:
        args.extend(release_args)
        if build_options.link:
            args.extend(release_link_args)
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
