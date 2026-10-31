#!/usr/bin/env python3
"""Compares ceesafec's command line with the pinned novac's (docs/p8-plan.md S0).

- usage: `--help`, no arguments, an unknown command, the usage errors of `explain`, `doc` and `fmt`, and a bad
  `--diagnostics-format`;
- explain: every code N0000-N0999, lower case too, and malformed codes;
- fix: every check-fail and parse-fail corpus file and the reference's FixTests programs, each in a scratch directory
  as `main.nova`: `fix --dry-run`, `fix --diagnostics-format=json --dry-run`, then `fix` itself and the file it leaves.

Each run must give the same exit status, stdout and stderr, and `fix` the same file, once ceesafec's output has
CeeSafe's names mapped back to Nova's (tools/names.py).

usage: python3 tools/compare_cli.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root NOVA_CHECKOUT
       [--only usage|explain|fix] [--jobs N]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from names import FORK_DIVERGENCES, cee_path, map_back

# The reference's FixTests programs (Missing_mut_is_inserted ... No_fix_where_the_repair_is_not_certain).
FIX_PROGRAMS = (
    "fn bump(x: borrow mut i32) { x += 1; }\nfn main() { var n = 1; bump(n); Console.writeLine(n); }\n",
    "fn bump(x: borrow mut i32) { x += 1; }\nfn main() { let n = 1; bump(n); Console.writeLine(n); }\n",
    "fn look(x: borrow i32) -> i32 => x;\nfn main() { var n = 1; Console.writeLine(look(mut n)); }\n",
    "fn main() { let n = 1; n = 2; Console.writeLine(n); }\n",
    "fn bump(x: borrow mut i32) { x += 1; }\nfn main() { let n = 1; bump(mut n); Console.writeLine(n); }\n",
    "fn main() { let wide: i64 = 300; Console.writeLine(1 + wide as u8); }\n",
    "fn main() { let wide: i64 = 300; Console.writeLine((wide + 1) as u8); }\n",
    "fn main() {\n    let n = 1\n    Console.writeLine(n);\n}\n",
    "fn f(n: i32) { n = 2; }\n",
    "fn main() { for (i in 0..3) { i = 1; } }\n",
    "struct P { x: i32; }\nfn f(p: borrow P) { p.x = 1; }\n",
    "fn main() { var a = 1; let r = borrow a; r = 2; }\n",
    "fn main() { let x: i32 = 1; let b = x as bool; }\n",
    "fn main() { let x = 1 2; }\n",
    "fn f(x: i32) -> i32 { let s = if (x < 0) { -1 } else { 1 }; return s; }\n",
    # Several fixes in one file, two rounds, and a fix that waits for the next round.
    "fn bump(x: borrow mut i32) { x += 1; }\nfn main() {\n    let n = 1\n    bump(n);\n    let m = 2;\n    m = 3;\n"
    "    bump(m);\n}\n",
)


def run(compiler, arguments, cwd=None, cee=False):
    """With `cee` (ceesafec since the fork, Decision 0005), a `.nova` file argument is named `.cee`."""
    p = subprocess.run([compiler] + ([cee_path(a) for a in arguments] if cee else arguments), cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def same(mine, ref):
    return (mine[0], map_back(mine[1]), map_back(mine[2])) == ref


def usage_cases():
    return [[], ["--help"], ["-h"], ["frobnicate"], ["explain"], ["explain", "N0100", "N0101"],
            ["explain", "--diagnostics-format=xml", "N0100"], ["explain", "--diagnostics-format=json", "N0100"],
            ["check", "--diagnostics-format"], ["parse", "--no-such-option", "a.nova"],
            ["doc", "-o"], ["doc", "--title"], ["doc", "--bogus", "a.nova"],
            ["fmt", "--check", "--stdout", "a.nova"], ["fmt", "--bogus", "a.nova"], ["fmt", "--stdout", "a.nova", "b.nova"],
            ["fmt", "--diagnostics-format=json", "--bogus"]]


def explain_cases():
    cases = [["explain", f"N{n:04d}"] for n in range(1000)]
    cases += [["explain", f"n{n:04d}"] for n in (100, 201, 249, 324)]
    cases += [["explain", c] for c in ("N1", "N01000", "X0100", "", "n0100x")]
    return cases


def fix_case(cee, novac, name, text):
    """The differences for one program, or an empty list."""
    problems = []
    with tempfile.TemporaryDirectory() as work:
        mine_dir, ref_dir = os.path.join(work, "c"), os.path.join(work, "n")
        os.mkdir(mine_dir)
        os.mkdir(ref_dir)
        for arguments in (["fix", "--dry-run", "main.nova"],
                          ["fix", "--diagnostics-format=json", "--dry-run", "main.nova"],
                          ["fix", "main.nova"]):
            for d, file in ((mine_dir, "main.cee"), (ref_dir, "main.nova")):
                with open(os.path.join(d, file), "wb") as f:
                    f.write(text)
            mine, ref = run(cee, arguments, mine_dir, True), run(novac, arguments, ref_dir)
            if not same(mine, ref):
                problems.append(f"{name}: {' '.join(arguments)}: output differs")
            with open(os.path.join(mine_dir, "main.cee"), "rb") as a, open(os.path.join(ref_dir, "main.nova"), "rb") as b:
                if a.read() != b.read():
                    problems.append(f"{name}: {' '.join(arguments)}: the fixed file differs")
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True, help="a Nova checkout at the pinned tag (for the corpus)")
    parser.add_argument("--only", choices=("usage", "explain", "fix"))
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    failures = []
    with ThreadPoolExecutor(options.jobs) as pool:
        for part, cases in (("usage", usage_cases()), ("explain", explain_cases())):
            if options.only not in (None, part):
                continue
            results = list(pool.map(lambda a: (a, run(cee, a, cee=True), run(novac, a)), cases))
            differ = [a for a, mine, ref in results if not same(mine, ref)]
            failures += [f"{part}: {' '.join(a) or '(no arguments)'}" for a in differ]
            print(f"compare_cli {part}: {len(cases)} runs, {len(cases) - len(differ)} identical, {len(differ)} differ")
        if options.only in (None, "fix"):
            corpus = os.path.join(options.root, "tests", "corpus")
            programs = []
            for family in ("check-fail", "parse-fail"):
                for name in sorted(os.listdir(os.path.join(corpus, family))):
                    if name.endswith(".nova") and f"tests/corpus/{family}/{name}" not in FORK_DIVERGENCES:
                        with open(os.path.join(corpus, family, name), "rb") as f:
                            programs.append((f"{family}/{name}", f.read()))
            programs += [(f"FixTests #{k}", t.encode()) for k, t in enumerate(FIX_PROGRAMS)]
            results = list(pool.map(lambda p: fix_case(cee, novac, p[0], p[1]), programs))
            problems = [p for r in results for p in r]
            failures += problems
            differ = sum(1 for r in results if r)
            print(f"compare_cli fix: {len(programs)} programs, {len(programs) - differ} identical, {differ} differ")
    for f in failures:
        print("differ:", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
