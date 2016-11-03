# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import platform
from argparse import ArgumentParser

argparser = ArgumentParser('ome', add_help=False)
argparser.add_argument('file', nargs='?')
argparser.add_argument('--version', action='store_true')
argparser.add_argument('--verbose', '-v', action='store_true')
argparser.add_argument('--verbose-backend', action='store_true')
argparser.add_argument('--target', action='store', default='c')
argparser.add_argument('--backend', action='store', default=None)
argparser.add_argument('--backend-command', action='store', default=None)
argparser.add_argument('--platform', action='store', default=platform.system())
argparser.add_argument('--make-object', '-c', action='store_true')
argparser.add_argument('--debug', '-g', action='store_true')
argparser.add_argument('--debug-gc', action='store_true')
argparser.add_argument('--gc-stats', action='store_true')
argparser.add_argument('--print-code', action='store_true')
argparser.add_argument('--output', '-o', action='store', default=None)

command_args = argparser.parse_args()
