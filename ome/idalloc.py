from .constants import *
from .error import OmeError

opaque_names = [
    'Constant',
    'Small-Integer',
    'Small-Decimal',
]

pointer_names = [
    'String',
    'String-Buffer',
    'Byte-Array',
    'Byte-Array-Mutable',
    'Byte-Array-Buffer',
    'Array',            # immutable
    'Array-Mutable',    # mutable, fixed-size
    'Array-Buffer',     # mutable, resizable
]

constant_names = [
    'False',
    'True',
    'Empty',                # The empty block
    'BuiltIn',              # Block for built-in methods
    'Stack-Overflow',
    'Not-Understood',
    'Type-Error',
    'Index-Error',
    'Overflow',
    'Divide-By-Zero',
]

def constant_id_to_tag(constant_id):
    return constant_id + MIN_CONSTANT_TAG

class IdAllocator(object):
    def __init__(self):
        self.opaque_names = []
        self.pointer_names = list(pointer_names)
        self.constant_names = []
        self.names = set(opaque_names)
        self.names.update(pointer_names)
        self.names.update(constant_names)
        self.tag_list = [(name, i) for i, name in enumerate(opaque_names)]
        self.constant_list = [(name, i) for i, name in enumerate(constant_names)]
        self.tags = dict(self.tag_list)
        self.constants = dict(self.constant_list)
        self.tags.update((name, constant_id_to_tag(id)) for name, id in self.constant_list)

    def _add_name(self, name):
        if name in self.names:
            raise OmeError('duplicate tag/constant name: {}'.format(name))
        self.names.add(name)

    def add_constant_name(self, name):
        self._add_name(name)
        self.constant_names.append(name)

    def add_opaque_name(self, name):
        self._add_name(name)
        self.opaque_names.append(name)

    def add_pointer_name(self, name):
        self._add_name(name)
        self.pointer_names.append(name)

    def add_builtins(self, builtins):
        for constant_name in builtins.constant_names:
            self.add_constant_name(constant_name)
        for opaque_name in builtins.opaque_names:
            self.add_opaque_name(opaque_name)
        for pointer_name in builtins.pointer_names:
            self.add_pointer_name(pointer_name)

    def allocate_ids(self, block_list):
        for name in self.opaque_names:
            self.tag_list.append((name, len(self.tag_list)))
        self.pointer_tag_id = len(self.tag_list)
        for name in self.pointer_names:
            self.tag_list.append((name, len(self.tag_list)))
        for block in block_list:
            if not block.is_constant:
                block.tag_id = len(self.tag_list)
                self.tag_list.append(('Block-{}'.format(block.tag_id), block.tag_id))

        for name in self.constant_names:
            self.constant_list.append((name, len(self.constant_list)))
        for block in block_list:
            if block.is_constant:
                block.constant_id = len(self.constant_list)
                block.tag_id = constant_id_to_tag(block.constant_id)
                self.tag_list.append(('Block-{}'.format(block.tag_id), block.tag_id))
                self.constant_list.append(('Constant-{}'.format(block.constant_id), block.constant_id))

        self.tags = dict(self.tag_list)
        self.constants = dict(self.constant_list)
        self.tags.update((name, constant_id_to_tag(id)) for name, id in self.constant_list)

        if len(self.tags) > MAX_TAG:
            raise OmeError('exhausted all tag IDs')
        if len(self.constants) > MAX_CONSTANT:
            raise OmeError('exhausted all constant tag IDs')
