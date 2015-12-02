# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import platform

from .linux_x86_64 import Target_Linux_x86_64

target_types = [
    Target_Linux_x86_64,
]

target_platform_map = {
    target_type.platform: target_type for target_type in target_types
}

default_target_platform = (platform.system(), platform.machine())
