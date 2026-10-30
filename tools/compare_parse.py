#!/usr/bin/env python3
"""Compares `ceesafec parse` (or `check`) with the pinned novac file by file (docs/p2-frontend.md §6).

For each file it runs `parse --dump-ast --diagnostics-format=json FILE` and `parse FILE` (text diagnostics on stderr)
with both compilers, from the same working directory, and requires the same exit status, stdout and stderr. With
`--command check` it runs `check --dump-hir --diagnostics-format=json FILE` and `check FILE` instead (P3), with the file's
`// option:` and `// profile:` lines as options, as tools/run_corpus.py passes them.

usage: tools/compare_parse.py --ceesafec out/ceesafe --novac ~/.nova/0.5.0/bin/novac [--command check] [--root DIR]
       PATH...
"""

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor


def files_of(root, paths):
    result = []
    for p in paths:
        full = os.path.join(root, p)
        if os.path.isdir(full):
            for d, dirs, names in os.walk(full):
                dirs.sort()
                result += [os.path.relpath(os.path.join(d, n), root) for n in sorted(names) if n.endswith(".nova")]
        else:
            result.append(p)
    return result


def outcome(compiler, argv, root):
    try:
        p = subprocess.run([compiler] + argv, cwd=root, capture_output=True, timeout=120)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "timeout", b"", b""


def options_of(root, path):
    """The corpus's per-file options for `check` (run_corpus.compile_options, CorpusTests.ProfileOf and the like)."""
    with open(os.path.join(root, path), encoding="utf-8", errors="replace") as f:
        stripped = {line.strip() for line in f.read().replace("\r\n", "\n").split("\n")}
    options = []
    if "// profile: freestanding" in stripped:
        options += ["--profile", "freestanding"]
    if "// option: no-float" in stripped:
        options.append("--no-float")
    if "// option: kernel cosmoos" in stripped:
        options += ["--kernel", "cosmoos"]
    return options


def compare(args, root, path):
    problems = []
    dump = "--dump-ast" if args.command == "parse" else "--dump-hir"
    extra = options_of(root, path) if args.command == "check" else []
    for argv in ([args.command, dump, "--diagnostics-format=json"] + extra + [path], [args.command] + extra + [path]):
        mine = outcome(args.ceesafec, argv, root)
        ref = outcome(args.novac, argv, root)
        if mine != ref:
            what = [n for n, a, b in zip(("status", "stdout", "stderr"), mine, ref) if a != b]
            detail = ""
            for n, a, b in zip(("stdout", "stderr"), mine[1:], ref[1:]):
                if a != b:
                    al, bl = a.split(b"\n"), b.split(b"\n")
                    k = next((i for i in range(max(len(al), len(bl)))
                              if (al[i] if i < len(al) else None) != (bl[i] if i < len(bl) else None)), 0)
                    detail = (f" first {n} difference at line {k + 1}:\n    novac:    "
                              f"{(bl[k] if k < len(bl) else b'<end>').decode(errors='replace')[:300]}\n    ceesafec: "
                              f"{(al[k] if k < len(al) else b'<end>').decode(errors='replace')[:300]}")
                    break
            problems.append(f"{path}: {' '.join(argv[:-1])}: {', '.join(what)} differ"
                            f" (status {mine[0]} vs {ref[0]}){detail}")
            break
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--command", choices=("parse", "check"), default="parse")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    args.ceesafec = os.path.abspath(os.path.expanduser(args.ceesafec))
    args.novac = os.path.abspath(os.path.expanduser(args.novac))
    files = files_of(args.root, args.paths)
    with ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda f: compare(args, args.root, f), files))
    problems = [p for r in results for p in r]
    for p in problems[:15]:
        print(p)
    print(f"compare_parse ({args.command}): {len(files)} files, {len(files) - len(problems)} identical, {len(problems)} differ")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
