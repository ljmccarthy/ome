# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import platform
from .lang_c import platforms as c_platforms

target_types = c_platforms

target_platform_map = {
    target_type.platform: target_type for target_type in target_types
}

#default_target_platform = (platform.machine(), platform.system())
default_target_platform = ('c', platform.system().lower())
