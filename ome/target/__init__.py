# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

import platform

from .linux_x86_64 import Target_Linux_x86_64

target_platforms = {
    ('Linux', 'x86_64'): Target_Linux_x86_64,
}

default_target_platform = (platform.system(), platform.machine())
