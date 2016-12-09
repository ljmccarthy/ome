from os.path import join
from ...package import SourcePackage

def get_cflags(backend):
    cflags = ['-DNDEBUG', '-O3', '-fomit-frame-pointer', '-fPIC', '-fno-asynchronous-unwind-tables']
    if backend.name == 'clang':
        cflags.append('-Qunused-arguments')
    return cflags

def build_mpdecimal(shell, backend, options):
    shell.run('./configure', 'CC=' + backend.tools['CC'], 'CFLAGS=' + ' '.join(get_cflags(backend)))
    shell.cd('libmpdec')
    shell.run('make', 'libmpdec.a')
    shell.copy('mpdecimal.h', options.include_dir)
    shell.copy('libmpdec.a', options.library_dir)

def build_libtommath(shell, backend, options):
    shell.run('make', 'CC=' + backend.tools['CC'], 'CFLAGS=' + ' '.join(get_cflags(backend) + ['-I.']))
    shell.copy('tommath.h', options.include_dir)
    shell.copy('tommath_class.h', options.include_dir)
    shell.copy('tommath_superclass.h', options.include_dir)
    shell.copy('libtommath.a', options.library_dir)

libuv_headers = '''\
android-ifaddrs.h
pthread-barrier.h
stdint-msvc2008.h
tree.h
uv-aix.h
uv-bsd.h
uv-darwin.h
uv-errno.h
uv.h
uv-linux.h
uv-sunos.h
uv-threadpool.h
uv-unix.h
uv-version.h
uv-win.h'''.split()

def build_libuv(shell, backend, options):
    shell.run('git', 'clone', 'https://chromium.googlesource.com/external/gyp.git', 'build/gyp')
    shell.run('python2', 'gyp_uv.py', '-f', 'make')
    shell.run('make', '-C', 'out', 'libuv', 'BUILDTYPE=Release', 'CC=' + backend.tools['CC'], 'CFLAGS=' + ' '.join(get_cflags(backend)))
    shell.copy(join('out', 'Release', 'libuv.a'), options.library_dir)
    for header in libuv_headers:
        shell.copy(join('include', header), options.include_dir)

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
    SourcePackage(
        name = 'libuv',
        version = '1.9.1',
        url = 'http://dist.libuv.org/dist/v{version}/{name}-v{version}.tar.gz',
        hash = 'e83953782c916d7822ef0b94e8115ce5756fab5300cca173f0de5f5b0e0ae928',
        extract_dir = '{name}-v{version}',
        build = build_libuv,
        output_files = [
            join('lib', 'libuv.a'),
        ] + [
            join('include', header) for header in libuv_headers
        ]
    ),
]
