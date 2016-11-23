import os
import shutil
import subprocess
from .error import OmeError

def run_shell_command(args, input=None, output=None, **kwargs):
    process = subprocess.Popen(args,
        stdin = input and subprocess.PIPE,
        stdout = output and subprocess.PIPE,
        **kwargs)
    outs, errs = process.communicate(input)
    if process.returncode != 0:
        if output:
            print(outs)
        raise OmeError('command failed with return code {}'.format(process.returncode))
    return outs

def get_args_list(args):
    if len(args) == 1 and isinstance(args[0], (list, tuple)):
        args = args[0]
    return args

class BuildShell(object):
    def __init__(self, show_commands=False):
        self.show_commands = show_commands
        self._pwd = ''
        self.cd('.')

    @property
    def pwd(self):
        return self._pwd

    def cd(self, path):
        self._pwd = os.path.abspath(os.path.join(self._pwd, path))

    def move(self, src, dst):
        shutil.move(os.path.join(self._pwd, src), os.path.join(self._pwd, dst))

    def copy(self, src, dst):
        shutil.copy2(os.path.join(self._pwd, src), os.path.join(self._pwd, dst))

    def print_command(self, args):
        if self.show_commands:
            print(' '.join(args))

    def run(self, *args, input=None, output=None):
        args = get_args_list(args)
        self.print_command(args)
        return run_shell_command(args, input, output, cwd=self._pwd)
