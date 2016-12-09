# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import subprocess
from .error import OmeError
from .target import target_map

def get_target(target_name):
    target_name = target_name.lower()
    if target_name not in target_map:
        raise OmeError("unknown target '{}'".format(target_name))
    return target_map[target_name]

def get_backend_version(backend):
    if not hasattr(backend, 'version') and hasattr(backend, 'version_args'):
        reason = 'could not get version number'
        args = list(backend.version_args)
        args[0] = backend.tools[args[0]]
        try:
            process = subprocess.Popen(args, stdout=subprocess.PIPE)
            outs, errs = process.communicate()
            if process.returncode == 0:
                m = backend.version_re.match(outs.decode('ascii'))
                if m:
                    backend.version = m.group(1)
                    return
        except OSError as e:
            reason = str(e)
        except UnicodeDecodeError:
            pass
        raise OmeError("backend '{}' is not available: {}".format(backend.name, reason))

def _get_backend(target, backend_name, backend_tools):
    return target.backends[backend_name](backend_tools)

def get_backend(target, platform, backend_name=None, backend_tools={}):
    platform = platform.lower()
    if backend_name is None:
        for backend_name in target.backend_preference:
            backend = _get_backend(target, backend_name, backend_tools)
            if not hasattr(backend, 'supported_platforms') or platform in backend.supported_platforms:
                try:
                    get_backend_version(backend)
                    return backend
                except OmeError:
                    pass
        raise OmeError("could not find a working backend for target '{}' for platform '{}'".format(target.name, platform))
    else:
        backend_name = backend_name.lower()
        if backend_name not in target.backends:
            raise OmeError("unknown backend '{}' for target '{}'".format(backend_name, target.name))
        backend = _get_backend(target, backend_name, backend_tools)
        if hasattr(backend, 'supported_platforms') and platform not in backend.supported_platforms:
            raise OmeError("backend '{}' does not support platform '{}'".format(backend.name, platform))
        get_backend_version(backend)
        return backend
