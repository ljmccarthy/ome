import os

def read_source(filename):
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), filename)
    with open(path, encoding='utf8') as f:
        return f.read()

header = read_source('ome.h')
source = read_source('runtime.c')
main = read_source('main.c')
