# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import re

re_symbol_part = re.compile(r'(~?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)(:,*)?')

operator_labels = {
    '+' : '_ADD',
    '-' : '_SUB',
    '*' : '_MUL',
    '/' : '_DIV',
    '==': '_EQ',
    '!=': '_NE',
    '<' : '_LT',
    '<=': '_LE',
    '>' : '_GT',
    '>=': '_GE',
}

def symbol_to_label(symbol):
    """
    Encodes a symbol into a form that can be used for an assembly label, e.g.
        foo            foo__0
        foo:           foo__1
        foo-bar-baz    foo_bar_baz__0
        foo:,,         foo__3
        foo4:,,bar5:,  foo4__3bar5__2
        +              _ADD
    """
    if symbol in operator_labels:
        return operator_labels[symbol]
    return ''.join(
        name.replace('-', '_') + '__' + str(len(args))
        for name, args in re_symbol_part.findall(symbol))

def make_send_label(symbol):
    return 'OME_message_' + symbol_to_label(symbol)

def make_call_label_format(symbol):
    return 'OME_method_%X_' + symbol_to_label(symbol)

def make_call_label(tag, symbol):
    return make_call_label_format(symbol) % tag

__all__ = [
    'symbol_to_label',
    'make_send_label',
    'make_call_label_format',
    'make_call_label',
]
