import hashlib
import os
import tarfile
import tempfile
from os.path import join
from urllib.request import urlopen
from .build_shell import BuildShell
from .error import OmeError

class SourcePackage(object):
    def __init__(self, name, version, url, hash, build, output_files=[],
                  archive_name='{name}-{version}.tar.gz',
                  extract_dir='{name}-{version}'):
        vars = dict(name=name, version=version)
        self.name = name
        self.version = version
        self.url = url.format(**vars)
        self.hash = hash
        self.build = build
        self.output_files = output_files
        self.archive_name = archive_name.format(**vars)
        self.extract_dir = extract_dir.format(**vars)

def remove(path):
    try:
        os.remove(path)
    except Exception:
        pass

def make_path(path):
    if not os.path.isdir(path):
        os.makedirs(path)

def temporary_dir(prefix):
    return tempfile.TemporaryDirectory(prefix='{}-{}.'.format(prefix, os.getuid()))

def download(url, path):
    print('ome: downloading', url)
    try:
        with open(path, 'wb') as output:
            with urlopen(url) as input:
                while True:
                    buf = input.read(1024)
                    if not buf:
                        break
                    output.write(buf)
    except KeyboardInterrupt:
        remove(path)
        raise
    except Exception as e:
        remove(path)
        raise OmeError('ome: download failed: {}'.format(e))

def get_file_hash(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()

class SourcePackageBuilder(object):
    def __init__(self, sources_dir, prefix_dir, backend, verbose=True):
        self.shell = BuildShell(verbose)
        self.sources_dir = sources_dir
        self.prefix_dir = prefix_dir
        self.include_dir = join(prefix_dir, 'include')
        self.library_dir = join(prefix_dir, 'lib')
        self.backend = backend
        self.verbose = verbose

    def print_verbose(self, *args):
        if self.verbose:
            print('ome:', *args)

    def get_source(self, package):
        source_path = join(self.sources_dir, package.archive_name)
        if os.path.exists(source_path):
            if get_file_hash(source_path) != package.hash:
                self.print_verbose('hash check failed for', source_path)
                remove(source_path)
                download(package.url, source_path)
        else:
            download(package.url, source_path)
        if get_file_hash(source_path) != package.hash:
            raise OmeError('hash check failed for {}'.format(source_path))
            remove(source_path)
        return source_path

    def build_package(self, package):
        output_exists = [os.path.exists(join(self.prefix_dir, filename)) for filename in package.output_files]
        if not all(output_exists):
            for filename, exists in zip(package.output_files, output_exists):
                if exists:
                    remove(join(self.prefix_dir, filename))
            source_path = self.get_source(package)
            with temporary_dir('.ome-build') as build_dir:
                self.print_verbose('extracting', package.archive_name)
                with tarfile.open(source_path) as tar:
                    tar.extractall(build_dir)
                self.shell.cd(join(build_dir, package.extract_dir))
                self.print_verbose('building {0.name} {0.version}'.format(package))
                package.build(self.shell, self.backend, self)

    def build_packages(self, packages):
        make_path(self.sources_dir)
        make_path(self.include_dir)
        make_path(self.library_dir)
        for package in packages:
            self.build_package(package)
