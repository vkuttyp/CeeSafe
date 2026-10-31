#!/usr/bin/env python3
"""Compares `ceesafec fmt` with the pinned novac's (docs/p8-plan.md S1).

Over every .nova file of a Nova checkout (the corpus, lib/, programs/, benchmarks/, …) and CeeSafe's own sources, each
compiler runs `fmt --stdout FILE` and `fmt --diagnostics-format=json --stdout FILE`: the exit status, stdout and stderr
must be the same once ceesafec's are mapped back to Nova's names (tools/names.py). ceesafec's output is then formatted
again and must not change (idempotence, formatting.md §6). Last, `fmt --check` and `fmt` itself run on a scratch copy of
a sample of files, and must list and rewrite the same files the same way. To exercise the breaking of long lines
(§3.4), every corpus file without a comment inside a line is also compared squashed onto one line.

usage: python3 tools/compare_fmt.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root NOVA_CHECKOUT
       [--jobs N] [--list FILE]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from names import FORK_DIVERGENCES, cee_path, for_compiler, map_back

HERE = os.path.dirname(os.path.abspath(__file__))


def same(mine, ref):
    """Equal as printed, or once ceesafec's names are mapped back (not always: CeeSafe's own sources contain them)."""
    return mine == ref or (mine[0], map_back(mine[1]), map_back(mine[2])) == ref


def run(compiler, arguments, cwd):
    p = subprocess.run([compiler] + arguments, cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def compare(cee, novac, path, cwd):
    """Problems with one file, or an empty list."""
    problems = []
    for arguments in (["fmt", "--stdout", path], ["fmt", "--diagnostics-format=json", "--stdout", path]):
        mine, ref = run(cee, *reversed(for_compiler(cee, cwd, arguments))), run(novac, arguments, cwd)
        if not same(mine, ref):
            problems.append(f"{path}: {' '.join(arguments[:-1])}: differs (status {mine[0]} vs {ref[0]})")
            return problems
    status, formatted, _ = run(cee, *reversed(for_compiler(cee, cwd, ["fmt", "--stdout", path])))
    if status == 0:
        with tempfile.TemporaryDirectory() as work:
            again = os.path.join(work, os.path.basename(cee_path(path)))
            with open(again, "wb") as f:
                f.write(formatted)
            status, twice, _ = run(cee, ["fmt", "--stdout", again], work)
            if status != 0 or twice != formatted:
                problems.append(f"{path}: not idempotent")
    return problems


def squashed(text):
    """The file on one line without its whole-line comments, or None if it has a comment after code."""
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if "//" in line or "/*" in line:
            return None
        if stripped:
            out.append(stripped)
    return " ".join(out) + "\n"


def compare_squashed(cee, novac, path, root):
    with open(os.path.join(root, path), encoding="utf-8") as f:
        text = squashed(f.read())
    if text is None:
        return None
    with tempfile.TemporaryDirectory() as work:
        for name in ("squashed.cee", "squashed.nova"):
            with open(os.path.join(work, name), "w", encoding="utf-8") as f:
                f.write(text)
        mine, ref = run(cee, ["fmt", "--stdout", "squashed.cee"], work), run(novac, ["fmt", "--stdout", "squashed.nova"], work)
        return [] if same(mine, ref) else [f"{path} squashed: differs"]


def in_place(cee, novac, files, root):
    """`fmt --check` and `fmt` on copies of `files`: the same listing and the same rewritten files."""
    problems = []
    with tempfile.TemporaryDirectory() as work:
        trees = {}
        for who, name in (("c", cee_path), ("n", lambda f: f)):
            tree = os.path.join(work, who)
            for f in files:
                os.makedirs(os.path.dirname(os.path.join(tree, f)), exist_ok=True)
                shutil.copy(os.path.join(root, f), os.path.join(tree, name(f)))
            trees[who] = tree
        for arguments in (["fmt", "--check"], ["fmt"]):
            mine = run(cee, arguments + [cee_path(f) for f in files], trees["c"])
            ref = run(novac, arguments + files, trees["n"])
            if not same(mine, ref):
                problems.append(f"in place: {arguments[1] if len(arguments) > 1 else ''}: output differs")
        for f in files:
            with open(os.path.join(trees["c"], cee_path(f)), "rb") as a, open(os.path.join(trees["n"], f), "rb") as b:
                if a.read() != b.read():
                    problems.append(f"in place: {f}: rewritten differently")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True, help="a Nova checkout at the pinned tag")
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--list", help="write the differing files to FILE")
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    root = os.path.abspath(options.root)
    files = []
    for base, directories, names in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in (".git", "bin", "obj", "node_modules", "out"))
        files += sorted(os.path.relpath(os.path.join(base, n), root) for n in names if n.endswith(".nova"))
    files = [f for f in files if f.replace(os.sep, "/") not in FORK_DIVERGENCES]
    own_root = os.path.normpath(os.path.join(HERE, ".."))
    own = sorted(subprocess.run(["git", "-C", own_root, "ls-files", "*.cee"], capture_output=True, text=True,
                                check=True).stdout.split())
    jobs = [(f, root) for f in files] + [(f, own_root) for f in own]
    with ThreadPoolExecutor(options.jobs) as pool:
        results = list(pool.map(lambda job: compare(cee, novac, job[0], job[1]), jobs))
    problems = [p for r in results for p in r]
    differ = [job[0] for job, r in zip(jobs, results) if r]
    sample = [f for f in files if f.startswith("tests/corpus/run-pass/")][:40] + \
             [f for f in files if f.startswith("tests/corpus/parse-fail/")][:5]
    problems += in_place(cee, novac, sample, root)
    corpus = [f for f in files if f.startswith("tests/corpus/")]
    with ThreadPoolExecutor(options.jobs) as pool:
        squash = [r for r in pool.map(lambda f: compare_squashed(cee, novac, f, root), corpus) if r is not None]
    problems += [p for r in squash for p in r]
    for p in problems[:50]:
        print("differ:", p)
    if options.list:
        with open(options.list, "w") as f:
            f.write("".join(d + "\n" for d in sorted(differ)))
    print(f"compare_fmt: {len(files)} Nova files and {len(own)} CeeSafe files, {len(jobs) - len(differ)} identical, "
          f"{len(differ)} differ; in place over {len(sample)} files: "
          f"{'identical' if not any(p.startswith('in place') for p in problems) else 'differs'}; "
          f"{len(squash)} squashed, {sum(1 for r in squash if r)} differ")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
