#!/usr/bin/env python3
"""Compares `ceesafec check` with the pinned novac in package mode (docs/p3-plan.md S8b).

Each directory under tests/packages is one fixture: its root package is `app/` if there is one, else the directory
itself. Both compilers run `check` there (HIR dump with JSON diagnostics, then text diagnostics), and their outputs
must be byte-identical.

The fixtures are Nova packages, which novac reads as they are. ceesafec reads only CeeSafe packages (Decision 0003),
so each fixture is first copied with every `nova.toml`, `nova.lock` and `*.nova` renamed to `ceesafe.toml`,
`ceesafe.lock` and `*.cee`; ceesafec's output on the copy, with those names mapped back, must equal novac's on the
original.

With --windows (both compilers on Windows), two things novac does there are folded before comparing (docs/p8-plan.md,
known differences): its Console.WriteLine ends lines with CR LF, and with output redirected it writes in the console's
code page (437: `§` as 0x15, `…` and dashes best-fitted), where ceesafec writes UTF-8 with LF.

usage: python3 tools/compare_packages.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac [--windows] [fixtures...]
"""
import argparse
import os
import shutil
import tempfile
import subprocess
import sys

from names import map_back


def run(compiler, directory, arguments):
    result = subprocess.run([compiler, "check"] + arguments, cwd=directory, capture_output=True)
    return result.returncode, result.stdout + result.stderr




def renamed_copy(fixture, work):
    """The fixture copied under `work`, its packages renamed to CeeSafe's names."""
    copy = os.path.join(work, os.path.basename(fixture))
    shutil.copytree(fixture, copy)
    for base, _, names in os.walk(copy):
        for name in names:
            stem, extension = os.path.splitext(name)
            if name in ("nova.toml", "nova.lock"):
                os.rename(os.path.join(base, name), os.path.join(base, "ceesafe" + extension))
            elif extension == ".nova":
                os.rename(os.path.join(base, name), os.path.join(base, stem + ".cee"))
    return copy


def mapped_back(outcome, windows=False):
    status, output = outcome
    output = map_back(output)
    if windows:
        text = output.decode("utf-8").replace("\u00a7", "\x15").replace("\u2026", ".").replace("\u2013", "-")
        output = text.replace("\u2014", "-").encode("cp437", "replace")
    return status, output


def novac_output(outcome, windows=False):
    status, output = outcome
    return status, output.replace(b"\r\n", b"\n") if windows else output


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--windows", action="store_true", help="fold novac's CR LF and code page 437 (on Windows)")
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
            copy = renamed_copy(fixture, work)
            ours = os.path.join(copy, "app") if os.path.isdir(os.path.join(copy, "app")) else copy
            for arguments in (["--dump-hir", "--diagnostics-format=json"], []):
                expected = novac_output(run(novac, directory, arguments), options.windows)
                actual = run(ceesafec, ours, arguments)
                if mapped_back(actual, options.windows) != expected:
                    differ.append(name)
                    break
    for name in differ:
        print("differ:", name)
    print(f"compare_packages: {len(fixtures)} fixtures, {len(fixtures) - len(differ)} identical, {len(differ)} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main())
