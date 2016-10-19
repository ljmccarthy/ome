from io import StringIO

escape_chars = {
    0: '\\0',
    7: '\\a',
    8: '\\b',
    9: '\\t',
    10: '\\n',
    11: '\\v',
    12: '\\f',
    13: '\\r',
    34: '\\"',
    92: '\\\\',
}

hex_chars = '0123456789ABCDEFabcdef'
oct_chars = '01234567'

def literal_c_string(s):
    if isinstance(s, str):
        s = s.encode('utf8')
    buf = StringIO()
    buf.write('"')
    last_was_hex_escape = False
    last_was_oct_escape = False
    for c in s:
        if c in escape_chars:
            buf.write(escape_chars[c])
            last_was_hex_escape = False
        elif 32 <= c < 127:
            if (last_was_hex_escape and chr(c) in hex_chars) \
            or (last_was_oct_escape and chr(c) in oct_chars):
                buf.write('""')
            buf.write(chr(c))
            last_was_hex_escape = False
        else:
            buf.write('\\x{:02x}'.format(c))
            last_was_hex_escape = True
        last_was_oct_escape = c == 0
    buf.write('"')
    return buf.getvalue()
