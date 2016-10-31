# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import os
from ...constants import *
from ...cpreparser import CPreParser
from ...runtime import runtime_header, runtime_source
from ...types import BuiltInMethod

builtin_macros = runtime_header

builtin_code = runtime_source

builtin_code_main = '''
int main(int argc, const char *const *argv)
{
    OME_initialize(argc, argv);
    return OME_thread_main();
}
'''

def builtin_methods():
    methods = []
    builtins_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'builtins'))
    for filename in os.listdir(builtins_path):
        if filename.endswith('.c'):
            filename = os.path.join(builtins_path, filename)
            with open(filename) as f:
                source = f.read()
            parser = CPreParser(source, filename)
            parser.parse()
            methods.extend(parser.methods)
    return methods

builtin_methods = builtin_methods()

def build_builtins():
    data_defs = []

    for name in constant_names[:-1]:
        uname = name.replace('-', '_')
        data_defs.append('static const OME_Value OME_{} = {{._udata = OME_Constant_{}, ._utag = OME_Tag_Constant}};\n'.format(uname, uname))
        builtin_methods.append(BuiltInMethod(name, 'string', ['_0'], [], '''
    OME_STATIC_STRING(s, "{}");
    return OME_tag_pointer(OME_Tag_String, &s);
'''.format(name)))

    data_defs.append('\n')
    for n in range(17):
        data_defs.append('typedef OME_Value (*OME_Method_{})({});\n'.format(n, ', '.join(['OME_Value'] * (n + 1))))

    global builtin_data
    builtin_data = ''.join(data_defs)

build_builtins()
del build_builtins

if __name__ == '__main__':
    for method in builtin_methods:
        print(method.tag_name, method.symbol, method.sent_messages)
