#!/usr/bin/env python3
"""Compares ceesafec's token dump with the reference lexer's (docs/p2-frontend.md §3).

Runs `ceesafec parse --dump-tokens FILE...` and the token-dump oracle (tools/oracles/token-dump, built against the
pinned Nova tag) over the same files in batches, from the same working directory, and compares the outputs byte for
byte: tokens, spans, literal values, doc comments, comments and lexer diagnostics. Identifier ids are shared across a
batch in both, as in one novac invocation.

usage: tools/compare_tokens.py --ceesafec out/ceesafe --oracle PATH/token-dump [--root DIR] [--batch N] PATH...
  PATH is a .nova file or a directory searched for .nova files; relative paths are taken from --root (default: the
  current directory), which is also the working directory of both programs.
"""

import argparse
import os
import subprocess
import sys


def files_of(root, paths):
    result = []
    for p in paths:
        full = os.path.join(root, p)
        if os.path.isdir(full):
            for d, dirs, names in os.walk(full):
                dirs.sort()
                for n in sorted(names):
                    if n.endswith(".nova"):
                        result.append(os.path.relpath(os.path.join(d, n), root))
        else:
            result.append(p)
    return result


def run(argv, root):
    p = subprocess.run(argv, cwd=root, capture_output=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--batch", type=int, default=50)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    ceesafec = os.path.abspath(os.path.expanduser(args.ceesafec))
    oracle = os.path.abspath(os.path.expanduser(args.oracle))
    files = files_of(args.root, args.paths)
    differ, total_lines = 0, 0
    for i in range(0, len(files), args.batch):
        batch = files[i:i + args.batch]
        _, mine, mine_err = run([ceesafec, "parse", "--dump-tokens", "--diagnostics-format=json"] + batch, args.root)
        status, ref, ref_err = run([oracle] + batch, args.root)
        if status != 0:
            sys.exit(f"compare_tokens: the oracle failed on {batch[0]}..: {ref_err.decode(errors='replace')[:500]}")
        # ceesafec prints the JSON document after the dump; the oracle prints only the dump.
        mine_dump = mine[:mine.rfind(b"\n{\"version\"") + 1] if b"\n{\"version\"" in mine else mine
        ref_lines, mine_lines = ref.split(b"\n"), mine_dump.split(b"\n")
        total_lines += len(ref_lines)
        if ref_lines != mine_lines:
            differ += 1
            current = None
            for k in range(max(len(ref_lines), len(mine_lines))):
                r = ref_lines[k] if k < len(ref_lines) else b"<end>"
                m = mine_lines[k] if k < len(mine_lines) else b"<end>"
                if r.startswith(b"file "):
                    current = r
                if r != m:
                    print(f"DIFF in {current.decode(errors='replace') if current else '?'} at dump line {k + 1}:")
                    print(f"  reference: {r.decode(errors='replace')[:200]}")
                    print(f"  ceesafec:  {m.decode(errors='replace')[:200]}")
                    break
            if mine_err.strip():
                print(f"  ceesafec stderr: {mine_err.decode(errors='replace')[:300]}")
    print(f"compare_tokens: {len(files)} files in {(len(files) + args.batch - 1) // args.batch} batches, "
          f"{total_lines} dump lines; {differ} batches differ")
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
