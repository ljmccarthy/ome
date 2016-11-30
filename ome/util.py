import hashlib
import os
import platform
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
        return os.path.expanduser(os.path.join('~', '.cache', appname))
