import sys
import os

ansi_colour_list = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
ansi_colour_code = dict((name, '{}m'.format(code)) for code, name in enumerate(ansi_colour_list, 30))

def is_ansi_terminal(file):
    return ((sys.platform != 'win32' or 'ANSICON' in os.environ)
        and hasattr(file, 'isatty') and file.isatty())

class MaybeAnsiTerminal(object):
    def __init__(self, file):
        self._file = file
        self.is_ansi = is_ansi_terminal(file)

    def __getattr__(self, attr):
        return getattr(self._file, attr)

    def write_ansi_code(self, code):
        if self.is_ansi:
            self._file.write('\x1B[' + code)

    def reset(self):
        self.write_ansi_code('0m')

    def bold(self):
        self.write_ansi_code('1m')

    def colour(self, name):
        self.write_ansi_code(ansi_colour_code[name])

stdout = MaybeAnsiTerminal(sys.stdout)
stderr = MaybeAnsiTerminal(sys.stderr)
