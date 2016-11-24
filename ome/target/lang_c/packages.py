import subprocess
from os.path import join
from ...package import SourcePackage

def build_mpdecimal(shell, backend, options):
    cflags = ['-DNDEBUG', '-O3', '-fomit-frame-pointer', '-fPIC']
    if backend.name == 'clang':
        cflags.append('-Qunused-arguments')
    shell.run('./configure', 'CC=' + backend.command, 'CFLAGS=' + ' '.join(cflags))
    shell.cd('libmpdec')
    shell.run('make', 'libmpdec.a')
    shell.copy('mpdecimal.h', options.include_dir)
    shell.copy('libmpdec.a', options.library_dir)

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
]
