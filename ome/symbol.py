# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

import re

re_symbol_part = re.compile(r'([~]?[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)*)(:,*)?')
re_hyphen_or_tilde = re.compile(r'[~-]')

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

operator_aliases = {
    '×' : '*',
    '÷' : '/',
    '≠' : '!=',
    '≤' : '<=',
    '≥' : '>=',
}

def symbol_to_label(symbol):
    """
    Encodes a symbol into a form that can be used for a label.

    >>> symbol_to_label('foo')
    'foo__0'
    >>> symbol_to_label('foo:')
    'foo__1'
    >>> symbol_to_label('foo-bar-baz')
    'foo_bar_baz__0'
    >>> symbol_to_label('foo:,,')
    'foo__3'
    >>> symbol_to_label('foo4:,,bar5:,')
    'foo4__3bar5__2'
    >>> symbol_to_label('~foo:')
    '_foo__1'
    >>> symbol_to_label('≠')
    '__NE'
    >>> symbol_to_label('!=')
    '__NE'
    >>> symbol_to_label('')
    Traceback (most recent call last):
    ...
    ValueError: Invalid symbol ''
    >>> symbol_to_label('~')
    Traceback (most recent call last):
    ...
    ValueError: Invalid symbol '~'
    >>> symbol_to_label(':foo')
    Traceback (most recent call last):
    ...
    ValueError: Invalid symbol ':foo'
    >>> symbol_to_label('foo::')
    Traceback (most recent call last):
    ...
    ValueError: Invalid symbol 'foo::'
    >>> symbol_to_label('foo-')
    Traceback (most recent call last):
    ...
    ValueError: Invalid symbol 'foo-'
    """
    op = operator_aliases.get(symbol, symbol)
    if op in operator_labels:
        return operator_labels[op]
    m = None
    pos = 0
    label = []
    for m in re_symbol_part.finditer(symbol):
        if m.start() != pos:
            raise ValueError('Invalid symbol {}'.format(repr(symbol)))
        pos = m.end()
        name, args = m.groups()
        label.append(re_hyphen_or_tilde.sub('_', name) + '__' + str(len(args or ())))
    if not m or m.end() != len(symbol):
        raise ValueError('Invalid symbol {}'.format(repr(symbol)))
    return ''.join(label)

def symbol_arity(symbol):
    """
    >>> symbol_arity('foo')
    1
    >>> symbol_arity('foo:')
    2
    >>> symbol_arity('foo:bar:')
    3
    >>> symbol_arity('foo:,,bar:')
    5
    >>> symbol_arity('*')
    2
    """
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

if __name__ == '__main__':
    import doctest
    doctest.testmod()
