"""CeeSafe names for the C names ceesafec generates (Nova's docs/c-backend.md section 2.1, docs/tooling.md section 3.2).

Shared by ceesafe_lldb.py and ceesafe_gdb.py; plain Python, no debugger API. The C names are still novac's (`nvF_`,
`nvM_`, `v_`, `f_`) until the fork point switches the prefix (Decision 0004); this file switches with them.
"""

import os
import re

# Split C (Nova's ADR 0022): external names carry the program's name, `nvF_<program>_main`. Set CEESAFE_PROGRAM to
# that name (ceesafec's --program, or the package's) to read them.
_PROGRAM = os.environ.get("CEESAFE_PROGRAM", "")

_LOCAL = re.compile(r"^v_(.+)_\d+$")
_FIELD = re.compile(r"^f_(.+)$")
_FUNCTION = re.compile(r"^nvF_(.+)$")
_METHOD = re.compile(r"^nvM_(\d+)(.+)$")


def local(name):
    """The CeeSafe name of a C local (`v_sum_1` is `sum`), or None for a compiler temporary or anything else."""
    match = _LOCAL.match(name or "")
    return match.group(1) if match else None


def field(name):
    """The CeeSafe name of a C struct member (`f_x` is `x`)."""
    match = _FIELD.match(name or "")
    return match.group(1) if match else name


def function(name):
    """The CeeSafe name of a C function: `nvF_length` is `length`, `nvM_7Counter_bump` is `Counter.bump`."""
    name = name or "?"
    if _PROGRAM:
        for family in ("nvF_", "nvM_"):
            if name.startswith(family + _PROGRAM + "_"):
                name = family + name[len(family + _PROGRAM) + 1:]
    match = _FUNCTION.match(name)
    if match:
        return match.group(1)
    match = _METHOD.match(name)
    if match:
        length, rest = int(match.group(1)), match.group(2)
        if len(rest) > length + 1 and rest[length] == "_":
            return rest[:length] + "." + rest[length + 1:]
    return name
