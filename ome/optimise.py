# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .instructions import *

def eliminate_aliases(instructions):
    """Eliminate all local variable aliases (i.e. ALIAS instructions)."""

    aliases = {}
    instructions_out = []

    for location, ins in enumerate(instructions):
        if isinstance(ins, ALIAS):
            aliases[ins.dest] = aliases.get(ins.source, ins.source)
        else:
            for i, arg in enumerate(ins.args):
                if arg in aliases:
                    ins.args[i] = aliases[arg]
            instructions_out.append(ins)

    return instructions_out

def eliminate_load_values(instructions, value_format):
    """
    Eliminate all LOAD_VALUE instructions by replacing references to
    the variable with the actual value in.
    """
    instructions_out = []
    values = {}

    for ins in instructions:
        if isinstance(ins, LOAD_VALUE):
            values[ins.dest] = ins
        else:
            for i, arg in enumerate(ins.args):
                if arg in values:
                    load_ins = values[arg]
                    ins.args[i] = value_format.format(tag=load_ins.tag, value=load_ins.value)
            instructions_out.append(ins)

    return instructions_out

def move_constants_to_usage_points(instructions, num_locals):
    """
    Remove LOAD_VALUE/LOAD_LABEL instructions and re-inserts loading to a
    new local just before they are needed. This reduces the size of the live
    set since it is only needed for an instance and can be re-loaded again
    as needed.
    """

    instructions_out = []
    constant_values = {}
    constant_labels = {}

    for ins in instructions:
        if isinstance(ins, LOAD_VALUE):
            constant_values[ins.dest] = ins
        elif isinstance(ins, LOAD_LABEL):
            constant_labels[ins.dest] = ins
        else:
            for i, arg in enumerate(ins.args):
                if arg in constant_values:
                    cins = constant_values[arg]
                    instructions_out.append(LOAD_VALUE(num_locals, cins.tag, cins.value))
                    ins.args[i] = num_locals
                    num_locals += 1
                elif arg in constant_labels:
                    cins = constant_labels[arg]
                    instructions_out.append(LOAD_LABEL(num_locals, cins.tag, cins.label))
                    ins.args[i] = num_locals
                    num_locals += 1
            instructions_out.append(ins)

    return instructions_out

def eliminate_redundant_untags(instructions):
    instructions_out = []
    untagged_locals = {}
    untagged_local_aliases = {}

    for ins in instructions:
        if isinstance(ins, UNTAG):
            if ins.source not in untagged_locals:
                untagged_locals[ins.source] = ins.dest
                untagged_local_aliases[ins.dest] = ins.dest
                instructions_out.append(ins)
            else:
                untagged_local_aliases[ins.dest] = untagged_locals[ins.source]
        else:
            for i, arg in enumerate(ins.args):
                if arg in untagged_local_aliases:
                    ins.args[i] = untagged_local_aliases[arg]
            instructions_out.append(ins)

    return instructions_out

def renumber_locals(instructions, num_args):
    """Renumbers locals in the order of creation without any gaps."""

    locals_map = {i: i for i in range(num_args)}

    for ins in instructions:
        for i, arg in enumerate(ins.args):
            ins.args[i] = locals_map.get(arg, arg)
        if hasattr(ins, 'dest'):
            assert ins.dest not in locals_map
            new_dest = len(locals_map)
            locals_map[ins.dest] = new_dest
            ins.dest = new_dest

    return len(locals_map)

def find_live_sets(instructions):
    """
    Compute the live set for each instruction.
    """
    created_at = {}
    last_used_at = [set() for _ in range(len(instructions))]

    seen = set()
    for loc, ins in reversed(list(enumerate(instructions))):
        if hasattr(ins, 'dest') and isinstance(ins.dest, int):
            created_at[loc] = ins.dest
            if ins.dest not in seen:
                last_used_at[loc].add(ins.dest)
        for arg in ins.args:
            if arg not in seen and isinstance(arg, int):
                seen.add(arg)
                last_used_at[loc].add(arg)

    live_set = seen - set(created_at.values())
    for loc, ins in enumerate(instructions):
        ins.live_set = frozenset(live_set)
        if loc in created_at:
            live_set.add(created_at[loc])
        live_set.difference_update(last_used_at[loc])
        ins.live_set_after = frozenset(live_set)

def find_local_usage_points(instructions, num_args):
    usage_points = {i: [] for i in range(num_args)}
    for loc, ins in enumerate(instructions):
        if hasattr(ins, 'dest'):
            usage_points[ins.dest] = [loc]
        for local in ins.args:
            usage_points[local].append(loc)
    return usage_points

def find_usage_distances(instructions, num_args):
    """
    For each instruction, find the the distance to the next use of each local
    variable in the live set.
    """
    usage_distances = []
    current_distance = {}
    created_point = {}

    for loc, ins in reversed(list(enumerate(instructions))):
        used_here = set(ins.args)
        if hasattr(ins, 'dest'):
            used_here.add(ins.dest)
            created_point[ins.dest] = loc
        not_used_here = set(current_distance.keys()) - used_here
        for local in used_here:
            current_distance[local] = 0
        for local in not_used_here:
            current_distance[local] += 1
        usage_distances.append(current_distance.copy())

    usage_distances.reverse()
    for local, created_loc in created_point.items():
        for loc in range(created_loc):
            del usage_distances[loc][local]

    # Add usage distance to instruction objects
    for loc, ins in enumerate(instructions):
        ins.usage_distance = usage_distances[loc]

    return usage_distances

def get_call_registers(call_ins, arg_regs):
    """
    Returns a dict mapping locals to registers for each register used
    to pass arguments to the call instruction.
    """
    return {call_ins.args[i]: arg_regs[i]
            for i in range(min(len(call_ins.args), len(arg_regs)))}

def get_call_ranges(instructions):
    call_ranges = []
    start = 0
    for loc, ins in enumerate(instructions):
        if isinstance(ins, CALL):
            call_ranges.append((start, loc))
            start = loc + 1
    return call_ranges, start

class LocalStorage(object):
    def __init__(self, num_args, target):
        self.arg_regs = target.arg_registers
        self.temp_regs = target.temp_registers
        self.return_reg = target.return_register

        self.local_register = {i: self.arg_regs[i] for i in range(min(num_args, len(self.arg_regs)))}
        self.register_local = {self.arg_regs[i]: i for i in range(min(num_args, len(self.arg_regs)))}
        self.free_registers = list(self.arg_regs[num_args:] + self.temp_regs)

        # Stack slots are negatively indexed from the position of the first argument
        # The real offset is computed by subtracting from the maximum frame size
        #
        # | loc1 | 5  0  num_stack_slots = 6
        # | loc0 | 4  1
        # | retn | 3  -
        # | arg0 | 2  3
        # | arg1 | 1  4
        # | arg2 | 0  5

        self.local_stack = {i: i - len(self.arg_regs) for i in range(len(self.arg_regs), num_args)}
        self.free_stack_slots = []
        self.stack_offset = len(self.local_stack)
        self.num_stack_slots = 0

        self.spills = []

    def get_local_register(self, local):
        return self.local_register[local]

    def remove_local_from_register(self, local):
        if local in self.local_register:
            reg = self.local_register[local]
            del self.local_register[local]
            del self.register_local[reg]
            if reg not in self.free_registers:
                self.free_registers.append(reg)
            return reg

    def remove_local_from_stack(self, local):
        if local in self.local_stack:
            slot = self.local_stack[local]
            del self.local_stack[local]
            self.free_stack_slots.append(slot)
            return slot

    def remove_inactive_locals(self, active_locals):
        active_locals = frozenset(active_locals)
        locals_using_regs = frozenset(self.local_register.keys())
        locals_using_stack = frozenset(self.local_stack.keys())
        reg_locals_to_free = sorted(locals_using_regs - active_locals)
        stack_locals_to_free = sorted(locals_using_stack - active_locals)

        for local in reg_locals_to_free:
            self.remove_local_from_register(local)

        for local in stack_locals_to_free:
            self.remove_local_from_stack(local)

    def get_stack_slot(self, local):
        if local in self.local_stack:
            stack_slot = self.local_stack[local]
        elif self.free_stack_slots:
            stack_slot = self.free_stack_slots.pop()
            self.local_stack[local] = stack_slot
        else:
            stack_slot = self.stack_offset
            self.stack_offset += 1
            self.num_stack_slots += 1
            self.local_stack[local] = stack_slot
        return stack_slot

    def move_local_to_register(self, local, new_reg):
        old_reg = self.local_register[local]
        del self.register_local[old_reg]
        self.local_register[local] = new_reg
        self.register_local[new_reg] = local
        if new_reg in self.free_registers:
            self.free_registers.remove(new_reg)
        if old_reg not in self.free_registers:
            self.free_registers.append(old_reg)
        self.spills.append(MOVE(new_reg, old_reg))
        return old_reg

    def spill(self, local):
        if local in self.local_stack:
            return self.local_stack[local]
        else:
            stack_slot = self.get_stack_slot(local)
            self.spills.append(SPILL(self.local_register[local], stack_slot))
            return stack_slot

    def unspill(self, local, reg):
        assert local not in self.local_register
        if reg in self.register_local:
            old_local = self.register_local[reg]
            del self.local_register[old_local]
        self.local_register[local] = reg
        self.register_local[reg] = local
        if reg in self.free_registers:
            self.free_registers.remove(reg)
        if local in self.local_stack:
            self.spills.append(UNSPILL(reg, self.local_stack[local]))

    def get_spills(self):
        spills = self.spills
        self.spills = []
        return spills

    def move_to_free_register_or_spill(self, local):
        if self.free_registers:
            self.move_local_to_register(local, self.free_registers.pop())
        else:
            self.spill(local)

    def find_lowest_priority_register(self, reg_priority):
        """
        Find the register containing the lowest priority local,
        i.e. largest distance to next use.
        """
        max_priority = -1
        lowest_priority_reg = None
        for local, reg in self.local_register.items():
            if local not in reg_priority or reg_priority[local] > max_priority:
                max_priority = reg_priority[local]
                lowest_priority_reg = reg
        return lowest_priority_reg

    def get_local_to_any_register(self, local, reg_priority):
        if local in self.local_register:
            return self.local_register[local]
        if self.free_registers:
            reg = self.free_registers.pop()
        else:
            reg = self.find_lowest_priority_register(reg_priority)
            self.spill(self.register_local[reg])
        self.unspill(local, reg)
        return reg

    def get_local_to_register(self, local, preferred_regs, reg_priority):
        if local not in self.local_register:
            if local not in preferred_regs:
                self.get_local_to_any_register(local, reg_priority)
            else:
                preferred_reg = preferred_regs[local]
                if preferred_reg not in self.register_local:
                    self.unspill(local, preferred_reg)
                else:
                    self.get_local_to_any_register(local, reg_priority)
        return self.local_register[local]

    def prepare_call(self, call_ins, after_call_ins):
        self.remove_inactive_locals(call_ins.usage_distance.keys())

        # Spill all locals needed after the call
        for local in list(self.local_register.keys()):
            if local in after_call_ins.usage_distance:
                self.spill(local)
                if local not in call_ins.args:
                    self.remove_local_from_register(local)

        # Push stack arguments
        for arg in call_ins.args[len(self.arg_regs):]:
            reg = self.get_local_to_any_register(arg, call_ins.usage_distance)
            self.spills.append(PUSH(reg))
            self.remove_local_from_register(arg)

        # Shuffle register arguments to correct registers
        for i, arg in enumerate(call_ins.args[:len(self.arg_regs)]):
            if self.arg_regs[i] in self.register_local:
                local_in_arg_reg = self.register_local[self.arg_regs[i]]
                if local_in_arg_reg != arg and local_in_arg_reg in call_ins.args:
                    self.move_to_free_register_or_spill(local_in_arg_reg)
            if arg in self.local_register:
                if self.local_register[arg] != self.arg_regs[i]:
                    self.move_local_to_register(arg, self.arg_regs[i])
            else:
                self.unspill(arg, self.arg_regs[i])

        self.local_register = {call_ins.dest: self.return_reg}
        self.register_local = {self.return_reg: call_ins.dest}
        self.free_registers = list(self.arg_regs + self.temp_regs)

        call_ins.num_stack_args = max(0, len(call_ins.args) - len(self.arg_regs))

    def move_to_return_register(self, local):
        if local not in self.local_register:
            self.unspill(local, self.return_reg)
        elif self.local_register[local] != self.return_reg:
            self.spills.append(MOVE(self.return_reg, self.local_register[local]))

    def adjust_stack_offsets(self, instructions):
        # Fix up stack offsets to be relative to stack pointer
        stack_adjust = self.stack_offset
        for ins in instructions:
            if isinstance(ins, (SPILL, UNSPILL)):
                ins.stack_slot = stack_adjust - ins.stack_slot
            elif isinstance(ins, PUSH):
                stack_adjust += 1
            elif isinstance(ins, CALL):
                stack_adjust = self.stack_offset

def allocate_registers(instructions, num_args, target):
    locals = LocalStorage(num_args, target)
    usage_distances = find_usage_distances(instructions, num_args)
    instructions_out = []

    def process_instruction(ins, next_ins, preferred_regs):
        locals.remove_inactive_locals(ins.usage_distance.keys())
        #if isinstance(ins, (TAG, UNTAG)) and ins.source not in next_ins.usage_distance:
        #    ins.dest = ins.source
        if hasattr(ins, 'dest'):
            locals.get_local_to_register(ins.dest, preferred_regs, ins.usage_distance)
        for arg in ins.args:
            locals.get_local_to_register(arg, preferred_regs, ins.usage_distance)
        for i, arg in enumerate(ins.args):
            ins.args[i] = locals.get_local_register(arg)
        if hasattr(ins, 'dest'):
            ins.dest = locals.get_local_register(ins.dest)
        instructions_out.extend(locals.get_spills())
        instructions_out.append(ins)

    call_ranges, tail = get_call_ranges(instructions)

    for start, end in call_ranges:
        next_call_ins = instructions[end]
        preferred_regs = get_call_registers(next_call_ins, target.arg_registers)

        for i in range(start, end):
            process_instruction(instructions[i], instructions[i+1], preferred_regs)

        locals.prepare_call(next_call_ins, instructions[end + 1])
        instructions_out.extend(locals.get_spills())

        next_call_ins.dest = None
        next_call_ins.args = []
        instructions_out.append(next_call_ins)

    return_ins = instructions[-1]
    preferred_regs = {return_ins.source: target.return_register}

    for i in range(tail, len(instructions)-1):
        process_instruction(instructions[i], instructions[i+1], preferred_regs)

    locals.move_to_return_register(return_ins.source)
    instructions_out.extend(locals.get_spills())
    locals.adjust_stack_offsets(instructions_out)

    return instructions_out, locals.num_stack_slots
