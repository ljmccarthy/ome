def format_sexpr_flat(node):
    if not isinstance(node, (list, tuple)):
        return str(node)
    else:
        return '(' + ' '.join(format_sexpr_flat(x) for x in node) + ')'

def format_sexpr(node, indent_level=0, max_width=80):
    if not isinstance(node, (list, tuple)):
        return str(node)
    if len(node) == 0:
        return '()'
    xs = [format_sexpr(x, indent_level, max_width) for x in node]
    width = indent_level + (len(xs) - 1) + sum(len(x) for x in xs) + 2
    if width < max_width:
        return '(' + ' '.join(xs) + ')'
    else:
        line_indent = '\n' + ' ' * (indent_level + 2)
        xs = [format_sexpr(x, indent_level + 2, max_width) for x in node[:-1]]
        if xs:
            xs.append(format_sexpr(node[-1], indent_level + 2, max_width - 1))
        if node[0] in ('method', 'send', 'call', 'local'):
            x = format_sexpr_flat(node[1])
            width = len(node[0]) + len(x) + 2
            if width < max_width:
                return '(' + node[0] + ' ' + x + line_indent + line_indent.join(xs[2:]) + ')'
        return '(' + line_indent.join(xs) + ')'
