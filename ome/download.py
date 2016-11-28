import os
import sys
import time
from urllib.request import urlopen
from .error import OmeError
from .util import remove, get_terminal_width

def format_size(n):
    if n < 1024:
        return '%d B' % n
    elif n < 1024**2:
        return '%.1f KB' % (float(n) / 1024)
    elif n < 1024**3:
        return '%.1f MB' % (float(n) / 1024**2)
    elif n < 1024**4:
        return '%.1f GB' % (float(n) / 1024**3)

def format_bar(value, total, max_width):
    width = value * max_width // total
    return '=' * width + ' ' * (max_width - width)

class Progress(object):
    def __init__(self, length, file=sys.stdout):
        self.length = length
        self.file = file
        self.is_tty = hasattr(file, 'isatty') and file.isatty()
        self.start_time = time.time()
        self.transferred = 0
        self.last_time = self.start_time
        self.last_transferred = 0
        self.rate = None
        self.last_line = ''

    def update(self, transferred):
        if self.is_tty:
            self.transferred += transferred
            now = time.time()
            if now - self.last_time > 1.0:
                self.rate = (self.transferred - self.last_transferred) / (now - self.last_time)
                self.last_time = now
                self.last_transferred = self.transferred

            rate = format_size(self.rate) + '/s' if self.rate is not None else ''
            if self.length:
                bar = format_bar(self.transferred, self.length, int(get_terminal_width() / 3))
                line = '\r\x1B[K[{0}] {1}% ({2} of {3}) @ {4}'.format(
                    bar, self.transferred * 100 // self.length,
                    format_size(self.transferred), format_size(self.length), rate)
            else:
                line = '\r\x1B[K=> {0} @ {1}\x1B[K'.format(format_size(self.transferred), rate)

            if line != self.last_line:
                self.file.write(line)
                self.file.flush()
                self.last_line = line

    def finish(self):
        if self.is_tty:
            self.file.write('\r\x1B[K')

def download(url, path):
    print('ome: downloading', url)
    try:
        with open(path, 'wb') as output:
            with urlopen(url) as input:
                progress = Progress(input.length)
                progress.update(0)
                try:
                    while True:
                        buf = input.read(1024)
                        if not buf:
                            break
                        progress.update(len(buf))
                        output.write(buf)
                finally:
                    progress.finish()
    except KeyboardInterrupt:
        remove(path)
        raise
    except Exception as e:
        remove(path)
        raise OmeError('ome: download failed: {}'.format(e))
