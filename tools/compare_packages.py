#!/usr/bin/env python3
"""Compares `ceesafec check` with the pinned novac in package mode (docs/p3-plan.md S8b).

Each directory under tests/packages is one fixture: its root package is `app/` if there is one, else the directory
itself. Both compilers run `check` there (HIR dump with JSON diagnostics, then text diagnostics), and their outputs
must be byte-identical.

With --renamed all (or root), each fixture is first copied and renamed to CeeSafe's names (Decision 0002): every
package's (or only the root package's) `nova.toml`, `nova.lock` and `*.nova` become `ceesafe.toml`, `ceesafe.lock` and
`*.cee`. ceesafec's output on the copy, with those names mapped back, must equal novac's on the original.

usage: python3 tools/compare_packages.py --ceesafec out/ceesafe --novac ~/.nova/0.6.0/bin/novac
           [--renamed all|root] [fixtures...]
"""
import argparse
import os
import shutil
import tempfile
import subprocess
import sys


def run(compiler, directory, arguments):
    result = subprocess.run([compiler, "check"] + arguments, cwd=directory, capture_output=True)
    return result.returncode, result.stdout + result.stderr


MAP_BACK = ((b"ceesafec fetch", b"novac fetch"), (b"ceesafe.toml", b"nova.toml"), (b"ceesafe.lock", b"nova.lock"),
            (b".cee", b".nova"))


def renamed_copy(fixture, work, scope):
    """The fixture copied under `work`, its packages (all, or the root `app/`) renamed to CeeSafe's names."""
    copy = os.path.join(work, os.path.basename(fixture))
    shutil.copytree(fixture, copy)
    root = os.path.join(copy, "app") if os.path.isdir(os.path.join(copy, "app")) else copy
    for base, _, names in os.walk(copy):
        if scope == "root" and not (base == root or base.startswith(root + os.sep)):
            continue
        for name in names:
            stem, extension = os.path.splitext(name)
            if name in ("nova.toml", "nova.lock"):
                os.rename(os.path.join(base, name), os.path.join(base, "ceesafe" + extension))
            elif extension == ".nova":
                os.rename(os.path.join(base, name), os.path.join(base, stem + ".cee"))
    return copy


def mapped_back(outcome):
    status, output = outcome
    for new, old in MAP_BACK:
        output = output.replace(new, old)
    return status, output


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--renamed", choices=("all", "root"))
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
        with tempfile.TemporaryDirectory() as work:
            ours = directory
            if options.renamed:
                copy = renamed_copy(fixture, work, options.renamed)
                ours = os.path.join(copy, "app") if os.path.isdir(os.path.join(copy, "app")) else copy
            for arguments in (["--dump-hir", "--diagnostics-format=json"], []):
                expected = run(novac, directory, arguments)
                actual = run(ceesafec, ours, arguments)
                if (mapped_back(actual) if options.renamed else actual) != expected:
                    differ.append(name)
                    break
    for name in differ:
        print("differ:", name)
    print(f"compare_packages: {len(fixtures)} fixtures, {len(fixtures) - len(differ)} identical, {len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
