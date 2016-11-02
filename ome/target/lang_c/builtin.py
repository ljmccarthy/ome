# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import os
from ...cpreparser import CPreParser
from ...idalloc import constant_names
from ...runtime import runtime_header, runtime_source
from ...types import BuiltInMethod

main_code = '''
int main(int argc, const char *const *argv)
{
    OME_initialize(argc, argv);
    return OME_thread_main();
}
'''

constant_string_method = '''
    OME_STATIC_STRING(s, "{name}");
    return OME_tag_pointer(OME_Tag_String, &s);
'''

def emit_constant_declarations(out, constants):
    out.write(runtime_header)
    out.write('\n')
    for n in range(17):
        out.write('typedef OME_Value (*OME_Method_{})({});\n'.format(n, ', '.join(['OME_Value'] * (n + 1))))
    out.write('\n')
    for name, value in constants:
        uname = name.replace('-', '_')
        out.write('static const OME_Value OME_{} = {{._udata = OME_Constant_{}, ._utag = OME_Tag_Constant}};\n'.format(uname, uname))
    out.write('\n')

def emit_builtin_code(out):
    out.write(runtime_source)

def emit_toplevel(out):
    out.write(main_code)

def get_builtin_methods():
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
    for name in constant_names:
        methods.append(BuiltInMethod(name, 'string', ['_0'], [], constant_string_method.format(name=name)))
    return methods

if __name__ == '__main__':
    for method in get_builtin_methods():
        print(method.tag_name, method.symbol, method.sent_messages)
