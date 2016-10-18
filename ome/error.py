class OmeError(Exception):
    _format = '\x1b[1m{0}: \x1b[31merror:\x1b[0m {1}'

    def __init__(self, message, filename='ome'):
        self.message = message
        self.filename = filename

    def __str__(self):
        return self._format.format(self.filename, self.message)
