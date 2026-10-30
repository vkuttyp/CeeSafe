#!/usr/bin/env python3
"""Compares `ceesafec build --dump-nir` with the pinned novac's NIR (docs/p4-plan.md).

novac prints the NIR after drop elaboration with `build --emit c -o DIR --dump-nir`; closure-call specialisation,
placement and check elimination are turned off, since they are P7's. Only the files novac builds are compared; the
corpus's `// profile:` and `// option:` lines are passed as in compare_parse.py.

usage: python3 tools/compare_nir.py --ceesafec out/ceesafe --novac ~/.nova/0.6.0/bin/novac --root <Nova>
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

OFF = ["--no-closure-specialisation", "--no-placement", "--no-bce", "--no-oce"]


def files(root, paths):
    for path in paths:
        full = os.path.join(root, path)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                if name.endswith(".nova"):
                    yield os.path.join(path, name)
        else:
            yield path


def compare(arguments):
    root, ceesafec, novac, path = arguments
    options = options_of(root, path)
    with tempfile.TemporaryDirectory() as out:
        reference = subprocess.run([novac, "build", "--emit", "c", "-o", out, "--dump-nir"] + OFF + options + [path],
                                   cwd=root, capture_output=True)
    if reference.returncode != 0:
        return path, None  # novac does not build it: nothing to compare
    with tempfile.TemporaryDirectory() as out:
        ours = subprocess.run([ceesafec, "build", "--emit", "c", "-o", out, "--dump-nir"] + OFF + options + [path],
                              cwd=root, capture_output=True)
    return path, ours.returncode == 0 and ours.stdout == reference.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--list", help="write every differing file's path to FILE, sorted, one per line")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    ceesafec = os.path.abspath(args.ceesafec)
    novac = os.path.expanduser(args.novac)
    work = [(args.root, ceesafec, novac, path) for path in files(args.root, args.paths)]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(compare, work))
    built = [(p, same) for p, same in results if same is not None]
    differ = sorted(p for p, same in built if not same)
    if args.list:
        with open(args.list, "w", encoding="utf-8") as f:
            f.write("".join(p + "\n" for p in differ))
    print(f"compare_nir: {len(results)} files, {len(built)} built by novac, {len(built) - len(differ)} identical, "
          f"{len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
