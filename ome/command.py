# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import platform
from argparse import ArgumentParser

argparser = ArgumentParser('ome', add_help=True)
argparser.add_argument('file', nargs='*')
argparser.add_argument('--version', action='store_true')
argparser.add_argument('--print-ast', action='store_true')
argparser.add_argument('--print-resolved-ast', action='store_true')
argparser.add_argument('--print-intermediate-code', action='store_true')
argparser.add_argument('--print-target-code', action='store_true')
argparser.add_argument('--verbose', '-v', action='store_true')
argparser.add_argument('--verbose-backend', action='store_true')
argparser.add_argument('--show-build-commands', action='store_true')
argparser.add_argument('--target', action='store', default='c')
argparser.add_argument('--backend', action='store', default=None)
argparser.add_argument('--backend-command', action='store', default=None)
argparser.add_argument('--platform', action='store', default=platform.system())
argparser.add_argument('--make-object', '-c', action='store_true')
argparser.add_argument('--static', action='store_true')
argparser.add_argument('--include-dir', '-I', action='append', default=[])
argparser.add_argument('--library-dir', '-L', action='append', default=[])
argparser.add_argument('--link', '-l', action='append', default=[])
argparser.add_argument('--use-musl', action='store_true')
argparser.add_argument('--musl-path', action='store')
argparser.add_argument('--fast', action='store_true')
argparser.add_argument('--debug', '-g', action='store_true')
argparser.add_argument('--debug-gc', action='store_true')
argparser.add_argument('--gc-stats', action='store_true')
argparser.add_argument('--no-traceback', action='store_true')
argparser.add_argument('--no-source-traceback', action='store_true')
argparser.add_argument('--output', '-o', action='store', default=None)
