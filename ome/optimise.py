# ome - Object Message Expressions
# Copyright (c) 2015-2016 Luke McCarthy <luke@iogopro.co.uk>

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

def move_constants_to_usage_points(instructions, num_locals):
    """
    Remove LOAD_VALUE/LOAD_LABEL instructions and re-inserts loading to a
    new local just before they are needed. This reduces the size of the live
    set since it is only needed for an instance and can be re-loaded again
    as needed.
    """

    instructions_out = []
    constant_instructions = {}

    for ins in instructions:
        if isinstance(ins, (LOAD_VALUE, LOAD_LABEL)):
            constant_instructions[ins.dest] = ins
        else:
            for i, arg in enumerate(ins.args):
                if arg in constant_instructions:
                    cins = constant_instructions[arg]
                    del constant_instructions[arg]
                    instructions_out.append(cins)
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
