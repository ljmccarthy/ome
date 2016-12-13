# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os

class FileBuilder(object):
    name = 'file'
    version = ''
    tools = {}
    build_packages = False

    def __init__(self, tools):
        pass

    def output_name(self, infile, build_options):
        return os.path.splitext(infile)[0] + '.c'

    def build_string(self, shell, code, outfile, build_options):
        with open(outfile, 'wb') as f:
            f.write(code)
