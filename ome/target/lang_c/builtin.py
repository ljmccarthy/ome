# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import os
from ... import runtime
from ...cpreparser import CPreParser
from ...types import BuiltIn, BuiltInMethod

constant_string_method = '''
    OME_STATIC_STRING(s, "{name}");
    return OME_tag_pointer(OME_Tag_String, &s);
'''

def emit_builtin_header(out, builtin):
    out.write(runtime.header)
    out.write('\n')
    for n in range(17):
        out.write('typedef OME_Value (*OME_Method_{})({});\n'.format(n, ', '.join(['OME_Value'] * (n + 1))))
    out.write('\n')
    for name in builtin.constant_names:
        name = name.replace('-', '_')
        out.write('static const OME_Value OME_{} = {{._udata = OME_Constant_{}, ._utag = OME_Tag_Constant}};\n'.format(name, name))

def emit_builtin_code(out):
    out.write(runtime.source)

def emit_builtin_main(out):
    out.write(runtime.main)

def get_builtin():
    builtin = BuiltIn()
    builtin_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'builtins'))
    for filename in os.listdir(builtin_path):
        if filename.endswith('.c'):
            filename = os.path.join(builtin_path, filename)
            with open(filename) as f:
                source = f.read()
            parser = CPreParser(source, filename)
            parser.parse(builtin)
    for name in builtin.constant_names:
        builtin.methods.append(BuiltInMethod(name, 'string', ['_0'], [], constant_string_method.format(name=name)))
    return builtin

if __name__ == '__main__':
    for method in get_builtin().methods:
        print(method.tag_name, method.symbol, method.sent_messages)
