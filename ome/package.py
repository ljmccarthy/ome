import os
import tarfile
from os.path import join
from urllib.parse import urlparse
from .build_shell import BuildShell
from .download import download
from .error import OmeError
from .util import get_file_hash, temporary_dir, make_path

class SourcePackage(object):
    def __init__(self, name, version, url, hash, build, output_files=[],
                  archive_name=None, extract_dir='{name}-{version}'):
        vars = dict(name=name, version=version)
        self.name = name
        self.version = version
        self.url = url.format(**vars)
        self.hash = hash
        self.build = build
        self.output_files = output_files
        self.archive_name = (archive_name or os.path.basename(urlparse(url).path)).format(**vars)
        self.extract_dir = extract_dir.format(**vars)

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

    def is_package_built(self, package):
        output_exists = [os.path.exists(join(self.prefix_dir, filename)) for filename in package.output_files]
        if not all(output_exists):
            for filename, exists in zip(package.output_files, output_exists):
                if exists:
                    remove(join(self.prefix_dir, filename))
            return False
        return True

    def build_package(self, package):
        with temporary_dir('.ome-build') as build_dir:
            self.print_verbose('extracting', package.archive_name)
            source_path = join(self.sources_dir, package.archive_name)
            with tarfile.open(source_path) as tar:
                tar.extractall(build_dir)
            self.shell.cd(join(build_dir, package.extract_dir))
            self.print_verbose('building {0.name} {0.version}'.format(package))
            package.build(self.shell, self.backend, self)

    def build_packages(self, packages):
        make_path(self.sources_dir)
        make_path(self.include_dir)
        make_path(self.library_dir)
        unbuilt_packages = [p for p in packages if not self.is_package_built(p)]
        for package in unbuilt_packages:
            self.get_source(package)
        for package in unbuilt_packages:
            self.build_package(package)
