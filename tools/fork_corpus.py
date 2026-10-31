#!/usr/bin/env python3
"""Writes tests/reference/: CeeSafe's own corpus at the fork point (docs/fork-point.md), from Nova's at the pinned tag.

It mirrors the Nova checkout's layout, so the comparison tools run novac in the checkout and ceesafec in
tests/reference/ on the same relative paths:

- every `.nova` file of the checkout becomes a `.cee` file with the same text (programs print and diagnose their own
  text, which must stay byte for byte), except the FORK_DIVERGENCES, whose reserved C names are CeeSafe's;
- the companion files under tests/corpus/ are copied: the C compiled with the programs (ffi's harnesses and
  `.types.h` headers, freestanding's environments) with CeeSafe's names, since they meet ceesafec's C; the snapshots
  (AST, HIR, emitted C and headers, reports) as they are, Nova's, which tools/run_corpus.py compares with ceesafec's
  output mapped back (tools/names.py), as every comparison with the frozen baseline does.

usage: python3 tools/fork_corpus.py --nova NOVA_CHECKOUT_AT_v0.6.0
"""
import argparse
import os
import shutil
import subprocess
import sys

from names import FORK_DIVERGENCES, map_forward

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "tests", "reference"))


def is_harness(directory, name):
    """C compiled with the program (ffi's NAME.c and NAME.types.h, freestanding's environments), not a snapshot."""
    family = directory.split("/")[-1]
    return (family in ("ffi", "freestanding") and name.endswith(".c")) or name.endswith(".types.h")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nova", required=True)
    args = parser.parse_args()
    nova = os.path.abspath(args.nova)
    tag = subprocess.run(["git", "-C", nova, "describe", "--tags"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", nova, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if tag != "v0.6.0" or dirty:
        sys.exit(f"fork_corpus: {nova} must be a clean checkout of v0.6.0 (it is {tag or 'untagged'}"
                 f"{', with changes' if dirty else ''})")
    shutil.rmtree(OUT, ignore_errors=True)
    sources = companions = 0
    for base, directories, names in os.walk(nova):
        directories[:] = sorted(d for d in directories if d not in (".git", "bin", "obj", "node_modules"))
        relative = os.path.relpath(base, nova).replace(os.sep, "/")
        in_corpus = relative == "tests/corpus" or relative.startswith("tests/corpus/")
        for name in sorted(names):
            path = name if relative == "." else f"{relative}/{name}"
            with open(os.path.join(base, name), "rb") as f:
                data = f.read()
            if name.endswith(".nova"):
                target = path[:-len(".nova")] + ".cee"
                if path in FORK_DIVERGENCES:
                    data = map_forward(data)
                sources += 1
            elif in_corpus and is_harness(relative, name):
                data, target = map_forward(data), path
                companions += 1
            elif in_corpus:
                target = path
                companions += 1
            else:
                continue
            full = os.path.join(OUT, target)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(f"""# CeeSafe's reference corpus

Written by `tools/fork_corpus.py` from Nova {tag} at the fork point (`docs/fork-point.md`): Nova's corpus, benchmarks,
programs and libraries as `.cee` files, with CeeSafe's names in the C harnesses; the snapshots stay Nova's, the frozen
baseline, and ceesafec's output is mapped back before it is compared with them. The comparison tools
run ceesafec here and novac in the Nova checkout. Do not edit by hand before the fork's first CeeSafe-only change.
""")
    print(f"fork_corpus: {sources} sources, {companions} companion files from Nova {tag} into {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
