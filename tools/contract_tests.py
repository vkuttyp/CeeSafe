#!/usr/bin/env python3
"""Every contract test of the port against one ceesafec (ROADMAP P6: "both pass the compiler contract tests").

Runs, against the pinned novac and the reference corpus at the pinned tag:
- parse and check comparisons (text, JSON, dumps), NIR comparisons, C comparisons in four shapes (flat, --split, -g,
  -g --split) both in P5's form (everything off) and in novac's default form (everything on, P7), the latter also over
  the benchmarks and programs, the four optimisation reports, CeeSafe's own C, the package fixtures;
- the corpus runner over run-pass, run-fail, ffi (and freestanding) under -Werror and ASan+UBSan with leak checks, and
  over the optimisation families and emit-c's snapshots, all in the default form;
- the command line (usage, `explain`, `fix`), `fmt`, `doc`, the package commands, `run --interp`, the `lsp` and
  `mcp` servers and debugging with editors/debug (P8);
- the M2 mutation suite, the M3 fault sweep, the collection properties and the freestanding checks.

Each step's last line is printed; the expected results are the P2–P7 gates' (docs/p*-plan.md).

usage: python3 tools/contract_tests.py --ceesafec PATH --novac PATH --root <Nova checkout at the pinned tag>
"""
import argparse
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# The recorded divergences (ROADMAP §P4): novac's `check --dump-hir` crashes on three check-fail programs, and Nova #6.
KNOWN_CHECK_DIFFERENCES = {"tests/corpus/check-fail/enums.nova", "tests/corpus/check-fail/optionals.nova",
                           "tests/corpus/check-fail/results.nova", "tests/corpus/check-fail/offset-of.nova"}
# GCC 12 -O2 -Werror rejects novac's C for this program too (-Wuninitialized in an enum constructor; ROADMAP §P5).
KNOWN_GCC_RUN_FAILURES = {"run-pass/nested-patterns.nova"}


def is_gcc():
    """Whether the default C compiler ($CC, else cc) is GCC."""
    cc = os.environ.get("CC") or "cc"
    version = subprocess.run([cc, "--version"], capture_output=True, text=True).stdout
    return "Free Software Foundation" in version or version.startswith("gcc")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    cee = os.path.abspath(os.path.expanduser(args.ceesafec))
    novac = os.path.abspath(os.path.expanduser(args.novac))
    root = os.path.abspath(args.root)
    corpus = os.path.join(root, "tests", "corpus")
    families = sorted("tests/corpus/" + d for d in os.listdir(corpus) if os.path.isdir(os.path.join(corpus, d)))
    parse_families = [f for f in families if f.endswith("parse-pass") or f.endswith("parse-fail")]
    check_families = [f for f in families if f not in parse_families]
    others = sorted({os.path.relpath(base, root) for top in ("benchmarks", "programs")
                     for base, _, names in os.walk(os.path.join(root, top)) if any(n.endswith(".nova") for n in names)})
    everything = [x for part in ("bce", "oce", "placement", "closure-specialisation", "structured")
                  for x in ("--on", part)]
    py = [sys.executable, "-B"]
    common = ["--ceesafec", cee, "--novac", novac, "--root", root]
    run_families = ["--family", "run-pass", "--family", "run-fail", "--family", "ffi"]
    steps = [
        ("parse", py + [f"{HERE}/compare_parse.py"] + common + parse_families),
        ("check", py + [f"{HERE}/compare_parse.py"] + common + ["--command", "check", "--list", "@LIST"] +
         check_families),
        ("nir", py + [f"{HERE}/compare_nir.py"] + common + families),
        ("c flat", py + [f"{HERE}/compare_c.py"] + common + families),
        ("c split", py + [f"{HERE}/compare_c.py"] + common + ["--extra=--split"] + families),
        ("c -g", py + [f"{HERE}/compare_c.py"] + common + ["--extra=-g"] + families),
        ("c -g split", py + [f"{HERE}/compare_c.py"] + common + ["--extra=-g", "--extra=--split"] + families),
        ("nir default", py + [f"{HERE}/compare_nir.py"] + common + ["--on", "closure-specialisation"] + families),
        ("c default", py + [f"{HERE}/compare_c.py"] + common + everything + families + others),
        ("c d. split", py + [f"{HERE}/compare_c.py"] + common + everything + ["--extra=--split"] + families + others),
        ("c d. -g", py + [f"{HERE}/compare_c.py"] + common + everything + ["--extra=-g"] + families + others),
        ("c d. -g split", py + [f"{HERE}/compare_c.py"] + common + everything + ["--extra=-g", "--extra=--split"] +
         families + others),
    ] + [
        (f"report {report[:10]}", py + [f"{HERE}/compare_reports.py"] + common + ["--report", report] + families + others)
        for report in ("allocations", "bounds-checks", "closure-calls", "overflow-checks")
    ] + [
        ("self default", py + [f"{HERE}/compare_self.py", "--ceesafec", cee, "--novac", novac] + everything),
        ("self d. split", py + [f"{HERE}/compare_self.py", "--ceesafec", cee, "--novac", novac] + everything +
         ["--extra=--split", "--extra=-g"]),
        ("packages", py + [f"{HERE}/compare_packages.py", "--ceesafec", cee, "--novac", novac]),
        ("cli", py + [f"{HERE}/compare_cli.py"] + common),
        ("fmt", py + [f"{HERE}/compare_fmt.py"] + common),
        ("doc", py + [f"{HERE}/compare_doc.py"] + common),
        ("package cmds", py + [f"{HERE}/compare_package_commands.py", "--ceesafec", cee, "--novac", novac]),
        ("interp", py + [f"{HERE}/compare_interp.py"] + common),
        ("servers", py + [f"{HERE}/compare_servers.py"] + common),
        ("debugger", py + [f"{HERE}/debugger_check.py", "--ceesafec", cee]),
        ("run -Werror", py + [f"{HERE}/run_corpus.py", "--compiler", cee, "--corpus", corpus] + run_families +
         ["--cflag=-Werror"]),
        ("run asan", py + [f"{HERE}/run_corpus.py", "--compiler", cee, "--corpus", corpus] + run_families +
         ["--cc", "clang", "--cflag=-O1", "--cflag=-Werror", "--cflag=-fsanitize=address,undefined",
          "--cflag=-fno-sanitize-recover=all", "--check-leaks"]),
        ("families", py + [f"{HERE}/run_corpus.py", "--compiler", cee, "--corpus", corpus] +
         [x for f in ("emit-c", "bounds-checks", "overflow-checks", "placement", "closure-calls") for x in ("--family", f)]),
        ("mutations", py + [f"{HERE}/mutation_suite.py", "--compiler", cee]),
        ("fault sweep", py + [f"{HERE}/fault_injection.py", "--compiler", cee, "--reference", novac, "--corpus",
                              corpus]),
        ("collections", py + [f"{HERE}/collection_properties.py", "--compiler", cee, "--reference", novac, "--sweep"]),
        ("freestanding", py + [f"{HERE}/freestanding_check.py", "--compiler", cee, "--corpus", corpus]),
    ]
    failed = 0
    with tempfile.TemporaryDirectory() as work:
        listing = os.path.join(work, "differ.txt")
        for name, argv in steps:
            argv = [listing if a == "@LIST" else a for a in argv]
            p = subprocess.run(argv, cwd=os.path.join(HERE, ".."), capture_output=True, text=True)
            lines = [line for line in (p.stdout + p.stderr).splitlines() if line.strip()]
            summary = " | ".join(lines[-3:]) if name.startswith("run") else (lines[-1] if lines else "(no output)")
            ok = p.returncode == 0
            failures = {line.split()[1] for line in lines if line.startswith("FAIL ")}
            if name == "run -Werror" and not ok and failures and failures <= KNOWN_GCC_RUN_FAILURES and is_gcc():
                ok = True
                summary += f" (GCC: {', '.join(sorted(failures))}, recorded)"
            if name == "check" and os.path.exists(listing):
                with open(listing, encoding="utf-8") as f:
                    differ = {line.strip() for line in f if line.strip()}
                ok = differ == KNOWN_CHECK_DIFFERENCES
                summary += " (the recorded divergences)" if ok else f" (unexpected: {sorted(differ ^ KNOWN_CHECK_DIFFERENCES)})"
            print(f"{name:17} {'ok  ' if ok else 'FAIL'} {summary}")
            failed += not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
