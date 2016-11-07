# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

def format_instruction_args(args):
    return ', '.join('%{}'.format(x) for x in args)

class Instruction(object):
    args = ()
    is_leaf = True
    check_error = False
    dest_from_heap = False
    load_list = ()
    save_list = ()
    clear_list = ()

    def emit(self, codegen):
        getattr(codegen, self.__class__.__name__)(self)

class ALLOC(Instruction):
    is_leaf = False
    dest_from_heap = True

    def __init__(self, dest, size, tag):
        self.dest = dest
        self.size = size
        self.tag = tag

    def __str__(self):
        return '%{} = ALLOC(size:{}, tag:{})'.format(self.dest, self.size, self.tag)

class ARRAY(Instruction):
    is_leaf = False
    dest_from_heap = True

    def __init__(self, dest, size, tag):
        self.dest = dest
        self.size = size
        self.tag = tag

    def __str__(self):
        return '%{} = ARRAY(size: {}, tag: {})'.format(self.dest, self.size, self.tag)

class CALL(Instruction):
    is_leaf = False
    dest_from_heap = True

    def __init__(self, dest, args, call_label, traceback_info, check_error=True):
        self.dest = dest
        self.args = args
        self.call_label = call_label
        self.traceback_info = traceback_info
        self.check_error = check_error

    def __str__(self):
        dest = '%{} = '.format(self.dest) if self.dest else ''
        return '{}CALL {}({})'.format(dest, self.call_label, format_instruction_args(self.args))

class CONCAT(Instruction):
    is_leaf = False
    dest_from_heap = True

    def __init__(self, dest, args, traceback_info):
        self.dest = dest
        self.args = args
        self.traceback_info = traceback_info

    def __str__(self):
        return '%{} = CONCAT({})'.format(self.dest, format_instruction_args(self.args))

class LOAD_VALUE(Instruction):
    def __init__(self, dest, tag, value):
        self.dest = dest
        self.tag = tag
        self.value = value

    def __str__(self):
        return '%{} = TAG({}, {})'.format(self.dest, self.tag, self.value)

class LOAD_LABEL(Instruction):
    def __init__(self, dest, tag, label):
        self.dest = dest
        self.tag = tag
        self.label = label

    def __str__(self):
        return '%{} = TAG({}, {})'.format(self.dest, self.tag, self.label)

class GET_SLOT(Instruction):
    dest_from_heap = True

    def __init__(self, dest, object, slot_index):
        self.dest = dest
        self.args = [object]
        self.slot_index = slot_index

    def __str__(self):
        return '%{} = GETSLOT(%{}, {})'.format(self.dest, self.object, self.slot_index)

    @property
    def object(self):
        return self.args[0]

class SET_SLOT(Instruction):
    def __init__(self, object, slot_index, value):
        self.args = [object, value]
        self.slot_index = slot_index

    @property
    def object(self):
        return self.args[0]

    @property
    def value(self):
        return self.args[1]

    def __str__(self):
        return 'SETSLOT(%{}, {}, %{})'.format(self.object, self.slot_index, self.value)

class SET_ELEM(Instruction):
    def __init__(self, array, elem_index, value):
        self.args = [array, value]
        self.elem_index = elem_index

    @property
    def array(self):
        return self.args[0]

    @property
    def value(self):
        return self.args[1]

    def __str__(self):
        return 'SETELEM(%{}, {}, %{})'.format(self.array, self.elem_index, self.value)

class RETURN(Instruction):
    def __init__(self, source):
        self.args = [source]

    @property
    def source(self):
        return self.args[0]

    def __str__(self):
        return 'RETURN %{}'.format(self.source)

class ALIAS(Instruction):
    def __init__(self, dest, source):
        self.dest = dest
        self.args = [source]

    def __str__(self):
        return '%{} = %{}'.format(self.dest, self.source)

    @property
    def source(self):
        return self.args[0]
