import sys
import os

tests_dir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(tests_dir, '..')))

from ome.parser import Parser
from ome.terminal import stderr

def read_tests(filename):
    with open(os.path.join(tests_dir, filename)) as f:
        s = f.read()
    lines = s.rstrip().split('\n')
    tests = []
    for i in range(0, len(lines), 3):
        test = lines[i:i+2]
        if len(test) == 1:
            test = (test[0], '')
        tests.append(test)
    return tests

def fail(filename, line, input, expected, actual):
    stderr.bold()
    stderr.colour('red')
    stderr.write('error: ')
    stderr.reset()
    stderr.bold()
    stderr.write('test failed in file {} on line {}\n'.format(filename, line))
    stderr.reset()
    stderr.write('input:\n\t{}\nexpected:\n\t{}\nactual:\n\t{}\n'.format(input, expected, actual))
    sys.exit(1)

def run_tests(filename, test_func):
    for n, (input, expected) in enumerate(read_tests(filename)):
        actual = test_func(input, expected)
        if actual != expected:
            fail(filename, n*3 + 1, input, expected, actual)

def test_parse_expr(input, expected):
    return str(Parser(input, '').expr())

def run_all_tests():
    run_tests('parse_expr.txt', test_parse_expr)
    run_tests('parse_number.txt', test_parse_expr)
    print('All tests passed successfully!')

if __name__ == '__main__':
    run_all_tests()
