# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os

class FileBuilder(object):
    name = 'file'
    default_command = ''
    version = ''

    def __init__(self, command):
        pass

    def executable_name(self, infile):
        return os.path.splitext(infile)[0] + '.c'

    def make_executable(self, shell, code, outfile, build_options):
        with open(outfile, 'wb') as f:
            f.write(code)
