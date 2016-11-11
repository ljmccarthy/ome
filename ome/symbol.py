# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import re

re_symbol_part = re.compile(r'([~]?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)(:,*)?')

operator_labels = {
    '+' : '__ADD',
    '-' : '__SUB',
    '*' : '__MUL',
    '/' : '__DIV',
    '==': '__EQ',
    '!=': '__NE',
    '<' : '__LT',
    '<=': '__LE',
    '>' : '__GT',
    '>=': '__GE',
}

re_hyphen_or_tilde = re.compile(r'[~-]')

def symbol_to_label(symbol):
    """
    Encodes a symbol into a form that can be used for an assembly label, e.g.
        foo            foo__0
        foo:           foo__1
        foo-bar-baz    foo_bar_baz__0
        foo:,,         foo__3
        foo4:,,bar5:,  foo4__3bar5__2
        ~foo:          _foo__1
        +              __ADD
        ≠              __NE
    """
    if symbol in operator_labels:
        return operator_labels[symbol]
    return ''.join(
        re_hyphen_or_tilde.sub('_', name) + '__' + str(len(args))
        for name, args in re_symbol_part.findall(symbol))

def symbol_arity(symbol):
    if symbol in operator_labels:
        return 2
    return symbol.count(':') + symbol.count(',') + 1

def is_private_symbol(name):
    return name.startswith('~')

__all__ = [
    'symbol_to_label',
    'symbol_arity',
    'is_private_symbol',
]
