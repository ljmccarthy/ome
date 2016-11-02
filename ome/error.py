class OmeError(Exception):
    def __init__(self, message, filename='ome'):
        self.message = message
        self.filename = filename

    def __str__(self):
        return '{}: error: {}'.format(self.filename, self.message)

    def write_ansi(self, terminal):
        terminal.bold()
        terminal.write(self.filename + ': ')
        terminal.colour('red')
        terminal.write('error: ')
        terminal.reset()
        terminal.write(self.message)
        terminal.write('\n')

class OmeParseError(OmeError):
    def __init__(self, message, ps):
        super(OmeParseError, self).__init__(message, ps.stream_name)
        source_line = ps.current_line.rstrip()
        self.source_line = source_line.lstrip()
        self.line_number = ps.line_number
        self.column = ps.column
        self.arrow_column = self.column - (len(source_line) - len(self.source_line))

    def write_ansi(self, terminal):
        terminal.bold()
        terminal.write('{0.filename}:{0.line_number}:{0.column}: '.format(self))
        terminal.colour('red')
        terminal.write('error: ')
        terminal.reset()
        terminal.write('{0.message} \n    {0.source_line}\n    '.format(self))
        terminal.write(' ' * self.arrow_column)
        terminal.bold()
        terminal.colour('green')
        terminal.write('^\n')
        terminal.reset()
