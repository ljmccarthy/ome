from os.path import join
from ...package import SourcePackage

def get_cflags(backend):
    cflags = ['-DNDEBUG', '-O3', '-fomit-frame-pointer', '-fPIC']
    if backend.name == 'clang':
        cflags.append('-Qunused-arguments')
    return cflags

def build_mpdecimal(shell, backend, options):
    shell.run('./configure', 'CC=' + backend.command, 'CFLAGS=' + ' '.join(get_cflags(backend)))
    shell.cd('libmpdec')
    shell.run('make', 'libmpdec.a')
    shell.copy('mpdecimal.h', options.include_dir)
    shell.copy('libmpdec.a', options.library_dir)

def build_libtommath(shell, backend, options):
    shell.run('make', 'CC=' + backend.command, 'CFLAGS=' + ' '.join(get_cflags(backend) + ['-I.']))
    shell.copy('tommath.h', options.include_dir)
    shell.copy('tommath_class.h', options.include_dir)
    shell.copy('tommath_superclass.h', options.include_dir)
    shell.copy('libtommath.a', options.library_dir)

packages = [
    SourcePackage(
        name = 'mpdecimal',
        version = '2.4.2',
        hash = '83c628b90f009470981cf084c5418329c88b19835d8af3691b930afccb7d79c7',
        url = 'http://www.bytereef.org/software/{name}/releases/{name}-{version}.tar.gz',
        build = build_mpdecimal,
        output_files = [
            join('include', 'mpdecimal.h'),
            join('lib', 'libmpdec.a'),
        ]
    ),
    SourcePackage(
        name = 'libtommath',
        version = '1.0',
        hash = '993a7df9ee091fca430cdde3263df57d88ef62af8103903214da49fc51bbb56c',
        url = 'https://github.com/libtom/libtommath/releases/download/v{version}/ltm-{version}.tar.xz',
        build = build_libtommath,
        output_files = [
            join('include', 'tommath.h'),
            join('include', 'tommath_class.h'),
            join('include', 'tommath_superclass.h'),
            join('lib', 'libtommath.a'),
        ]
    ),
]
