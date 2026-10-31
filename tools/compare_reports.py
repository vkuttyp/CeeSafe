#!/usr/bin/env python3
"""Compares one of novac's optimisation reports with ceesafec's, over every program novac builds (docs/p7-plan.md).

The reports are `build --explain-closure-calls`, `--explain-allocations`, `--explain-bounds-checks` and
`--explain-overflow-checks`; both compilers run `build --emit c -o DIR` with the report's switch and the corpus's
`// profile:` and `// option:` lines, and their standard output must be byte-identical.

usage: python3 tools/compare_reports.py --ceesafec out/ceesafec --novac NOVAC --root <Nova> --report NAME
           [--list FILE] paths...
"""
import argparse
import concurrent.futures
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_parse import options_of  # noqa: E402
from compare_nir import files  # noqa: E402
from names import compared_files, for_compiler, map_back  # noqa: E402

REPORTS = {"closure-calls": "--explain-closure-calls", "allocations": "--explain-allocations",
           "bounds-checks": "--explain-bounds-checks", "overflow-checks": "--explain-overflow-checks"}


def compare(arguments):
    root, ceesafec, novac, path, switch = arguments
    options = options_of(root, path)
    with tempfile.TemporaryDirectory() as out:
        reference = subprocess.run([novac, "build", "--emit", "c", "-o", out, switch] + options + [path], cwd=root,
                                   capture_output=True)
        if reference.returncode != 0:
            return path, None, b""
        cwd, argv = for_compiler(ceesafec, root, ["build", "--emit", "c", "-o", out, switch] + options + [path])
        ours = subprocess.run([ceesafec] + argv, cwd=cwd, capture_output=True)
    return path, ours.returncode == 0 and map_back(ours.stdout) == reference.stdout, reference.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--report", required=True, choices=sorted(REPORTS))
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--list")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    ceesafec = os.path.abspath(args.ceesafec)
    novac = os.path.expanduser(args.novac)
    work = [(args.root, ceesafec, novac, p, REPORTS[args.report])
            for p in compared_files(args.root, files(args.root, args.paths))]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(compare, work))
    built = [(p, same, text) for p, same, text in results if same is not None]
    differ = sorted(p for p, same, _ in built if not same)
    nonempty = sum(1 for _, _, text in built if text.strip())
    if args.list:
        with open(args.list, "w", encoding="utf-8") as f:
            f.write("".join(p + "\n" for p in differ))
    print(f"compare_reports ({args.report}): {len(built)} built by novac, {nonempty} with a non-empty report, "
          f"{len(built) - len(differ)} identical, {len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
