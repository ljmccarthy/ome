from .constants import MIN_CONSTANT_TAG, MAX_TAG, MAX_CONSTANT
from .error import OmeError

def constant_id_to_tag_id(constant_id):
    return constant_id + MIN_CONSTANT_TAG

class IdAllocator(object):
    def __init__(self, builtin):
        self.tag_names = list(builtin.opaque_names)
        self.pointer_tag_names = list(builtin.pointer_names)
        self.constant_names = list(builtin.constant_names)
        self._check_duplicates()
        self._update_dicts()

    def _check_duplicates(self):
        seen = set()
        for name_list in (self.tag_names, self.pointer_tag_names, self.constant_names):
            for name in name_list:
                if name in seen:
                    raise OmeError('duplicate tag/constant name: {}'.format(name))
                seen.add(name)

    def _update_dicts(self):
        self.tags = dict((name, i) for i, name in enumerate(self.tag_names))
        self.tags.update((name, constant_id_to_tag_id(i)) for i, name in enumerate(self.constant_names))
        self.constants = dict((name, i) for i, name in enumerate(self.constant_names))

    def allocate_block_ids(self, block_list):
        assert not hasattr(self, 'pointer_tag_id')
        self.pointer_tag_id = len(self.tag_names)
        self.tag_names.extend(self.pointer_tag_names)
        self.pointer_tag_names.clear()
        self._update_dicts()

        tag_id = len(self.tag_names)
        constant_id = len(self.constant_names)
        for block in block_list:
            if not block.is_constant:
                block.tag_id = tag_id
                tag_id += 1
            else:
                block.constant_id = constant_id
                block.tag_id = constant_id_to_tag_id(constant_id)
                constant_id += 1

        if tag_id > MAX_TAG:
            raise OmeError('exhausted all tag IDs')
        if constant_id > MAX_CONSTANT:
            raise OmeError('exhausted all constant IDs')
