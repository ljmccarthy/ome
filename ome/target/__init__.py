# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import platform
from .lang_c import targets

target_map = {
    target_type.target_id: target_type for target_type in targets
}

#default_target_platform = (platform.machine(), platform.system())
default_target_id = ('c', platform.system().lower())
