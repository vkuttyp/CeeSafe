"""
c2cee_port.py -- stage 2 of c2cee (spec/tooling.md §9.4): a first draft of a C file's CeeSafe port, from clang's AST.

The draft is unsafe CeeSafe that mirrors the C statement by statement, with the C names, for a person to finish: what it
cannot translate, or translates with a decision someone must check, carries TODO(c2cee) and the reason.
"""

from __future__ import annotations

import re
from pathlib import Path

RENAMES = {"fn": "callback", "class": "lock_class"}
INT_BITS = {"i8": 8, "u8": 8, "i16": 16, "u16": 16, "i32": 32, "u32": 32, "i64": 64, "u64": 64, "isize": 64,
            "usize": 64}
ORDERS = {0: "Relaxed", 1: "Acquire", 2: "Acquire", 3: "Release", 4: "AcquireRelease", 5: "SequentiallyConsistent"}
VARIADIC_FLOOR = ("panic", "klog", "kprintf", "kwarn", "kinfo", "kdebug", "kerror")
ATOMIC_VIEW = {"u64": "AtomicU64", "i64": "AtomicU64", "u32": "AtomicU32", "i32": "AtomicU32", "usize": "AtomicUSize"}


class Port:
    def __init__(self, c2cee, source: Path, header: Path | None, asts: dict, report: dict, keywords: set,
                 decls: dict, root: Path | None = None):
        self.root = (root or source.parent).resolve()
        self.c2cee = c2cee
        self.source, self.header = source, header
        self.raw = source.read_bytes()
        self.asts, self.report, self.keywords, self.decls = asts, report, keywords, decls
        self.stem = source.stem
        self.typedefs: dict[str, str] = {}
        self.records: dict[str, dict] = {}
        self.statics: dict[str, dict] = {}
        self.functions: dict[str, dict] = {}
        self.release_functions: set[str] = set()
        self.floor_funcs: list[str] = []      # C definitions
        self.floor_decls: list[str] = []      # CeeSafe declarations of them
        self.helpers: dict[str, str] = {}     # CeeSafe helpers (atomic views, wait conditions)
        self.imported_fields: dict[str, dict[str, str]] = {}
        self.callbacks: set[str] = set()
        self.helper_decls: set[str] = set()   # wait_floor_* (wait.h), declared by the draft itself
        self.extern_calls: set[str] = set()
        self.constant_macros: dict[str, str] = {}
        self.todos = 0
        self.counter = 0
        self.regions = self._conditional_regions()
        self.fn_ret = "void"
        self._collect()

    # ---- collection ------------------------------------------------------------------------------------------------

    def _collect(self):
        loc = self.c2cee.Locations()
        for top in self.asts["debug"].get("inner", []):
            loc.update(top)
            file = loc.file
            kind = top.get("kind")
            if kind == "TypedefDecl":
                self.typedefs[top["name"]] = top["type"]["qualType"]
            elif kind == "RecordDecl" and top.get("completeDefinition") and top.get("name"):
                fields = [(f["name"], f["type"].get("desugaredQualType", f["type"]["qualType"]), f["type"]["qualType"])
                          for f in top.get("inner", []) if f.get("kind") == "FieldDecl" and f.get("name")]
                # (name, desugared, written); an anonymous struct or union member has no name, and no port takes
                # such a struct over (analyse refuses it)
                self.records[top["name"]] = {"fields": fields, "file": file}
            elif kind == "VarDecl" and file and Path(file).resolve() == self.source:
                self.statics[top["name"]] = top
            elif kind == "FunctionDecl" and file and Path(file).resolve() == self.source and \
                    any(c.get("kind") == "CompoundStmt" for c in top.get("inner", [])):
                self.functions[top["name"]] = top
        loc = self.c2cee.Locations()
        for top in self.asts["release"].get("inner", []):
            loc.update(top)
            if top.get("kind") == "FunctionDecl" and loc.file and Path(loc.file).resolve() == self.source and \
                    any(c.get("kind") == "CompoundStmt" for c in top.get("inner", [])):
                self.release_functions.add(top["name"])

    def _conditional_regions(self) -> list[tuple[int, int, str]]:
        """The source's #if…#endif regions: (start, end, condition), each #else its own region."""
        regions, stack, offset = [], [], 0
        for line in self.raw.split(b"\n"):
            text = line.decode(errors="replace").strip()
            if m := re.match(r"#\s*(if|ifdef|ifndef)\b\s*(.*)", text):
                stack.append([offset, f"#{m.group(1)} {m.group(2)}".strip()])
            elif re.match(r"#\s*(else|elif)\b", text) and stack:
                start, cond = stack[-1]
                regions.append((start, offset, cond))
                stack[-1] = [offset, f"#else of {cond}"]
            elif re.match(r"#\s*endif\b", text) and stack:
                start, cond = stack.pop()
                regions.append((start, offset, cond))
            offset += len(line) + 1
        return regions

    def conditional(self, node: dict) -> str | None:
        """The innermost #if region a statement is written in, if any (header guards are outside functions)."""
        b = node.get("range", {}).get("begin", {})
        off = b.get("expansionLoc", b).get("offset")
        if off is None:
            return None
        inside = [r for r in self.regions if r[0] <= off < r[1]]
        return min(inside, key=lambda r: r[1] - r[0])[2] if inside else None

    def owned(self, struct: str) -> bool:
        r = self.records.get(struct)
        return bool(r and self.header and r["file"] and Path(r["file"]).resolve() == self.header)

    # ---- types -----------------------------------------------------------------------------------------------------

    def ntype(self, qual: str) -> str:
        """A C type's CeeSafe spelling; typedefs of integers resolved, of structs kept (@ctype)."""
        q = re.sub(r"\s+", " ", qual.strip())
        base = q.replace("const ", "").replace("volatile ", "").strip()
        if base.startswith("enum "):
            # clang gives an enum without negative values unsigned int, and a prototype must match it exactly
            return "u32"
        if base in self.c2cee.NAMED or base in self.c2cee.SCALARS:
            return self.c2cee.ceesafe_type(q)
        if base in self.typedefs and not base.endswith("*"):
            under = self.typedefs[base]
            if "(*)" in under:
                return self.ntype(under)
            if not under.startswith("struct "):
                t = self.c2cee.ceesafe_type(under)
                if t in INT_BITS or t == "bool":
                    return t
        return self.c2cee.ceesafe_type(q)

    def field_name(self, struct: str | None, name: str) -> str:
        if struct and self.owned(struct) and name in self.keywords:
            return RENAMES.get(name, name + "_")
        return name

    def local_name(self, name: str) -> str:
        return name + "_" if name in self.keywords else name

    @staticmethod
    def struct_of(qual: str) -> str | None:
        m = re.search(r"struct (\w+)", qual)
        return m.group(1) if m else None

    # ---- the source ------------------------------------------------------------------------------------------------

    def text_of(self, node: dict) -> str:
        """The C text a node was written as (its expansion, for a macro)."""
        r = node.get("range", {})
        b, e = r.get("begin", {}), r.get("end", {})
        b = b.get("expansionLoc", b)
        e = e.get("expansionLoc", e)
        if "offset" in b and "offset" in e:
            return self.raw[b["offset"]:e["offset"] + e.get("tokLen", 0)].decode(errors="replace")
        return "?"

    def invocation(self, node: dict) -> str:
        """A macro invocation's whole text: clang maps an expansion to the macro's name, so the arguments are read from
        the source, up to the parenthesis that closes them."""
        exp = node.get("range", {}).get("begin", {}).get("expansionLoc", {})
        if "offset" not in exp:
            return self.text_of(node)
        i = exp["offset"] + exp.get("tokLen", 0)
        j = i
        while j < len(self.raw) and self.raw[j:j + 1] in (b" ", b"\t"):
            j += 1
        if self.raw[j:j + 1] != b"(":
            return self.raw[exp["offset"]:i].decode(errors="replace")
        depth, k = 0, j
        while k < len(self.raw):
            c = self.raw[k:k + 1]
            depth += c == b"("
            depth -= c == b")"
            k += 1
            if depth == 0:
                break
        return self.raw[exp["offset"]:k].decode(errors="replace")

    def macro_of(self, node: dict) -> str | None:
        b = node.get("range", {}).get("begin", {})
        exp = b.get("expansionLoc")
        if isinstance(exp, dict) and "offset" in exp and not exp.get("isMacroArgExpansion"):
            tok = self.raw[exp["offset"]:exp["offset"] + exp.get("tokLen", 0)].decode(errors="replace")
            return tok if re.fullmatch(r"[A-Za-z_]\w*", tok) else None
        return None

    def todo(self, why: str) -> str:
        self.todos += 1
        return f"TODO(c2cee): {why}"

    # ---- statements ------------------------------------------------------------------------------------------------

    def stmt(self, n: dict, out: list, ind: str, fn: str):
        kind = n.get("kind")
        cond = self.conditional(n) if kind != "CompoundStmt" else None
        if cond and cond != getattr(self, "_marked", None):
            out.append(f"{ind}// {self.todo(f'written under `{cond}`: this line exists only when that holds; drafted from the debug build')}")
        self._marked = cond
        macro = self.macro_of(n)
        if macro in ("KASSERT",):
            return self.kassert(n, out, ind, fn)
        if macro in ("wait_event", "wait_event_timeout") and kind != "CompoundStmt":
            return self.wait_event(n, macro, out, ind, fn, None)
        if macro == "might_sleep":
            self.helper_decls.add("    fn wait_floor_check_sleep(ip: usize, what: *CChar);")
            out.append(f'{ind}wait_floor_check_sleep(0, "{fn}\\0".ptr as *CChar); // {self.todo("might_sleep: pass callerAddress() if this is an export")}')
            return
        if macro in ("list_for_each_entry", "list_for_each_entry_safe", "WARN", "WARN_ON"):
            out.append(f"{ind}// {self.todo(f'{macro}: ' + self.text_of(n).splitlines()[0])}")
            return
        if kind == "CompoundStmt":
            for c in n.get("inner", []) or []:
                self.stmt(c, out, ind, fn)
        elif kind == "DeclStmt":
            for v in n.get("inner", []):
                if v.get("kind") != "VarDecl":
                    continue
                t = self.ntype(v["type"].get("qualType"))
                init = [c for c in v.get("inner", []) or [] if c.get("kind") not in ("FullComment",)]
                if init:
                    pre: list = []
                    e = self.rvalue(init[0], pre, fn, want=t)
                    out.extend(ind + p for p in pre)
                    out.append(f"{ind}var {self.local_name(v['name'])}: {t} = {e};")
                elif t.startswith("[") or t in INT_BITS or t == "bool" or t.startswith("*"):
                    out.append(f"{ind}var {self.local_name(v['name'])}: {t} = {self.zero(t)};")
                else:
                    why = f"a local {v['name']} of C type {t}: CeeSafe locals cannot hold C state (a floor helper)"
                    out.append(f"{ind}// {self.todo(why)}")
        elif kind == "IfStmt":
            parts = n.get("inner", [])
            pre: list = []
            c = self.cond(parts[0], pre, fn)
            out.extend(ind + p for p in pre)
            out.append(f"{ind}if ({c}) {{")
            self.stmt(parts[1], out, ind + "    ", fn)
            if len(parts) > 2:
                if parts[2].get("kind") == "IfStmt":
                    out.append(f"{ind}}} else {{")
                    self.stmt(parts[2], out, ind + "    ", fn)
                    out.append(f"{ind}}}")
                else:
                    out.append(f"{ind}}} else {{")
                    self.stmt(parts[2], out, ind + "    ", fn)
                    out.append(f"{ind}}}")
            else:
                out.append(f"{ind}}}")
        elif kind == "WhileStmt":
            cond, body = n["inner"][0], n["inner"][1]
            pre: list = []
            c = self.cond(cond, pre, fn)
            if pre:
                out.append(f"{ind}loop {{")
                out.extend(ind + "    " + p for p in pre)
                out.append(f"{ind}    if (!({c})) {{ break; }}")
            else:
                out.append(f"{ind}while ({c}) {{")
            self.stmt(body, out, ind + "    ", fn)
            out.append(f"{ind}}}")
        elif kind == "ForStmt":
            init, _, cond, inc, body = (n.get("inner", []) + [{}] * 5)[:5]
            if self.has(body, "ContinueStmt"):
                out.append(f"{ind}// {self.todo('a for with continue (the increment would be skipped): ' + self.text_of(n).splitlines()[0])}")
                return
            out.append(f"{ind}{{")
            if init:
                self.stmt(init, out, ind + "    ", fn)
            pre: list = []
            c = self.cond(cond, pre, fn) if cond else "true"
            out.append(f"{ind}    while ({c}) {{")
            self.stmt(body, out, ind + "        ", fn)
            if inc:
                self.stmt(inc, out, ind + "        ", fn)
            out.append(f"{ind}    }}")
            out.append(f"{ind}}}")
        elif kind == "DoStmt":
            body, cond = n["inner"][0], n["inner"][1]
            if self.has(body, "ContinueStmt"):
                out.append(f"{ind}// {self.todo('a do-while with continue: ' + self.text_of(n).splitlines()[0])}")
                return
            out.append(f"{ind}loop {{")
            self.stmt(body, out, ind + "    ", fn)
            pre: list = []
            c = self.cond(cond, pre, fn)
            out.extend(ind + "    " + p for p in pre)
            out.append(f"{ind}    if (!({c})) {{ break; }}")
            out.append(f"{ind}}}")
        elif kind == "ReturnStmt":
            if n.get("inner"):
                pre: list = []
                e = self.rvalue(n["inner"][0], pre, fn, want=self.fn_ret)
                out.extend(ind + p for p in pre)
                out.append(f"{ind}return {e};")
            else:
                out.append(f"{ind}return;")
        elif kind == "BreakStmt":
            out.append(f"{ind}break;")
        elif kind == "ContinueStmt":
            out.append(f"{ind}continue;")
        elif kind == "NullStmt":
            pass
        elif kind in ("SwitchStmt", "GotoStmt", "LabelStmt"):
            out.append(f"{ind}// {self.todo(kind + ': ' + self.text_of(n).splitlines()[0])}")
        else:
            pre: list = []
            e = self.effect(n, pre, fn)
            out.extend(ind + p for p in pre)
            if e:
                out.append(f"{ind}{e};")

    def has(self, n: dict, kind: str) -> bool:
        if not n:
            return False
        if n.get("kind") == kind:
            return True
        if n.get("kind") in ("ForStmt", "WhileStmt", "DoStmt", "SwitchStmt") and kind in ("ContinueStmt", "BreakStmt"):
            return False   # belongs to the inner loop
        return any(self.has(c, kind) for c in n.get("inner", []) or [])

    def kassert(self, n: dict, out: list, ind: str, fn: str):
        text = self.invocation(n)
        m = re.match(r"KASSERT\s*\((.*)\)\s*$", text, re.S)
        cond_text = m.group(1).strip() if m else text
        ifs = self.c2cee.find(n, lambda x: x.get("kind") == "IfStmt")
        self.counter += 1
        name = f"{self.stem}_floor_assert_{self.counter}"
        line = n.get("range", {}).get("begin", {}).get("expansionLoc", {}).get("line", 0)
        self.floor_funcs.append(f"void {name}(void)\n{{\n    panic(\"assertion failed: %s at %s:%d (%s)\", {cstr(cond_text)}, "
                                f"\"{self.source.name}\", {line}, \"{fn}\");\n}}")
        self.floor_decls.append(f"    fn {name}();")
        if ifs:
            pre: list = []
            c = self.cond(ifs["inner"][0], pre, fn)   # the macro's !(cond)
            out.extend(ind + p for p in pre)
            out.append(f"{ind}if ({c}) {{")
            out.append(f"{ind}    {name}(); // KASSERT({cond_text})")
            out.append(f"{ind}}}")
        else:
            out.append(f"{ind}// {self.todo('KASSERT: ' + text)}")

    def wait_event(self, n: dict, macro: str, out: list, ind: str, fn: str, result: str | None):
        """wait_event(q, c[, ns]) → wait_floor_until(_timeout) over a @callback condition and a context of its locals."""
        text = self.text_of(n)
        # The condition is the expression the macro tests first (wait_event: in the loop; _timeout: `bool __ok = (cond)`).
        conds = []
        self.c2cee.walk(n, lambda x, f: conds.append(x) if x.get("kind") == "VarDecl" and x.get("name") == "__ok" else None,
                         self.c2cee.Locations())
        cond_node = None
        if conds and conds[0].get("inner"):
            cond_node = conds[0]["inner"][0]
        else:
            loop = self.c2cee.find(n, lambda x: x.get("kind") == "ForStmt")
            ifs = self.c2cee.find(loop or {}, lambda x: x.get("kind") == "IfStmt")
            cond_node = ifs["inner"][0] if ifs else None
        wq = self.c2cee.find(n, lambda x: x.get("kind") == "CallExpr" and
                              (self.callee_name(x) in ("waitqueue_prepare", "wait_timeout_init")))
        if not cond_node or not wq:
            out.append(f"{ind}// {self.todo(macro + ': ' + ' '.join(text.split()))}")
            return "false"
        locals_used: dict[str, str] = {}
        self.c2cee.walk(cond_node, lambda x, f: locals_used.__setitem__(x["referencedDecl"]["name"], x["type"]["qualType"])
                         if x.get("kind") == "DeclRefExpr" and x.get("referencedDecl", {}).get("kind") in ("VarDecl", "ParmVarDecl")
                         and x["referencedDecl"]["name"] not in self.statics else None, self.c2cee.Locations())
        self.counter += 1
        ctx = f"{self.stem.capitalize()}Wait{self.counter}"
        cb = f"{fn}_until_{self.counter}"
        fields = "".join(f"\n    {k}: {self.ntype(v)};" for k, v in sorted(locals_used.items()))
        pre: list = []
        cexpr = self.cond(cond_node, pre, fn)
        body_pre = "".join(f"\n    {p}" for p in pre)
        unpack = "".join(f"\n    let {k} = c.{k};" for k in sorted(locals_used))
        self.helpers[cb] = (f"struct {ctx} {{{fields or chr(10) + '    unused: u8;'}\n}}\n\n"
                            f"/// The condition of {fn}'s {macro}.\n/// Safety: `arg` is the waiter's {ctx}.\n@callback\n"
                            f"unsafe fn {cb}(arg: *mut void) -> bool {{\n    let c = Ptr.toBorrow(arg as *{ctx});{unpack}{body_pre}\n"
                            f"    return {cexpr};\n}}")
        wq_arg = self.rvalue(wq["inner"][2] if self.callee_name(wq) == "wait_timeout_init" else wq["inner"][1], [], fn)
        init = ", ".join(f"{k}: {k}" for k in sorted(locals_used)) or "unused: 0"
        out.append(f"{ind}var wait_ctx_{self.counter} = {ctx} {{ {init} }};")
        arg = f"borrow mut wait_ctx_{self.counter} as *mut {ctx} as *mut void"
        if macro == "wait_event":
            self.helper_decls.add('    fn wait_floor_until(wq: *mut waitqueue, cond: extern "C" fn(*mut void) -> bool, arg: *mut void);')
            out.append(f"{ind}wait_floor_until({wq_arg}, {cb}, {arg});")
            return None
        ns = self.c2cee.find(n, lambda x: x.get("kind") == "CallExpr" and self.callee_name(x) == "timer_start")
        ns_text = self.rvalue(ns["inner"][2], [], fn, want="u64") if ns else self.todo("the timeout")
        self.helper_decls.add('    fn wait_floor_until_timeout(wq: *mut waitqueue, cond: extern "C" fn(*mut void) -> bool, arg: *mut void, '
                              'ns: u64) -> bool;')
        call = f"wait_floor_until_timeout({wq_arg}, {cb}, {arg}, {ns_text})"
        if result is None:
            out.append(f"{ind}{call};")
        return call

    # ---- expressions -----------------------------------------------------------------------------------------------

    def callee_name(self, call: dict) -> str | None:
        ref = self.c2cee.find(call["inner"][0], lambda x: x.get("kind") == "DeclRefExpr")
        return ref["referencedDecl"]["name"] if ref else None

    def strip(self, n: dict) -> dict:
        while n.get("kind") in ("ImplicitCastExpr", "ParenExpr") and n.get("castKind", "NoOp") in \
                ("NoOp", "LValueToRValue", "ArrayToPointerDecay") or n.get("kind") == "ParenExpr":
            n = n["inner"][0]
        return n

    def cond(self, n: dict, pre: list, fn: str) -> str:
        """A condition as a CeeSafe bool."""
        while n.get("kind") in ("ImplicitCastExpr", "ParenExpr") and (n.get("kind") == "ParenExpr" or
                n.get("castKind") in ("IntegralCast", "NoOp", "LValueToRValue") and
                self.ntype(n["inner"][0].get("type", {}).get("qualType", "")) == "bool" or
                n.get("castKind") in ("NoOp", "LValueToRValue")):
            n = n["inner"][0]
        e, et = self.expr(n, pre, fn)
        t = self.ntype(n.get("type", {}).get("qualType", "int"))
        if t == "bool" or et == "bool" or self.is_bool(n):
            return e
        if t.startswith("*") or t.startswith('extern "C" fn'):
            return f"!({e}).isNull()"
        return f"({e}) != 0"

    def is_bool(self, n: dict) -> bool:
        n2 = n
        while n2.get("kind") in ("ImplicitCastExpr", "ParenExpr"):
            if n2.get("castKind") in ("IntegralToBoolean", "PointerToBoolean"):
                return True
            n2 = n2["inner"][0]
        return n2.get("kind") == "BinaryOperator" and n2.get("opcode") in ("==", "!=", "<", ">", "<=", ">=", "&&", "||") \
            or n2.get("kind") == "UnaryOperator" and n2.get("opcode") == "!"

    def effect(self, n: dict, pre: list, fn: str) -> str | None:
        """An expression evaluated for its effect, as a statement."""
        kind = n.get("kind")
        if kind == "CStyleCastExpr" and n["type"]["qualType"] == "void":
            inner = self.strip(n["inner"][0])
            if inner.get("kind") == "DeclRefExpr":
                return None   # (void)x marks x used; CeeSafe does not warn
            return self.effect(n["inner"][0], pre, fn)
        if kind == "ParenExpr":
            return self.effect(n["inner"][0], pre, fn)
        if kind == "UnaryOperator" and n.get("opcode") in ("++", "--"):
            op = "+=" if n["opcode"] == "++" else "-="
            return self.assign(n["inner"][0], f"{op} 1", pre, fn)
        if kind == "BinaryOperator" and n.get("opcode") == "=":
            lhs, rhs = n["inner"]
            v = self.rvalue(rhs, pre, fn, want=self.ntype(lhs["type"]["qualType"]))
            return self.assign(lhs, f"= {v}", pre, fn)
        if kind == "CompoundAssignOperator":
            lhs, rhs = n["inner"]
            v = self.rvalue(rhs, pre, fn, want=self.ntype(lhs["type"]["qualType"]))
            return self.assign(lhs, f"{n['opcode']} {v}", pre, fn)
        return self.rvalue(n, pre, fn)

    def assign(self, lhs: dict, rest: str, pre: list, fn: str) -> str:
        lhs = self.strip(lhs)
        kind = lhs.get("kind")
        if kind == "DeclRefExpr":
            return f"{self.local_name(lhs['referencedDecl']['name'])} {rest}"
        if kind == "MemberExpr":
            base = lhs["inner"][0]
            struct = self.struct_of(base["type"]["qualType"])
            fname = self.field_name(struct, lhs["name"])
            self.note_field(struct, lhs)
            if lhs.get("isArrow"):
                p = self.rvalue(base, pre, fn)
                self.counter += 1
                ref = f"r{self.counter}"
                pre.append(f"let {ref} = Ptr.toBorrowMut({p});")
                return f"{ref}.{fname} {rest}"
            place = self.place(base, pre, fn)
            return f"{place}.{fname} {rest}"
        if kind == "UnaryOperator" and lhs.get("opcode") == "*":
            p = self.rvalue(lhs["inner"][0], pre, fn)
            if rest.startswith("= "):
                return f"({p}).write({rest[2:]})"
            op = rest.split(" ", 1)
            return f"({p}).write(({p}).read() {op[0][:-1]} {op[1]})"
        if kind == "ArraySubscriptExpr":
            return f"{self.place(lhs, pre, fn)} {rest}"
        return f"/* {self.todo('assignment to ' + kind)} */"

    def place(self, n: dict, pre: list, fn: str) -> str:
        """A place to read a field of, or to take the address of."""
        n = self.strip(n)
        kind = n.get("kind")
        if kind == "DeclRefExpr":
            return self.local_name(n["referencedDecl"]["name"])
        if kind == "MemberExpr":
            base = n["inner"][0]
            struct = self.struct_of(base["type"]["qualType"])
            self.note_field(struct, n)
            fname = self.field_name(struct, n["name"])
            if n.get("isArrow"):
                return f"Ptr.toBorrowMut({self.rvalue(base, pre, fn)}).{fname}"
            return f"{self.place(base, pre, fn)}.{fname}"
        if kind == "ArraySubscriptExpr":
            arr, idx = n["inner"]
            i = self.rvalue(idx, pre, fn, want="usize")
            return f"{self.place(arr, pre, fn)}[{i}]"
        if kind == "UnaryOperator" and n.get("opcode") == "*":
            return f"Ptr.toBorrowMut({self.rvalue(n['inner'][0], pre, fn)})"
        return f"/* {self.todo('a place of kind ' + str(kind))} */"

    def note_field(self, struct: str | None, member: dict):
        if struct and not self.owned(struct):
            self.imported_fields.setdefault(struct, {})[member["name"]] = member["type"]["qualType"]

    def cast(self, e: str, src: str, dst: str) -> str:
        if src == dst or not dst:
            return e
        if src in INT_BITS and dst in INT_BITS:
            widening = INT_BITS[dst] > INT_BITS[src] and (src.startswith("u") or dst.startswith("i")) \
                or INT_BITS[dst] == INT_BITS[src] and src[0] == dst[0]
            return f"({e}) as {dst}" if widening else f"truncate<{dst}>({e})"
        if src == "bool" and dst in INT_BITS:
            return f"(if ({e}) 1 else 0)"
        if src.startswith("*") and dst.startswith("*") or src in INT_BITS and dst.startswith("*") or \
                src.startswith("*") and dst in INT_BITS:
            return f"({e}) as {dst}"
        return e

    def rvalue(self, n: dict, pre: list, fn: str, want: str | None = None) -> str:
        e, t = self.expr(n, pre, fn)
        if want and t and want != t and not e.lstrip("-").isdigit():
            return self.cast(e, t, want)
        return e

    def expr(self, n: dict, pre: list, fn: str) -> tuple[str, str]:
        kind = n.get("kind")
        qual = n.get("type", {}).get("qualType", "")
        t = self.ntype(qual) if qual else ""
        macro = self.macro_of(n)
        if macro in ("wait_event_timeout",) and kind == "StmtExpr":
            return self.wait_event(n, macro, pre, "", fn, "value") or "false", "bool"
        if kind == "ParenExpr":
            e, it = self.expr(n["inner"][0], pre, fn)
            return f"({e})", it
        if kind == "ImplicitCastExpr" or kind == "CStyleCastExpr":
            ck = n.get("castKind")
            inner = n["inner"][0]
            e, it = self.expr(inner, pre, fn)
            if ck in ("LValueToRValue", "NoOp", "FunctionToPointerDecay", "ArrayToPointerDecay", "ToVoid"):
                return e, it if ck != "ToVoid" else "void"
            if ck == "IntegralToBoolean":
                lit = self.strip(inner)
                if lit.get("kind") == "IntegerLiteral":
                    return ("false" if lit.get("value") == "0" else "true"), "bool"
                if self.is_bool(inner):
                    return e, "bool"   # a C comparison is an int; in CeeSafe it is already a bool
                return f"({e}) != 0", "bool"
            if ck == "PointerToBoolean":
                return f"!({e}).isNull()", "bool"
            if ck == "NullToPointer":
                return f"0 as {t}", t
            if ck == "IntegralCast":
                if inner.get("kind") == "IntegerLiteral" or e.lstrip("-").isdigit():
                    return e, t
                return self.cast(e, it, t), t
            return self.cast(e, it, t), t
        if kind == "IntegerLiteral":
            return n.get("value", "0"), t
        if kind == "CharacterLiteral":
            return str(n.get("value", 0)), t
        if kind == "StringLiteral":
            v = n.get("value", '""')
            return f'{v[:-1]}\\0".ptr as *CChar', "*CChar"
        if kind == "DeclRefExpr":
            d = n["referencedDecl"]
            name = d["name"]
            if d.get("kind") == "FunctionDecl":
                if name in self.functions:
                    self.callbacks.add(name)
                return name, t
            if d.get("kind") == "EnumConstantDecl":
                return f"/* {self.todo('enum constant ' + name)} */ 0", t
            return self.local_name(name), t
        if kind == "MemberExpr":
            base = n["inner"][0]
            struct = self.struct_of(base["type"]["qualType"])
            self.note_field(struct, n)
            fname = self.field_name(struct, n["name"])
            if n.get("isArrow"):
                p, pt = self.expr(base, pre, fn)
                const = pt.replace("*mut ", "*") if pt.startswith("*mut ") else pt
                return f"Ptr.toBorrow({p} as {const}).{fname}", t
            return f"{self.place(base, pre, fn)}.{fname}", t
        if kind == "ArraySubscriptExpr":
            return self.place(n, pre, fn), t
        if kind == "UnaryOperator":
            op = n["opcode"]
            inner = n["inner"][0]
            if op == "&":
                return f"borrow mut {self.place(inner, pre, fn)} as {t}", t
            if op == "*":
                e, _ = self.expr(inner, pre, fn)
                return f"({e}).read()", t
            if op == "!":
                return f"!({self.cond(inner, pre, fn)})", "bool"
            if op == "-":
                return f"-{self.rvalue(inner, pre, fn, want=t)}", t
            if op == "~":
                e = self.rvalue(inner, pre, fn, want=t)
                ones = "0xFFFFFFFFFFFFFFFF" if INT_BITS.get(t, 32) == 64 else "0xFFFFFFFF"
                return f"({e} ^ {ones})", t
            if op in ("++", "--"):
                return f"/* {self.todo(op + ' inside an expression: ' + self.text_of(n))} */", t
            return f"/* {self.todo('unary ' + op)} */", t
        if kind == "BinaryOperator":
            op = n["opcode"]
            a, b = n["inner"]
            if op in ("&&", "||"):
                return f"{self.cond(a, pre, fn)} {op} {self.cond(b, pre, fn)}", "bool"
            if op in ("==", "!=") and (self.is_null(a) or self.is_null(b)):
                other = b if self.is_null(a) else a
                e, _ = self.expr(other, pre, fn)
                return (f"({e}).isNull()" if op == "==" else f"!({e}).isNull()"), "bool"
            lit_node = a
            while lit_node.get("kind") in ("ImplicitCastExpr", "CStyleCastExpr", "ParenExpr"):
                lit_node = lit_node["inner"][0]
            if op in ("<<", ">>", "&", "|", "^") and lit_node.get("kind") == "IntegerLiteral" and t in INT_BITS and t != "i32":
                lit = lit_node.get("value", "0")
                return f"({lit} as {t}) {op} {self.rvalue(b, pre, fn, want=t if op not in ('<<', '>>') else None)}", t
            if op == ",":
                return f"/* {self.todo('the comma operator')} */", t
            at = self.ntype(a["type"]["qualType"])
            if op in ("==", "!=", "<", ">", "<=", ">="):
                return f"{self.rvalue(a, pre, fn)} {op} {self.rvalue(b, pre, fn, want=at)}", "bool"
            return f"{self.rvalue(a, pre, fn, want=t)} {op} {self.rvalue(b, pre, fn, want=t)}", t
        if kind == "ConditionalOperator":
            c, a, b = n["inner"]
            return f"if ({self.cond(c, pre, fn)}) {self.rvalue(a, pre, fn, want=t)} else {self.rvalue(b, pre, fn, want=t)}", t
        if kind == "CallExpr":
            return self.call(n, pre, fn, t)
        if kind == "AtomicExpr":
            return self.atomic(n, pre, fn, t)
        if kind == "UnaryExprOrTypeTraitExpr" and n.get("name") == "sizeof":
            arg = n.get("argType", {}).get("qualType") or (n.get("inner") or [{}])[0].get("type", {}).get("qualType", "?")
            return f"layoutOf<{self.ntype(arg)}>().size", "usize"
        if kind == "StmtExpr" or macro:
            return f"/* {self.todo((macro or kind) + ': ' + ' '.join(self.text_of(n).split()))} */", t
        return f"/* {self.todo('expression ' + str(kind))} */", t

    def is_null(self, n: dict) -> bool:
        while n.get("kind") in ("ImplicitCastExpr", "ParenExpr", "CStyleCastExpr"):
            if n.get("castKind") == "NullToPointer":
                return True
            n = n["inner"][0]
        return False

    def call(self, n: dict, pre: list, fn: str, t: str) -> tuple[str, str]:
        callee = n["inner"][0]
        args = n["inner"][1:]
        name = self.callee_name(n)
        ref = self.c2cee.find(callee, lambda x: x.get("kind") == "DeclRefExpr")
        if name and ref and ref["referencedDecl"].get("kind") == "FunctionDecl":
            if name == "__builtin_return_address":
                return "callerAddress()", "usize"
            if name in ("__builtin_expect",):
                return self.rvalue(args[0], pre, fn), t
            if name == "__atomic_thread_fence":
                # CeeSafe has no fence (spec/tooling.md §9.1): one in the floor, with the C's order.
                self.counter += 1
                floor = f"{self.stem}_floor_fence_{self.counter}"
                order = self.invocation(args[0]) if args and self.macro_of(args[0]) else (self.text_of(args[0]) if args else "__ATOMIC_SEQ_CST")
                self.floor_funcs.append(f"void {floor}(void)\n{{\n    __atomic_thread_fence({order});\n}}")
                self.floor_decls.append(f"    fn {floor}();")
                return f"{floor}()", "void"
            d = self.decls.get(name, {})
            if "variadic" in d.get("kinds", {}).values():
                return self.floor_variadic(name, args, pre, fn, n), t
            params = self.param_types(d.get("type", ""))
            vals = [self.rvalue(a, pre, fn, want=params[i] if i < len(params) else None) for i, a in enumerate(args)]
            if name not in self.functions:
                self.extern_calls.add(name)
            return f"{name}({', '.join(vals)})", t
        # through a function pointer, usually a member
        f, _ = self.expr(callee, pre, fn)
        self.counter += 1
        pre.append(f"let f{self.counter} = {f};")
        vals = [self.rvalue(a, pre, fn) for a in args]
        return f"f{self.counter}({', '.join(vals)})", t

    def param_types(self, ftype: str) -> list[str]:
        m = re.match(r"[^(]*\((.*)\)\s*$", ftype)
        return [self.ntype(p) for p in self.c2cee.split_params(m.group(1))] if m else []

    def floor_variadic(self, name: str, args: list, pre: list, fn: str, call: dict | None = None) -> str:
        """One floor function per call of a variadic C function: the format fixed, the other arguments passed. A call
        made through a macro (kwarn, kinfo over klog) calls the macro, as the C did."""
        self.counter += 1
        callee = name
        macro = self.macro_of(call) if call else None
        if macro and macro != name and re.fullmatch(r"k(warn|info|debug|err|error|notice)|pr_\w+|printk", macro):
            callee = macro
        at = next((i for i, a in enumerate(args) if self.c2cee.find(a, lambda x: x.get("kind") == "StringLiteral")), None)
        if at is None:
            return f"/* {self.todo(name + ' without a literal format')} */"
        fmt = self.c2cee.find(args[at], lambda x: x.get("kind") == "StringLiteral")
        fixed = [self.text_of(a) for a in args[:at]] if callee == name else []
        values = args[at + 1:]
        ctypes = [a.get("type", {}).get("qualType", "int") for a in values]
        floor = f"{self.stem}_floor_{callee}_{self.counter}"
        params = ", ".join(f"{c} a{i}" for i, c in enumerate(ctypes)) or "void"
        head = ", ".join(fixed + [fmt.get("value", '""')])
        fargs = "".join(f", a{i}" for i in range(len(ctypes)))
        self.floor_funcs.append(f"void {floor}({params})\n{{\n    {callee}({head}{fargs});\n}}")
        nparams = ", ".join(f"a{i}: {self.ntype(c)}" for i, c in enumerate(ctypes))
        self.floor_decls.append(f"    fn {floor}({nparams});")
        vals = [self.rvalue(a, pre, fn, want=self.ntype(c)) for a, c in zip(values, ctypes)]
        return f"{floor}({', '.join(vals)})"

    def atomic(self, n: dict, pre: list, fn: str, t: str) -> tuple[str, str]:
        op = n.get("name", "")
        inner = n.get("inner", [])
        ptr = inner[0]
        pt = self.ntype(ptr["type"]["qualType"])
        target = pt.replace("*mut ", "").replace("*", "")
        view = ATOMIC_VIEW.get(target) or ("AtomicUSize" if target.startswith("*") else None)
        if not view:
            return f"/* {self.todo(f'{op} on a {target} (a bool needs a u32)')} */", t
        helper = f"atomic_{view[6:].lower()}"
        cast_to = {"AtomicU64": "u64", "AtomicU32": "u32", "AtomicUSize": "usize"}[view]
        self.helpers[helper] = (f"/// An atomic view of a word only ever accessed atomically.\n/// Safety: `p` is such a word.\n"
                                f"unsafe fn {helper}(p: *mut {cast_to}) -> borrow(static) {view} => Ptr.toBorrow(p as *{view});")
        p = self.rvalue(ptr, pre, fn)
        p = f"{p} as *mut {cast_to}" if target != cast_to else p
        order_vals = [self.order(x) for x in inner[1:] if self.order(x) is not None]
        order = order_vals[0] if order_vals else "SequentiallyConsistent"
        vals = [self.rvalue(x, pre, fn, want=target if target in INT_BITS else None) for x in inner[1:] if self.order(x) is None]
        v = f"{helper}({p})"
        if op == "__atomic_load_n":
            return f"{v}.loadWith(LoadOrdering.{'Acquire' if order in ('Acquire', 'AcquireRelease') else order})", target
        if op == "__atomic_store_n":
            return f"{v}.storeWith({vals[0]}, StoreOrdering.{'Release' if order in ('Release', 'AcquireRelease') else order})", "void"
        if op in ("__atomic_fetch_add", "__atomic_fetch_sub"):
            return f"{v}.fetch{'Add' if 'add' in op else 'Sub'}With({vals[0]}, Ordering.{order})", target
        if op in ("__atomic_add_fetch", "__atomic_sub_fetch"):
            sign = "+" if "add" in op else "-"
            return f"({v}.fetch{'Add' if 'add' in op else 'Sub'}With({vals[0]}, Ordering.{order}) {sign} {vals[0]})", target
        return f"/* {self.todo(op)} */", t

    def order(self, n: dict) -> str | None:
        n = self.strip(n)
        while n.get("kind") == "ImplicitCastExpr":
            n = n["inner"][0]
        if n.get("kind") == "IntegerLiteral" and self.macro_of(n) and self.macro_of(n).startswith("__ATOMIC_"):
            return ORDERS.get(int(n["value"]))
        return None

    def zero(self, t: str) -> str:
        if self.owned(t):
            fields = ", ".join(f"{self.field_name(t, f)}: {self.zero(self.ntype(d if '(*)' in d else q))}"
                               for f, d, q in self.records[t]["fields"])
            return f"{t} {{ {fields} }}"
        if t.startswith("extern \"C\" fn"):
            return f"0 as {t}"
        if t.startswith("["):
            m = re.match(r"\[(.*); (\d+)\]$", t)
            return f"[{self.zero(m.group(1))}; {m.group(2)}]" if m else "0"
        if t.startswith("*"):
            return f"0 as {t}"
        return "false" if t == "bool" else "0"

    # ---- functions -------------------------------------------------------------------------------------------------

    def function(self, f: dict) -> str:
        name = f["name"]
        qual = f["type"]["qualType"]
        self.fn_ret = self.ntype(qual.split("(")[0].strip())
        params = [p for p in f.get("inner", []) if p.get("kind") == "ParmVarDecl"]
        sig = ", ".join(f"{self.local_name(p.get('name', '_'))}: {self.ntype(p['type']['qualType'])}"
                        for p in params)
        body = [c for c in f["inner"] if c.get("kind") == "CompoundStmt"][0]
        out: list[str] = []
        self.stmt(body, out, "        ", name)
        notes = []
        start = f.get("range", {}).get("begin", {}).get("offset")
        end = f.get("range", {}).get("end", {}).get("offset")
        if start is not None and end is not None and re.search(rb"^\s*#\s*if", self.raw[start:end], re.M):
            notes.append(self.todo("this function has #if blocks; drafted from the debug build, so the release build differs"))
        if name not in self.release_functions:
            notes.append(self.todo("only in the debug build (#if CONFIG_DEBUG): the port must keep it out of the release one"))
        report = next((r for r in self.report["functions"] if r["name"] == name), {})
        attrs = []
        if report.get("exported") or not f.get("storageClass") == "static":
            attrs.append(f'@export("{name}")')
        doc = [f"/// {n}" for n in notes] + [f"/// Safety: {self.todo('what the caller guarantees')}"]
        head = "\n".join(doc + attrs)
        ret = "" if self.fn_ret == "void" else f" -> {self.fn_ret}"
        return f"{head}\nunsafe fn {name}({sig}){ret} {{\n    unsafe {{\n" + "\n".join(out) + "\n    }\n}"

    # ---- the files -------------------------------------------------------------------------------------------------

    def draft(self) -> dict[str, str]:
        fns = [self.function(self.functions[n]) for n in self.functions]
        # A static function the file passes as a function pointer needs a C address (type-system.md §34.1).
        fns = [text.replace("\nunsafe fn ", "\n@callback\nunsafe fn ", 1) if n in self.callbacks and
               self.functions[n].get("storageClass") == "static" else text for n, text in zip(self.functions, fns)]
        ceesafe_statics, floor_statics = [], []
        for name, v in self.statics.items():
            if v.get("storageClass") == "extern" or v["type"]["qualType"].startswith("const "):
                continue
            t = self.ntype(v["type"]["qualType"])
            init = [c for c in v.get("inner", []) or []]
            macro = self.macro_of(init[0]) if init else None
            ctype = v["type"]["qualType"]
            inv = self.invocation(init[0]) if init and macro else ""
            if init and macro and not re.search(rf"\b{re.escape(name)}\b", inv) and macro.endswith("_INIT"):
                args = inv
                lit = re.sub(r'"([^"]*)"', r'"\1\\0".ptr as *CChar', args)
                self.constant_macros[macro] = self.ntype(ctype)
                ceesafe_statics.append(f"static mut {name}: {t} = {lit};")
            elif not init and (t in INT_BITS or t == "bool" or t.startswith("*") or t.startswith("[") or self.owned(t)):
                ceesafe_statics.append(f"static mut {name}: {t} = {self.zero(t)};")
            else:
                text = f"static {ctype} {name}" + (f" = {self.invocation(init[0]) if macro else self.text_of(init[0])}" if init else "")
                floor_statics.append((name, ctype, text))
                self.floor_decls.append(f"    fn {self.stem}_floor_{name}() -> *mut {t};")
                self.floor_funcs.append(f"struct {ctype.replace('struct ', '')} *{self.stem}_floor_{name}(void)\n{{\n    return &{name};\n}}"
                                        if ctype.startswith("struct ") else
                                        f"{ctype} *{self.stem}_floor_{name}(void)\n{{\n    return &{name};\n}}")
        # A static the floor keeps is reached through its accessor.
        for name, ctype, _ in floor_statics:
            def sub(f, name=name):
                f = re.sub(rf"(?<![\w.]){name}(?!\w)", f"Ptr.toBorrowMut({self.stem}_floor_{name}())", f)
                return f.replace(f"borrow mut Ptr.toBorrowMut({self.stem}_floor_{name}()) as ", f"{self.stem}_floor_{name}() as ")
            fns = [sub(f) for f in fns]
            self.helpers = {k: sub(v) for k, v in self.helpers.items()}
        fns = [self.hoist(f) for f in fns]
        ceesafe = self.ceesafe_file(fns, ceesafe_statics)
        floor = self.floor_file(floor_statics)
        build = self.build_file(floor_statics)
        return {f"{self.stem}.cee": ceesafe, f"{self.stem}_floor.c": floor, "BUILD.md": build}

    def ceesafe_file(self, fns: list[str], statics: list[str]) -> str:
        def rel(p):
            if not p:
                return "?"
            full = str(Path(p).resolve())
            if "/include/" in full:
                return full.split("/include/")[-1]   # as #include names it under CosmoOS's include paths
            return str(Path(full).relative_to(self.source.parent)) if full.startswith(str(self.source.parent)) else Path(full).name
        lines = [f"// DRAFT by c2cee (spec/tooling.md §9.4) from {self.source.name}: unsafe CeeSafe that mirrors the C. Finish",
                 "// every TODO(c2cee), review each line beside the C, then run `c2cee.py verify`.", ""]
        owned = [n for n in self.records if self.owned(n)]
        headers, plain = {}, []
        for name in sorted(self.extern_calls):
            d = self.decls.get(name, {})
            hnote = next((h["note"] for h in self.report["headers"] if h["header"].endswith(rel(d.get("file")))), None)
            sig = self.extern_sig(name, d.get("type", ""))
            if d.get("file") and not hnote and Path(d["file"]).resolve() != self.source:
                headers.setdefault(rel(d["file"]), []).append(sig)
            else:
                plain.append(sig)
        imported = sorted({s for s in re.findall(r"\b(\w+)\b", " ".join(fns) + " ".join(statics))
                           if s in self.records and not self.owned(s)} | set(self.imported_fields))
        typedef_structs = sorted({n for n, under in self.typedefs.items() if under.startswith("struct ")
                                  and re.search(rf"\b{re.escape(n)}\b", " ".join(fns) + " ".join(statics))})
        all_headers = sorted(headers) + ([] if not self.header else [])
        decl_lines = []
        for td in typedef_structs:
            decl_lines += [f'    @ctype("{td}")', f"    struct {td};"]
        for s in imported:
            fields = self.imported_fields.get(s, {})
            if fields:
                decl_lines.append(f"    struct {s} {{")
                for fname, ft in sorted(fields.items()):
                    nf = fname if fname not in self.keywords else fname + "_"
                    cn = f'        @cname("{fname}")\n' if fname in self.keywords else ""
                    decl_lines.append(f"{cn}        {nf}: {self.ntype(ft)};")
                decl_lines.append("    }")
            else:
                decl_lines.append(f"    struct {s};")
        for macro, t in sorted(self.constant_macros.items()):
            decl_lines += ["    @constant", f"    fn {macro}(name: *CChar) -> {t}; // {self.todo('check the macro’s parameters')}"]
        for h in sorted(headers):
            decl_lines += sorted(headers[h])
        if all_headers or decl_lines:
            lines.append("@header(" + ", ".join(f'"{h}"' for h in all_headers) + ")")
            lines.append('extern "C" {')
            lines += decl_lines
            lines.append("}")
            lines.append("")
        if plain or self.floor_decls or self.helper_decls:
            lines.append("// Without a header (each would include the port's header back), and the floor's (" +
                         f"{self.stem}_floor.c).")
            lines.append('extern "C" {')
            lines += sorted(plain) + sorted(self.helper_decls) + self.floor_decls
            lines.append("}")
            lines.append("")
        for s in owned:
            lines.append("@repr(C)")
            lines.append(f"struct {s} {{")
            for fname, desugared, qual in self.records[s]["fields"]:
                ft = self.ntype(desugared if "(*)" in desugared else qual)
                nm = self.field_name(s, fname)
                note = f" // was `{fname}` (a CeeSafe keyword): rename the C member" if nm != fname else ""
                lines.append(f"    {nm}: {ft};{note}")
            lines.append("}")
            lines.append("")
        lines += statics + ([""] if statics else [])
        lines += [h + "\n" for h in self.helpers.values()]
        lines += [f + "\n" for f in fns]
        lines.append(f"// {self.todos} TODO(c2cee) in this draft.")
        return "\n".join(lines) + "\n"

    @staticmethod
    def hoist(text: str) -> str:
        """CeeSafe assigns only to places reached through variables: an assignment through Ptr.toBorrowMut(…) takes a `let`
        of the borrow first."""
        out = []
        for line in text.split("\n"):
            m = re.match(r"^(\s*)(Ptr\.toBorrowMut\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))(.*?) (=|\+=|-=|\*=|\|=|&=|\^=|<<=|>>=) (.*);(.*)$", line)
            if m:
                ind, borrow, rest, op, value, tail = m.groups()
                out.append(f"{ind}{{ let place = {borrow}; place{rest} {op} {value}; }}{tail}")
            else:
                out.append(line)
        return "\n".join(out)

    def extern_sig(self, name: str, ftype: str) -> str:
        m = re.match(r"(.*?)\((.*)\)\s*$", ftype)
        if not m:
            return f"    fn {name}(); // {self.todo('the signature: ' + ftype)}"
        params = self.c2cee.split_params(m.group(2))
        ret = self.ntype(m.group(1).strip())
        ps = ", ".join(f"a{i}: {self.ntype(p)}" for i, p in enumerate(params))
        return f"    fn {name}({ps})" + ("" if ret == "void" else f" -> {ret}") + ";"

    def floor_file(self, statics) -> str:
        includes = sorted(set(re.findall(r'^\s*#\s*include\s*([<"][^>"]+[>"])', self.raw.decode(errors="replace"), re.M)))
        out = [f"/*\n * {self.stem}_floor.c - DRAFT by c2cee (spec/tooling.md §9.4): the C under {self.stem}.cee.\n *",
               " * What CeeSafe cannot express yet: the formatted messages of variadic calls, statics of C types, and the",
               " * module exports. Review it as C that stays.\n */", ""]
        out += [f"#include {i}" for i in includes] + [""]
        protos = [re.match(r"^([^{]+?)\n\{", f).group(1).strip() + ";" for f in self.floor_funcs if re.match(r"^([^{]+?)\n\{", f)]
        # File-scope static assertions stay C's (spec §9.4): the floor sees the same headers.
        asserts = re.findall(r"^(?:STATIC_ASSERT|_Static_assert)\s*\(.*?\);", self.raw.decode(errors="replace"), re.M | re.S)
        if asserts:
            out += asserts + [""]
        out += ["/* Declared for the CeeSafe port only. */"] + protos + [""]
        for name, ctype, text in statics:
            out.append(f"{text};")
        out.append("")
        out += [f + "\n" for f in self.floor_funcs]
        exports = re.findall(r"^\s*EXPORT_SYMBOL\(\s*\w+\s*\);", self.raw.decode(errors="replace"), re.M)
        if exports:
            out += ["/* Module exports (docs/kernel/module/api.md). */"] + [e.strip() for e in exports]
        return "\n".join(out) + "\n"

    def build_file(self, statics) -> str:
        src = str(self.source.relative_to(self.root)) if str(self.source).startswith(str(self.root)) else self.source.name
        nova = src[:-2] + ".nova"  # CosmoOS keeps its ports as Nova (CeeSafe's Decision 0003)
        hdr = None
        if self.header:
            hdr = str(self.header).split("/kernel/include/")[-1] if "/kernel/include/" in str(self.header) else self.header.name
        types_h = None if not hdr else hdr.replace(".h", "_types.h")
        renamed = [f"`{f}` → `{self.field_name(s, f)}` in struct {s}" for s in self.records if self.owned(s)
                   for f, _, _ in self.records[s]["fields"] if self.field_name(s, f) != f]
        lines = [f"# Building the {self.stem} port (DRAFT by c2cee)", "",
                 f"- Check the finished port with ceesafec first: `ceesafec check --profile freestanding --kernel cosmoos --no-float {self.stem}.cee`.",
                 f"- `scripts/nova-gen.py`, in `PORTS`:",
                 f'  `("{nova}", "{src}", "TODO: title", ' + (f'"kernel/include/{types_h}"' if types_h else "None") + ", False),`",
                 f"- `kernel/kernel.mk`: add `{src[:-2]}_floor.c` after `{src}`.",
                 f"- `tests/host/host.mk`: every test that links `{src}` also links `{src[:-2]}_floor.c`, "
                 "`kernel/nova/nova_rt_core.c` and `tests/host/nova_panic.c`.",
                 f"- Copy `{self.stem}.cee` to `{nova}` (the same language as Nova at the fork) and `{self.stem}_floor.c` to "
                 f"`{src[:-2]}_floor.c`; `make nova` writes `{src}` with CosmoOS's pinned novac."]
        if hdr:
            lines.append(f"- `{hdr}`: replace the definitions of {', '.join('`struct ' + s + '`' for s in self.records if self.owned(s)) or 'its structs'} "
                         f"with `#include <{types_h}>` (a comment naming the members keeps it readable).")
        if renamed:
            lines.append("- Renamed members (every C user follows; `c2cee.py analyse --header` lists them): " + "; ".join(renamed) + ".")
        if statics:
            lines.append("- Statics that stay in C (the floor): " + ", ".join(f"`{n}`" for n, _, _ in statics) + ".")
        lines.append("- Then `c2cee.py verify`, including the release build and boot.")
        return "\n".join(lines) + "\n"


def cstr(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
