#!/usr/bin/env python3
"""Compares `ceesafec check` with the pinned novac in package mode (docs/p3-plan.md S8b).

Each directory under tests/packages is one fixture: its root package is `app/` if there is one, else the directory
itself. Both compilers run `check` there (HIR dump with JSON diagnostics, then text diagnostics), and their outputs
must be byte-identical.

usage: python3 tools/compare_packages.py --ceesafec out/ceesafe --novac ~/.nova/0.6.0/bin/novac [fixtures...]
"""
import argparse
import os
import subprocess
import sys


def run(compiler, directory, arguments):
    result = subprocess.run([compiler, "check"] + arguments, cwd=directory, capture_output=True)
    return result.returncode, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("fixtures", nargs="*")
    options = parser.parse_args()
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "packages")
    fixtures = options.fixtures or sorted(os.listdir(root))
    ceesafec = os.path.abspath(options.ceesafec)
    novac = os.path.expanduser(options.novac)
    differ = []
    for name in fixtures:
        fixture = os.path.join(root, name)
        directory = os.path.join(fixture, "app") if os.path.isdir(os.path.join(fixture, "app")) else fixture
        for arguments in (["--dump-hir", "--diagnostics-format=json"], []):
            if run(novac, directory, arguments) != run(ceesafec, directory, arguments):
                differ.append(name)
                break
    for name in differ:
        print("differ:", name)
    print(f"compare_packages: {len(fixtures)} fixtures, {len(fixtures) - len(differ)} identical, {len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
