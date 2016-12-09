import hashlib
import os
import platform
import stat
import sys
import tempfile
from contextlib import contextmanager

def is_terminal(file):
    return hasattr(file, 'isatty') and file.isatty()

def is_ansi_terminal(file):
    return (sys.platform != 'win32' or 'ANSICON' in os.environ) and is_terminal(file)

def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80

def remove(path):
    try:
        os.remove(path)
    except OSError:
        pass

def make_path(path):
    if not os.path.isdir(path):
        os.makedirs(path)

@contextmanager
def temporary_file(prefix=None, suffix=None):
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    try:
        yield path
    finally:
        os.close(fd)
        remove(path)

def temporary_dir(prefix):
    uid = '-{}'.format(os.getuid()) if hasattr(os, 'getuid') else ''
    return tempfile.TemporaryDirectory(prefix=prefix + uid)

def get_file_hash(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()

def get_cache_dir(appname):
    if platform.system() == 'Darwin':
        return os.path.expanduser(os.path.join('~', 'Library', 'Caches', appname))
    elif platform.system() == 'Windows':
        return os.path.join(os.environ['LOCALAPPDATA'], appname, 'cache')
    else:
        cache_dir = os.environ.get('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
        return os.path.join(cache_dir, appname)

def is_executable(filename):
    if platform.system() == 'Windows':
        return os.path.isfile(filename)
    try:
        st = os.stat(filename)
    except OSError:
        return False
    mode = st.st_mode
    return stat.S_ISREG(mode) and ((mode & stat.S_IXOTH) or
        (os.getuid() == st.st_uid and mode & stat.S_IXUSR) or
        (os.getgid() == st.st_gid and mode & stat.S_IXGRP))

executable_name_format = {'Windows': '{}.exe'}

def find_executable(name):
    name = executable_name_format.get(platform.system(), '{}').format(name)
    for path in os.environ.get('PATH', '').split(os.path.pathsep):
        filepath = os.path.realpath(os.path.join(path, name))
        if is_executable(filepath):
            return filepath
