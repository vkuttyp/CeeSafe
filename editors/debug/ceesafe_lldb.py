"""CeeSafe names in lldb (Nova's docs/tooling.md section 3.3): `command script import editors/debug/ceesafe_lldb.py`.

ceesafe-locals  the current frame's locals and parameters by their CeeSafe names, without the compiler's temporaries
ceesafe-bt      the backtrace as `name at file:line`
"""

import os
import sys

import lldb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ceesafe_names  # noqa: E402


def _value(value, depth=0):
    """A value as CeeSafe would write it: a struct with its fields by their CeeSafe names, anything else as lldb shows it."""
    kind = value.GetType().GetCanonicalType().GetTypeClass()
    if kind in (lldb.eTypeClassStruct, lldb.eTypeClassClass) and depth < 3:
        fields = []
        for i in range(value.GetNumChildren()):
            child = value.GetChildAtIndex(i)
            fields.append(f"{ceesafe_names.field(child.GetName())}: {_value(child, depth + 1)}")
        return "{ " + ", ".join(fields) + " }"
    return value.GetValue() or value.GetSummary() or "?"


def _frame(debugger):
    return debugger.GetSelectedTarget().GetProcess().GetSelectedThread().GetSelectedFrame()


def ceesafe_locals(debugger, command, result, internal_dict):
    for variable in _frame(debugger).GetVariables(True, True, False, True):
        name = ceesafe_names.local(variable.GetName())
        if name is not None:
            result.AppendMessage(f"{name} = {_value(variable)}")


def ceesafe_bt(debugger, command, result, internal_dict):
    thread = debugger.GetSelectedTarget().GetProcess().GetSelectedThread()
    for frame in thread:
        entry = frame.GetLineEntry()
        where = f"{entry.GetFileSpec().GetFilename()}:{entry.GetLine()}" if entry.IsValid() else "?"
        result.AppendMessage(f"{ceesafe_names.function(frame.GetFunctionName())} at {where}")


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand("command script add -f ceesafe_lldb.ceesafe_locals ceesafe-locals")
    debugger.HandleCommand("command script add -f ceesafe_lldb.ceesafe_bt ceesafe-bt")
