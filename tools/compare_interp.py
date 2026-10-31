#!/usr/bin/env python3
"""Compares `ceesafec run --interp` with the pinned novac's interpreter (docs/p8-plan.md S4).

Over the corpus's run-pass and run-fail programs (never benchmarks: novac's interpreter needs tens of GB on them), both
run each program and must give the same exit status, stdout and stderr. Each program also runs with
NOVA_ALLOC_REPORT=1, and with --no-placement --no-bce --no-oce --no-closure-specialisation. Programs read their
standard input from /dev/null.

ceesafec is a Nova program too: with NOVA_ALLOC_REPORT its own runtime adds its report line after the interpreted
program's, which is dropped before comparing (docs/p8-plan.md, known differences).

usage: python3 tools/compare_interp.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root NOVA_CHECKOUT
       [--jobs N] [--list FILE] [--only report|off] [files...]
"""
import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from names import dialect, for_compiler, map_back

OFF = ["--no-placement", "--no-bce", "--no-oce", "--no-closure-specialisation"]


def run(compiler, arguments, cwd, env, own_report=False):
    d = dialect(compiler)
    cwd, arguments = for_compiler(compiler, cwd, arguments)
    if "NOVA_ALLOC_REPORT" in env and d.cee:
        env = {**{k: v for k, v in env.items() if k != "NOVA_ALLOC_REPORT"}, d.alloc_report: env["NOVA_ALLOC_REPORT"]}
    alloc = d.alloc.encode()
    try:
        p = subprocess.run([compiler] + arguments, cwd=cwd, capture_output=True, env=env, stdin=subprocess.DEVNULL,
                           timeout=300)
        stderr = p.stderr
        if own_report and stderr.startswith(alloc) or own_report and b"\n" + alloc in stderr:
            stderr = stderr[:stderr.rstrip(b"\n").rfind(b"\n") + 1] if b"\n" in stderr.rstrip(b"\n") else b""
        return p.returncode, p.stdout, stderr
    except subprocess.TimeoutExpired:
        return "timeout", b"", b""


def compare(cee, novac, path, root, only):
    problems = []
    plain = dict(os.environ)
    report = {**plain, "NOVA_ALLOC_REPORT": "1"}
    runs = [("plain", ["run", "--interp", path], plain), ("report", ["run", "--interp", path], report),
            ("off", ["run", "--interp"] + OFF + [path], plain)]
    for name, arguments, env in runs:
        if only and name not in ("plain", only):
            continue
        mine, ref = run(cee, arguments, root, env, own_report=name == "report"), run(novac, arguments, root, env)
        if mine != ref and (mine[0], map_back(mine[1]), map_back(mine[2])) != ref:
            problems.append((name, mine, ref))
            break
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--list", help="write the differing files to FILE")
    parser.add_argument("--only", choices=("report", "off"))
    parser.add_argument("--show", type=int, default=10)
    parser.add_argument("files", nargs="*")
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    root = os.path.abspath(options.root)
    files = options.files
    if not files:
        for family in ("run-pass", "run-fail"):
            directory = os.path.join(root, "tests", "corpus", family)
            files += sorted(f"tests/corpus/{family}/{n}" for n in os.listdir(directory) if n.endswith(".nova"))
    with ThreadPoolExecutor(options.jobs) as pool:
        results = list(pool.map(lambda f: compare(cee, novac, f, root, options.only), files))
    differ = [(f, r) for f, r in zip(files, results) if r]
    for f, r in differ[:options.show]:
        name, mine, ref = r[0]
        print(f"differ: {f} ({name}): status {mine[0]} vs {ref[0]}")
        for label, a, b in (("stdout", mine[1], ref[1]), ("stderr", mine[2], ref[2])):
            if a != b:
                print(f"    {label}: ceesafec {a[-300:]!r}")
                print(f"    {label}: novac    {b[-300:]!r}")
    if options.list:
        with open(options.list, "w") as fh:
            fh.write("".join(f + "\n" for f, _ in differ))
    print(f"compare_interp: {len(files)} programs, {len(files) - len(differ)} identical, {len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
