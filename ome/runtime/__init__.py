import os

def read_source(filename):
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), filename)
    with open(path) as f:
        return f.read()

runtime_header = read_source('ome.h')
runtime_source = read_source('runtime.c')
