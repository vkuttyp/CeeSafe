#!/usr/bin/env python3
"""Compares `ceesafec lsp` and `ceesafec mcp` with the pinned novac's servers (docs/p8-plan.md S5).

LSP: for each corpus file, one session opens the file, asks for its symbols, its code actions over the whole file, its
formatting, and hover and definition at the start of every word and one character into it, then changes the text and
closes it. Hand-written sessions cover the protocol's edges (parse errors, unknown methods, missing members, positions
in non-ASCII text, exit without shutdown) and a document in a package.

MCP: for each corpus file, one session calls check, fix, format, emit_c with every report, symbol at each word, and
for the run families run (with arguments and standard input). Hand-written sessions cover the protocol (every version,
parse errors, requests without a method, notifications, line ends), every resource, both prompts, explain for every
code the documents' tables name, spec_search and spec_section, arguments of the wrong kind and paths on disk.

Both servers get the same bytes, and must answer with the same bytes and exit status once ceesafec's names are mapped
back (tools/names.py) and the version in serverInfo is normalised.

usage: python3 tools/compare_servers.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root NOVA_CHECKOUT
       [--jobs N] [--only lsp|mcp] [--show N] [files...]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from names import map_back

FAMILIES = ("parse-pass", "parse-fail", "check-pass", "check-fail", "run-pass", "run-fail")


def frame(message):
    body = json.dumps(message, ensure_ascii=False).encode() if not isinstance(message, bytes) else message
    return b"Content-Length: %d\r\n\r\n" % len(body) + body


def utf16_position(text, offset):
    """The LSP position (line, UTF-16 character) of a str offset."""
    line = text.count("\n", 0, offset)
    start = text.rfind("\n", 0, offset) + 1
    return line, len(text[start:offset].encode("utf-16-le")) // 2


def lsp_session(uri, text, dense=False):
    messages = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "initialized", "params": {}},
                {"jsonrpc": "2.0", "method": "textDocument/didOpen",
                 "params": {"textDocument": {"uri": uri, "languageId": "nova", "version": 1, "text": text}}}]
    document = {"uri": uri}
    next_id = 2

    def request(method, params):
        nonlocal next_id
        messages.append({"jsonrpc": "2.0", "id": next_id, "method": method, "params": params})
        next_id += 1

    request("textDocument/documentSymbol", {"textDocument": document})
    end_line = text.count("\n") + 1
    request("textDocument/codeAction", {"textDocument": document,
                                        "range": {"start": {"line": 0, "character": 0},
                                                  "end": {"line": end_line, "character": 0}},
                                        "context": {"diagnostics": []}})
    request("textDocument/formatting", {"textDocument": document, "options": {"tabSize": 4, "insertSpaces": True}})
    offsets = range(len(text) + 1) if dense else sorted(
        {o for m in re.finditer(r"\w+", text) for o in (m.start(), min(m.start() + 1, m.end() - 1))})
    for offset in offsets:
        line, character = utf16_position(text, offset)
        position = {"line": line, "character": character}
        request("textDocument/hover", {"textDocument": document, "position": position})
        request("textDocument/definition", {"textDocument": document, "position": position})
    messages.append({"jsonrpc": "2.0", "method": "textDocument/didChange",
                     "params": {"textDocument": {"uri": uri, "version": 2},
                                "contentChanges": [{"text": text + "\nfn added() -> i32 => 1;\n"}]}})
    request("textDocument/documentSymbol", {"textDocument": document})
    messages.append({"jsonrpc": "2.0", "method": "textDocument/didClose", "params": {"textDocument": document}})
    request("textDocument/hover", {"textDocument": document, "position": {"line": 0, "character": 0}})
    request("shutdown", None)
    messages.append({"jsonrpc": "2.0", "method": "exit"})
    return b"".join(frame(m) for m in messages)


def edge_sessions():
    """Hand-written sessions over the protocol's edges: (name, input bytes)."""
    sessions = []
    init = frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    done = frame({"jsonrpc": "2.0", "id": 99, "method": "shutdown"}) + frame({"jsonrpc": "2.0", "method": "exit"})
    sessions.append(("not json", init + frame(b"{nope") + frame(b"[1,2]") + frame(b'"text"') + done))
    sessions.append(("unknown method", init + frame({"jsonrpc": "2.0", "id": "x", "method": "workspace/symbol"}) +
                     frame({"jsonrpc": "2.0", "method": "custom/notify"}) + done))
    sessions.append(("missing members", init + frame({"jsonrpc": "2.0", "id": 2, "method": "textDocument/hover"}) +
                     frame({"jsonrpc": "2.0", "id": 3, "method": "textDocument/didOpen", "params": {}}) +
                     frame({"jsonrpc": "2.0", "id": 4, "method": "textDocument/hover",
                            "params": {"textDocument": {"uri": "file:///nowhere.nova"},
                                       "position": {"line": 0, "character": 0}}}) +
                     frame({"jsonrpc": "2.0", "id": 5, "method": "textDocument/documentSymbol",
                            "params": {"textDocument": {"uri": "file:///nowhere.nova"}}}) + done))
    sessions.append(("ids", init + frame({"jsonrpc": "2.0", "id": None, "method": "shutdown"}) +
                     frame({"jsonrpc": "2.0", "id": 1.5, "method": "shutdown"}) +
                     frame({"jsonrpc": "2.0", "id": {"a": [1]}, "method": "shutdown"}) +
                     frame({"jsonrpc": "2.0", "id": 1, "result": {}}) + done))
    sessions.append(("exit without shutdown", init + frame({"jsonrpc": "2.0", "method": "exit"})))
    sessions.append(("end of input", init))
    sessions.append(("headers", b"content-length: 65\r\nContent-Type: x\r\n\r\n" +
                     json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode().ljust(65) +
                     b"\r\n\r\n" + done))
    text = 'fn main() {\n    let é = "a\\"b+`&\'<>";\n    let 𝕏 = 1;\n    é;\n}\nfn f(x: i32) -> i32 => x + 𝕏;\n'
    uri = "file:///tmp/a%20b.nova"
    sessions.append(("non-ascii", lsp_session(uri, text)))
    sessions.append(("freestanding", lsp_session("file:///tmp/f.nova", "// profile: freestanding\nfn f() -> i32 => 1;\n")))
    sessions.append(("not a file uri", lsp_session("untitled:Untitled-1", "fn main() { let x: i32 = true; }\n")))
    return sessions


def serve(compiler, arguments, data, cwd, env=None):
    try:
        p = subprocess.run([compiler] + arguments, input=data, capture_output=True, cwd=cwd, timeout=600, env=env)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "timeout", b"", b""


def mcp_line(method, params=None, id=0):
    message = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        message["params"] = params
    return json.dumps(message, ensure_ascii=False).encode() + b"\n"


def tool(name, arguments, id=0):
    return mcp_line("tools/call", {"name": "nova_" + name, "arguments": arguments}, id)


def mcp_file_session(path, text, run):
    files = [{"path": path, "text": text}]
    lines = [mcp_line("initialize", {"protocolVersion": "2025-06-18"}, 1),
             mcp_line("notifications/initialized"),
             tool("check", {"files": files}, 2), tool("fix", {"files": files}, 3),
             tool("format", {"text": text, "path": path}, 4),
             tool("emit_c", {"files": files, "explain": ["overflow-checks", "allocations", "bounds-checks"]}, 5)]
    if run:
        lines.append(tool("run", {"files": files, "args": ["a", "b c"], "stdin": "line one\nline two\n"}, 6))
        lines.append(tool("run", {"files": files, "maxOutputBytes": 7, "maxSteps": 2000}, 7))
    for k, match in enumerate(re.finditer(r"\w+", text)):
        line, character = utf16_position(text, match.start())
        lines.append(tool("symbol", {"files": files, "path": path, "line": line + 1, "column": character + 1}, 100 + k))
    return b"".join(lines)


def mcp_protocol_sessions(root):
    """Hand-written MCP sessions: (name, input bytes)."""
    sessions = []
    lines = [b"\xef\xbb\xbf" + mcp_line("initialize", {"protocolVersion": "2024-11-05"}, 1), b"   \r\n",
             mcp_line("tools/list", None, 2), mcp_line("resources/list", {}, 3), mcp_line("prompts/list", {}, 4),
             mcp_line("ping", None, "p"), mcp_line("nothing/here", None, 5), mcp_line("notifications/x"),
             mcp_line("nothing/notified")[:-1].replace(b'"id": 0, ', b"") + b"\r",
             b"{nope\n", b"[1]\n", b"null\n", b'{"id": 7}\n', b'{"id": null, "params": 1}\n',
             b'{"id": 8, "result": 1}\n', b'{"id": 9, "method": 5}\n', b'{"id": null, "method": "ping"}\n',
             b'{"jsonrpc":"2.0","id":{"x":[1,2.50,-0]},"method":"ping"}\n',
             tool("check", {"files": [{"path": "a.nova", "text": "fn main() { let s = \"\u00e9\U0001d54f\\\u0001<>&'+`\"; }"}]}, 10),
             mcp_line("initialize", {"protocolVersion": "2025-03-26"}, 11), mcp_line("tools/list", None, 12),
             tool("check", {"files": [{"path": "a.nova", "text": "fn main() {}"}]}, 13),
             mcp_line("initialize", {"protocolVersion": "1999-01-01"}, 14), mcp_line("tools/list", None, 15),
             mcp_line("initialize", None, 16)]
    sessions.append(("protocol", b"".join(lines)))
    reads = [mcp_line("initialize", {}, 1)]
    for k, document in enumerate(sorted(documents(root))):
        reads.append(mcp_line("resources/read", {"uri": "nova://docs/" + document}, 10 + k))
    reads += [mcp_line("resources/read", {"uri": "nova://docs/nothing.md"}, 2),
              mcp_line("resources/read", {"uri": "file:///etc/passwd"}, 3), mcp_line("resources/read", {}, 4)]
    sessions.append(("resources", b"".join(reads)))
    prompts = [mcp_line("initialize", {}, 1),
               mcp_line("prompts/get", {"name": "write-nova", "arguments": {"task": "a stack \u00e9"}}, 2),
               mcp_line("prompts/get", {"name": "port-c-to-nova", "arguments": {"file": "lz4.c"}}, 3),
               mcp_line("prompts/get", {"name": "port-c-to-nova", "arguments": {"file": "lz4.c", "api": "lz4.h"}}, 4),
               mcp_line("prompts/get", {"name": "write-nova"}, 5),
               mcp_line("prompts/get", {"name": "write-nova", "arguments": {"task": ""}}, 6),
               mcp_line("prompts/get", {"name": "write-nova", "arguments": {"task": 5}}, 7),
               mcp_line("prompts/get", {"name": "port-c-to-nova", "arguments": {"file": "x", "api": [1]}}, 8),
               mcp_line("prompts/get", {"name": "other"}, 9), mcp_line("prompts/get", {}, 10)]
    sessions.append(("prompts", b"".join(prompts)))
    codes = sorted(set(re.findall(rb"\bN\d{4}\b", open(os.path.join(root, "docs", "diagnostics.md"), "rb").read())))
    explains = [mcp_line("initialize", {}, 1)]
    for k, code in enumerate(codes):
        explains.append(tool("explain", {"code": code.decode()}, 10 + k))
    explains += [tool("explain", {"code": " n0249 "}, 2), tool("explain", {"code": "N9999"}, 3), tool("explain", {}, 4)]
    sessions.append(("explain", b"".join(explains)))
    queries = ["borrow", "region parameter", "N0249", "  ", "move semantics drop", "static Mutex", "\u00a7", "zzzz",
               "the", "Fixed-buffer allocator", "UTF-16", "closure", "unsafe pointer arithmetic"]
    searches = [mcp_line("initialize", {}, 1)]
    for k, query in enumerate(queries):
        searches.append(tool("spec_search", {"query": query}, 10 + k))
    searches += [tool("spec_search", {"query": "borrow", "limit": 100}, 2),
                 tool("spec_search", {"query": "borrow", "limit": 0}, 3),
                 tool("spec_search", {"query": "borrow", "limit": 2.0}, 4),
                 tool("spec_search", {"query": "borrow", "limit": 1e1}, 5),
                 tool("spec_search", {"query": "borrow", "limit": -1}, 6),
                 tool("spec_search", {"query": "borrow", "limit": 1.5}, 7),
                 tool("spec_search", {"query": "borrow", "limit": "3"}, 8)]
    for k, number in enumerate((b"1e-400", b"-0.0", b"-0", b"1E2", b"9223372036854775808", b"1e19", b"9007199254740993.5")):
        searches.append(b'{"jsonrpc":"2.0","id":%d,"method":"tools/call","params":{"name":"nova_spec_search",'
                        b'"arguments":{"query":"borrow","limit":%s}}}\n' % (30 + k, number))
    sections = [("type-system", "31.2"), ("type-system", "\u00a731.2"), ("type-system", None), ("grammar", " "),
                ("diagnostics", "N0249"), ("tooling", "6.3"), ("unsafe", "pointers"), ("type-system.md", "2"),
                ("site/guide/basics.md", "Variables"), ("nothing", None), ("type-system", "99.99"),
                ("docs/type-system.md", "Generics"), ("tooling", "MCP")]
    for k, (document, section) in enumerate(sections):
        arguments = {"document": document}
        if section is not None:
            arguments["section"] = section
        searches.append(tool("spec_section", arguments, 50 + k))
    sessions.append(("spec", b"".join(searches)))
    program = [{"path": "a.nova", "text": "fn main() {}"}]
    bad = [mcp_line("initialize", {"protocolVersion": 5}, 1), mcp_line("initialize", {"protocolVersion": {}}, 2),
           tool("check", {"files": program, "profile": 5}, 3), tool("check", {"files": program, "noFloat": "x"}, 4),
           tool("check", {"paths": [5]}, 5), tool("check", {"paths": [None]}, 6),
           tool("check", {"paths": ["missing.nova"]}, 7), tool("check", {"paths": ["adir"]}, 8),
           tool("check", {"paths": ["nodir/x.nova"]}, 9), tool("run", {"files": program, "stdin": 5}, 10),
           tool("check", {"files": program, "noFloat": [1]}, 11), tool("check", {"files": program, "profile": True}, 12),
           tool("check", {"files": program, "noFloat": None, "profile": None}, 13),
           tool("check", {"paths": ["/etc/passwd/x"]}, 14), tool("check", {"paths": ["adir/../missing2.nova"]}, 15),
           tool("emit_c", {"files": program, "explain": [1]}, 16), tool("emit_c", {"files": program, "explain": [None]}, 17),
           tool("check", {}, 18), tool("check", {"files": [1, {"path": "a.nova"}]}, 19),
           tool("check", {"files": program * 2}, 20), tool("check", {"files": program, "profile": "kernel"}, 21),
           tool("check", {"files": program, "profile": "freestanding", "noFloat": True}, 22),
           tool("check", {"paths": ["good.nova", "adir/b.nova"]}, 23), tool("check", {"paths": ["bom.nova"]}, 24),
           tool("symbol", {"files": program, "path": "b.nova", "line": 1, "column": 1}, 25),
           tool("symbol", {"files": [{"path": "a.nova", "text": "fn main( {"}], "path": "a.nova", "line": 1, "column": 1}, 26),
           tool("symbol", {"files": program, "path": "a.nova", "line": 0, "column": 0}, 27),
           tool("symbol", {"files": program, "path": "a.nova", "line": 9, "column": 99}, 28),
           tool("symbol", {"files": program, "path": "a.nova", "line": "1", "column": 1}, 29),
           tool("format", {"text": "fn main( {"}, 30), tool("format", {"text": 5}, 31), tool("format", {"path": 5}, 32),
           tool("run", {"files": program, "maxSteps": -1}, 33), tool("run", {"files": [{"path": "a.nova", "text": "fn f() {}"}]}, 34),
           tool("run", {"files": [{"path": "a.nova", "text": "fn main() { let v = [1]; var i: usize = 3; Console.writeLine(v[i]); }"}]}, 35),
           tool("run", {"files": [{"path": "a.nova", "text": "fn main() { while (true) {} }"}], "maxSteps": 500}, 36),
           tool("run", {"files": [{"path": "a.nova", "text": "fn main() -> i32 { match (File.open(\"/etc/passwd\")) { Ok(f) => { return 1; } Err(e) => { Console.writeLine(e.message()); return 2; } } }"}]}, 37),
           tool("run", {"files": [{"path": "a.nova", "text": "fn main() { Console.write(\"\u00e9\u00e9\u00e9\u00e9\"); }"}], "maxOutputBytes": 3}, 38),
           tool("emit_c", {"files": [{"path": "a.nova", "text": "fn main( {"}]}, 39),
           tool("nothing", {}, 40), mcp_line("tools/call", {"arguments": {}}, 41), mcp_line("tools/call", {"name": "nova_check", "arguments": 5}, 42)]
    sessions.append(("arguments", b"".join(bad)))
    return sessions


def documents(root):
    found = [os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/")
             for top in ("docs", os.path.join("site", "guide"))
             for d, _, names in os.walk(os.path.join(root, top)) for n in names if n.endswith(".md")]
    return found


def mcp_normalise(output, mapping=lambda line: line):
    """The version in serverInfo and in the generated C's banner made VERSION."""
    output = re.sub(rb'("name":"novac","title":"Nova","version":")[^"]*"', rb'\g<1>VERSION"', mapping(output))
    return re.sub(rb"Generated by novac [^ ]+\. Do not edit", b"Generated by novac VERSION. Do not edit", output)


def to_cee(data):
    """A session for ceesafec: the tool and resource names it serves."""
    return re.sub(rb'"name": ?"nova_', lambda m: m.group(0).replace(b"nova_", b"ceesafe_"), data).replace(
        b"nova://", b"ceesafe://")


def compare_mcp(cee, novac, name, cee_data, data, cwd):
    mine = serve(cee, ["mcp"], cee_data, cwd)
    ref = serve(novac, ["mcp"], data, cwd)
    mapped = (mine[0], mcp_normalise(mine[1], map_back), map_back(mine[2]))
    ref = (ref[0], mcp_normalise(ref[1]), ref[2])
    return None if mapped == ref else (name, mapped, ref)


def normalise(output, mapping=lambda body: body):
    """Each message mapped and its serverInfo version made VERSION, then framed again for its new length."""
    messages, rest = [], output
    while rest.startswith(b"Content-Length: "):
        header, _, rest = rest.partition(b"\r\n\r\n")
        length = int(header[len(b"Content-Length: "):])
        body, rest = rest[:length], rest[length:]
        messages.append(frame(re.sub(rb'("name":"novac","version":")[^"]*"', rb'\g<1>VERSION"', mapping(body))))
    return b"".join(messages) + mapping(rest)


def compare_lsp(cee, novac, name, data, cee_data, cwd_cee, cwd_novac, paths=(b"", b"")):
    mine = serve(cee, ["lsp"], cee_data, cwd_cee)
    ref = serve(novac, ["lsp"], data, cwd_novac)
    mapping = (lambda body: map_back(body).replace(*paths)) if paths[0] else map_back
    mapped = (mine[0], normalise(mine[1], mapping), mapping(mine[2]))
    ref = (ref[0], normalise(ref[1]), ref[2])
    return None if mapped == ref else (name, mapped, ref)


def package_session(scratch):
    """A document in a package, its sibling unsaved: the same tree under both names (same-length directories)."""
    sessions = []
    for flavour, manifest, ext in (("n", "nova.toml", ".nova"), ("c", "ceesafe.toml", ".cee")):
        root = os.path.join(scratch, flavour, "pkg")
        os.makedirs(os.path.join(root, "src"), exist_ok=True)
        with open(os.path.join(root, manifest), "w") as f:
            f.write('[package]\nname = "demo"\nversion = "0.1.0"\n')
        with open(os.path.join(root, "src", "helper" + ext), "w") as f:
            f.write("fn helper() -> i32 => 41;\n")
        text = "fn main() -> i32 {\n    let x: bool = helper();\n    return helper() + 1;\n}\n"
        with open(os.path.join(root, "src", "main" + ext), "w") as f:
            f.write(text)
        uri = "file://" + os.path.join(root, "src", "main" + ext)
        sessions.append(lsp_session(uri, text))
    return sessions


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--only", choices=("lsp", "mcp"))
    parser.add_argument("--show", type=int, default=5)
    parser.add_argument("--dense", action="store_true", help="hover and definition at every character")
    parser.add_argument("files", nargs="*")
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    root = os.path.abspath(options.root)
    files = options.files
    if not files:
        for family in FAMILIES:
            directory = os.path.join(root, "tests", "corpus", family)
            files += sorted(f"tests/corpus/{family}/{n}" for n in os.listdir(directory) if n.endswith(".nova"))
    cases, results, mcp_results = [], [], []
    scratch = tempfile.mkdtemp(prefix="servers-")
    try:
        if options.only != "mcp":
            for f in files:
                with open(os.path.join(root, f), encoding="utf-8", errors="surrogateescape") as handle:
                    text = handle.read()
                try:
                    data = lsp_session("file://" + os.path.join(root, f), text, options.dense)
                except UnicodeEncodeError:
                    continue
                cases.append((f, data, data, root, root))
            for name, data in edge_sessions():
                cases.append((name, data, data, scratch, scratch))
            nova_package, cee_package = package_session(scratch)
            cases.append(("package", nova_package, cee_package, scratch, scratch, (b"/c/pkg/", b"/n/pkg/")))
        with ThreadPoolExecutor(options.jobs) as pool:
            results = list(pool.map(lambda c: compare_lsp(cee, novac, *c), cases))
        mcp_cases = []
        if options.only != "lsp":
            # The names in the session are Nova's: ceesafec's server reads ceesafe_ tools and ceesafe:// resources.
            work = os.path.join(scratch, "mcp")
            os.makedirs(os.path.join(work, "adir"))
            for name, text in (("good.nova", "fn main() {}\n"), ("adir/b.nova", "fn g() -> i32 => x;\n"),
                               ("bom.nova", "\ufefffn main() { let x: i32 = true; }\n")):
                with open(os.path.join(work, name), "w", encoding="utf-8") as handle:
                    handle.write(text)
            for f in files:
                with open(os.path.join(root, f), encoding="utf-8", errors="surrogateescape") as handle:
                    text = handle.read()
                try:
                    data = mcp_file_session(f, text, "/run-" in f)
                except UnicodeEncodeError:
                    continue
                mcp_cases.append((f, data))
            mcp_cases += mcp_protocol_sessions(root)
            with ThreadPoolExecutor(options.jobs) as pool:
                mcp_results = list(pool.map(lambda c: compare_mcp(cee, novac, c[0], to_cee(c[1]), c[1], work), mcp_cases))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    differ = [r for r in results if r]
    for name, mine, ref in differ[:options.show]:
        print(f"differ: lsp {name}: status {mine[0]} vs {ref[0]}")
        a, b = mine[1], ref[1]
        k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
        print(f"    ceesafec ...{a[max(0, k - 200):k + 200]!r}")
        print(f"    novac    ...{b[max(0, k - 200):k + 200]!r}")
        if mine[2] != ref[2]:
            print(f"    stderr: {mine[2][-300:]!r} vs {ref[2][-300:]!r}")
    if results:
        print(f"lsp: {len(results) - len(differ)}/{len(results)} sessions identical")
    mcp_differ = [r for r in mcp_results if r]
    for name, mine, ref in mcp_differ[:options.show]:
        print(f"differ: mcp {name}: status {mine[0]} vs {ref[0]}")
        a, b = mine[1].split(b"\n"), ref[1].split(b"\n")
        k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
        x, y = (a[k] if k < len(a) else b""), (b[k] if k < len(b) else b"")
        j = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), min(len(x), len(y)))
        print(f"    line {k}: ceesafec ...{x[max(0, j - 150):j + 150]!r}")
        print(f"    line {k}: novac    ...{y[max(0, j - 150):j + 150]!r}")
        if mine[2] != ref[2]:
            print(f"    stderr: {mine[2][-300:]!r} vs {ref[2][-300:]!r}")
    if mcp_results:
        print(f"mcp: {len(mcp_results) - len(mcp_differ)}/{len(mcp_results)} sessions identical")
    return 1 if differ or mcp_differ else 0


if __name__ == "__main__":
    sys.exit(main())
