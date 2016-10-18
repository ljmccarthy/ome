# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

class StackAllocator(object):
    """
    Generates a list of variables to load and save on the stack for each instruction.
    """
    def __init__(self, instructions, num_args):
        self.stack_size = 0
        self.non_heap_locals = set()
        self.valid_heap_locals = set(range(num_args))
        self.saved_heap_locals = {}
        self.free_stack_slots = set()
        self.cleared_stack_slots = set()

        for ins in instructions:
            self.forget_locals(ins.live_set)
            ins.load_list = self.load_locals(ins.args)

            if not ins.is_leaf:
                ins.save_list, ins.clear_list = self.save_locals(ins.live_set_after - {ins.dest})

            if hasattr(ins, 'dest'):
                if ins.dest_from_heap:
                    self.valid_heap_locals.add(ins.dest)
                else:
                    self.non_heap_locals.add(ins.dest)

    def load_locals(self, locals):
        load_list = []
        locals = sorted(x for x in locals if isinstance(x, int))
        for local in locals:
            if local not in self.valid_heap_locals and local not in self.non_heap_locals:
                load_list.append((local, self.saved_heap_locals[local]))
                self.valid_heap_locals.add(local)
        return load_list

    def save_locals(self, locals):
        save_list = []
        clear_list = []
        locals = sorted(x for x in locals if isinstance(x, int))
        for local in locals:
            if local not in self.saved_heap_locals and local not in self.non_heap_locals:
                if self.free_stack_slots:
                    slot = min(self.free_stack_slots)
                    self.free_stack_slots.remove(slot)
                else:
                    slot = len(self.saved_heap_locals)
                    self.stack_size = max(self.stack_size, slot + 1)
                self.saved_heap_locals[local] = slot
                save_list.append((local, slot))
                self.cleared_stack_slots.add(slot)
        self.valid_heap_locals.clear()
        for slot in sorted(self.free_stack_slots - self.cleared_stack_slots):
            clear_list.append(slot)
            self.cleared_stack_slots.add(slot)
        return save_list, clear_list

    def forget_locals(self, live_set):
        dead_set = set(self.saved_heap_locals.keys())
        dead_set.difference_update(live_set)
        for local in sorted(dead_set):
            slot = self.saved_heap_locals[local]
            del self.saved_heap_locals[local]
            self.free_stack_slots.add(slot)
            if slot in self.cleared_stack_slots:
                self.cleared_stack_slots.remove(slot)

def allocate_stack_slots(instructions, num_args):
    return StackAllocator(instructions, num_args).stack_size
