#!/usr/bin/env python3
"""Reference inventory for the CeeSafe port (ROADMAP P0).

Reads a Nova checkout and writes a deterministic Markdown inventory of everything the port must cover:
C# source files, CLI commands and options, diagnostic codes (with the files that emit them and the corpus
files that annotate them), runtime and library files, embedded resources, and test families. Each item is
assigned the roadmap phase that ports it, using the rules in PHASE_RULES below.

The output depends only on the checkout's contents (sorted ordinally, no timestamps, no absolute paths),
so rerunning it after a rebaseline gives a reviewable diff.

usage: tools/inventory.py [--nova ~/Nova] [-o docs/reference-inventory.md] [--allow-dirty]
"""

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict

GENERATOR = "tools/inventory.py v1"

# C# file (path relative to src/) -> roadmap phase. First matching prefix wins; every file must match one.
PHASE_RULES = [
    ("Nova.Compiler/NovaVersion.cs", "P1"),
    ("Nova.Compiler/Semantics/IntegerSemantics.cs", "P1+P3"),
    ("Nova.Compiler/Semantics/FloatSemantics.cs", "P1+P3"),
    ("Nova.Compiler/Syntax/", "P2"),
    ("Nova.Compiler/Diagnostics/", "P2"),
    ("Nova.Compiler/Semantics/", "P3"),
    ("Nova.Compiler/Hir/", "P3"),
    ("Nova.Compiler/Compilation.cs", "P3+P4"),
    ("Nova.Compiler/Nir/ClosureSpecialisation.cs", "P7"),
    ("Nova.Compiler/Nir/", "P4"),
    ("Nova.Compiler/Analysis/CheckElimination.cs", "P7"),
    ("Nova.Compiler/Analysis/PlacementAnalysis.cs", "P7"),
    ("Nova.Compiler/Analysis/", "P4"),
    ("Nova.Compiler/Backend.C/CStructurer.cs", "P7"),
    ("Nova.Compiler/Backend.C/", "P5"),
    ("Nova.Compiler/CoreLibrary.cs", "P5"),
    ("Nova.Compiler/Interpreter/", "P8"),
    ("Nova.Compiler/Packages/Manifest.cs", "P6R+P8"),
    ("Nova.Compiler/Packages/", "P8"),
    ("Nova.Compiler/Formatting/", "P8"),
    ("Nova.Compiler/Documentation/", "P8"),
    ("Nova.Compiler/Tooling/", "P8"),
    ("Nova.Cli/", "P1..P8"),
]

# CLI command -> phase in which the command reaches parity (ROADMAP §4).
COMMAND_PHASES = {
    "parse": "P2", "check": "P4", "build": "P5 (flat C), P7 (all options)", "run": "P8 (interpreter)",
    "fmt": "P8", "new": "P8", "agents": "P8", "fetch": "P8", "publish": "P8", "index-check": "P8",
    "lsp": "P8", "mcp": "P8", "fix": "P8", "explain": "P8", "doc": "P8",
}

# CLI option -> phase.
OPTION_PHASES = {
    "--diagnostics-format": "P2 (text), P8 (json)", "--dump-ast": "P2", "--dump-hir": "P3", "--dump-nir": "P4",
    "--emit": "P5", "--kernel": "P3", "--profile": "P3", "--no-float": "P3", "-o": "P5", "--cc": "P5",
    "--cflag": "P5", "--ld": "P5", "--line-directives": "P5", "-g": "P5", "--flat-c": "P7",
    "--interp": "P8", "--no-placement": "P7", "--explain-allocations": "P7", "--no-bce": "P7",
    "--explain-bounds-checks": "P7", "--no-oce": "P7", "--explain-overflow-checks": "P7",
    "--no-closure-specialisation": "P7", "--split": "P7", "--program": "P7", "--explain-closure-calls": "P7",
}

# Test class -> phase whose gate it belongs to.
TEST_PHASES = {
    "Lexer": "P2", "Parser": "P2", "Corpus": "P2-P4", "PrivateField": "P3", "Package": "P3",
    "NicheLayout": "P5", "FloatFormat": "P1+P5", "RuntimeSemantics": "P5", "Backend": "P5", "SourceMap": "P5",
    "RunCorpus": "P5", "Ffi": "P5", "Freestanding": "P5", "KernelLibrary": "P5", "Unsafe": "P4",
    "Mutation": "P4", "FaultInjection": "P5", "CollectionProperty": "P5", "Program": "P5",
    "StructuredC": "P7", "CheckElimination": "P7", "Placement": "P7", "ClosureSpecialisation": "P7",
    "Msvc": "P9", "ToolchainReport": "P5", "Fuzz": "P9", "Interpreter": "P8", "Formatter": "P8", "Doc": "P8",
    "Cli": "P8", "Lsp": "P8", "Mcp": "P8", "Fix": "P8", "AgentFiles": "P8", "Debugger": "P8",
    "InstallScript": "P9", "PackageManager": "P8", "Readme": "P5", "Site": "P8",
}

# Corpus family -> phase whose gate requires it.
CORPUS_PHASES = {
    "parse-pass": "P2", "parse-fail": "P2", "check-pass": "P3", "check-fail": "P3/P4", "run-pass": "P5",
    "run-fail": "P5", "emit-c": "P5", "ffi": "P5", "freestanding": "P5", "bounds-checks": "P7",
    "overflow-checks": "P7", "placement": "P7", "closure-calls": "P7",
}


# The paths the inventory reads: a change elsewhere in the checkout does not make it dirty.
INPUT_PATHS = ["src", "tests", "lib", "runtime", "docs/diagnostics.md"]


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def line_count(path):
    with open(path, "rb") as f:
        return f.read().count(b"\n")


def files_under(root, base, suffixes):
    result = []
    for directory, dirs, names in os.walk(os.path.join(root, base)):
        dirs[:] = sorted(d for d in dirs if d not in ("bin", "obj", "node_modules"))
        for name in names:
            if name.endswith(suffixes):
                result.append(os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/"))
    return sorted(result)


def phase_of(path):
    for prefix, phase in PHASE_RULES:
        if path.startswith(prefix):
            return phase
    sys.exit(f"inventory: no phase rule for {path}")


def parse_usage(program_cs):
    """Commands and options from the CLI's usage text (src/Nova.Cli/Program.cs)."""
    text = read(program_cs)
    usage = text[text.index('private const string Usage = """'):]
    usage = usage[:usage.index('""";')]
    # An entry starts at a 10-space indent; deeper lines continue its description.
    entries = {"commands": [], "options": []}
    section = None
    for line in usage.splitlines():
        stripped = line.strip()
        if stripped in ("commands:", "options:"):
            section = stripped[:-1]
        elif section and re.match(r"^ {10}\S", line):
            entries[section].append(stripped)
        elif section and stripped and entries[section]:
            entries[section][-1] += " " + stripped
    commands = []
    for entry in entries["commands"]:
        name, _, description = entry.partition(" ")
        commands.append((name, description.strip()))
    options = []
    for entry in entries["options"]:
        m = re.match(r"^(\S+)(?: (?!\()(\S+))?\s*(.*)$", entry)
        options.append((m.group(1), m.group(2) or "", m.group(3)))
    return commands, options


def cell(text):
    """Text for a Markdown table cell."""
    return text.replace("|", "\\|")


def diagnostic_codes(nova):
    text = read(os.path.join(nova, "src/Nova.Compiler/Diagnostics/Diagnostic.cs"))
    codes = re.findall(r'public const string (\w+) = "(N\d{4})";', text)
    return sorted(codes, key=lambda c: c[1])


def code_emitters(nova, cs_files, names):
    emitters = defaultdict(set)
    for path in cs_files:
        if path.endswith("Diagnostics/Diagnostic.cs"):
            continue
        text = read(os.path.join(nova, "src", path))
        for name in set(re.findall(r"DiagnosticCodes\.(\w+)", text)):
            if name in names:
                emitters[name].add(path)
    return emitters


def corpus_annotations(nova):
    """Code -> sorted corpus files annotating it with // error[CODE]."""
    result = defaultdict(set)
    for path in files_under(nova, "tests/corpus", (".nova",)):
        for code in re.findall(r"// error\[(N\d{4})\]", read(os.path.join(nova, path))):
            result[code].add(path.removeprefix("tests/corpus/"))
    return result


def documented_codes(nova):
    """(codes with a row in docs/diagnostics.md, codes whose row says they are retired)."""
    rows = re.findall(r"^\| (N\d{4}) \| (.*)$", read(os.path.join(nova, "docs/diagnostics.md")), re.M)
    return {code for code, _ in rows}, {code for code, rest in rows if rest.startswith("*Retired")}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nova", default=os.path.expanduser("~/Nova"))
    parser.add_argument("-o", "--output", default="docs/reference-inventory.md")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    nova = args.nova

    commit = run(["git", "rev-parse", "HEAD"], nova).strip()
    dirty = run(["git", "status", "--porcelain", "--untracked-files=no", "--", *INPUT_PATHS], nova).strip()
    if dirty and not args.allow_dirty:
        sys.exit("inventory: the Nova checkout has uncommitted changes; commit them or pass --allow-dirty")
    version = re.search(r'Text = "([^"]+)"', read(os.path.join(nova, "src/Nova.Compiler/NovaVersion.cs"))).group(1)

    out = []
    w = out.append
    w("# Reference inventory")
    w("")
    w(f"Generated by `{GENERATOR}` from Nova `{commit}` ({version}"
      f"{', **dirty tree**' if dirty else ', clean tree'}). Do not edit: rerun the script.")
    w("Phases are the ROADMAP's; the rules that assign them are in the script. `docs/parity.md` tracks status.")
    w("")

    # 1. C# sources.
    cs_files = [p.removeprefix("src/") for p in files_under(nova, "src", (".cs",))]
    w("## 1. Compiler and CLI sources")
    w("")
    w("| File | Lines | Phase |")
    w("|---|---:|---|")
    by_phase = defaultdict(int)
    total = 0
    for path in cs_files:
        n = line_count(os.path.join(nova, "src", path))
        total += n
        by_phase[phase_of(path)] += n
        w(f"| `{path}` | {n:,} | {phase_of(path)} |")
    w(f"| **total ({len(cs_files)} files)** | **{total:,}** | |")
    w("")
    w("Lines by phase: " + ", ".join(f"{p} {n:,}" for p, n in sorted(by_phase.items())) + ".")
    w("")

    # 2. CLI.
    commands, options = parse_usage(os.path.join(nova, "src/Nova.Cli/Program.cs"))
    w("## 2. CLI commands and options (`src/Nova.Cli/Program.cs`, usage text)")
    w("")
    w("| Command | Phase | Description |")
    w("|---|---|---|")
    for name, description in commands:
        w(f"| `{name}` | {COMMAND_PHASES.get(name, '**unmapped**')} | {cell(description)} |")
    w("")
    w("| Option | Argument | Phase | Description |")
    w("|---|---|---|---|")
    for name, argument, description in options:
        w(f"| `{name}` | {('`' + cell(argument) + '`') if argument else ''} | {OPTION_PHASES.get(name, '**unmapped**')} "
          f"| {cell(description)} |")
    w("")
    w("Also: `--version`, `-h`/`--help`, `--offline` (package commands), `--check`/`--stdout` (fmt), `--lib` (new), "
      "`--update` (fetch), `--dry-run` (fix), `--title`/`--missing` (doc), `--agent`/`--no-agent` (new, agents): "
      "parsed in `Program.cs`, not all in the usage text.")
    w("")

    # 3. Diagnostics.
    codes = diagnostic_codes(nova)
    names = {name for name, _ in codes}
    emitters = code_emitters(nova, cs_files, names)
    annotated = corpus_annotations(nova)
    documented, retired = documented_codes(nova)
    w(f"## 3. Diagnostic codes ({len(codes)}; `src/Nova.Compiler/Diagnostics/Diagnostic.cs`)")
    w("")
    w("Phase: the latest phase among the files that emit the code (a code is complete when all its emitters are "
      "ported). Corpus: the files annotating it with `// error[CODE]`.")
    w("")
    w("| Code | Name | Emitted by | Phase | Corpus files | In diagnostics.md |")
    w("|---|---|---|---|---:|---|")
    order = ["P1", "P1+P3", "P2", "P3", "P3+P4", "P4", "P5", "P6R+P8", "P7", "P8", "P1..P8"]
    uncovered = []
    for name, code in codes:
        files = sorted(emitters.get(name, ()))
        phases = sorted({phase_of(f) for f in files}, key=order.index)
        phase = phases[-1] if phases else ("retired" if code in retired else "**no emitter**")
        short = ", ".join(f.split("/")[-1].removesuffix(".cs") for f in files) or "—"
        count = len(annotated.get(code, ()))
        if count == 0:
            uncovered.append(code)
        w(f"| {code} | {name} | {short} | {phase} | {count} | {'yes' if code in documented else '**no**'} |")
    w("")
    w(f"Codes with no corpus annotation ({len(uncovered)}; covered by unit tests or not at all — P0 records which): "
      + ", ".join(uncovered) + ".")
    w("")

    # 4. Runtime, libraries and resources.
    w("## 4. Runtime, libraries and embedded resources")
    w("")
    w("| File | Lines | Carried over in |")
    w("|---|---:|---|")
    for path in files_under(nova, "runtime", (".c", ".h")) + files_under(nova, "lib", (".nova",)):
        w(f"| `{path}` | {line_count(os.path.join(nova, path)):,} | P5 |")
    w("")
    rt = read(os.path.join(nova, "runtime/include/nova/rt.h"))
    groups = defaultdict(int)
    for symbol in sorted(set(re.findall(r"\b((?:nova|nv|NOVA|NV)_[A-Za-z0-9_]+)", rt))):
        parts = symbol.split("_")
        groups["_".join(parts[:2]) + ("_*" if len(parts) > 2 else "")] += 1
    w("Symbols named in `runtime/include/nova/rt.h`, grouped by prefix (the ABI the P7 rename must version):")
    w("")
    w(", ".join(f"`{g}` {n}" for g, n in sorted(groups.items())) + ".")
    w("")
    csproj = read(os.path.join(nova, "src/Nova.Compiler/Nova.Compiler.csproj"))
    w("Embedded resources (`Nova.Compiler.csproj`): " + ", ".join(
        f"`{r}`" for r in sorted(set(re.findall(r'LogicalName="([^"]+)"', csproj)))) + ".")
    w("")

    # 5. Tests.
    w("## 5. Tests")
    w("")
    w("| Test class | Lines | Phase |")
    w("|---|---:|---|")
    for path in files_under(nova, "tests/Nova.Compiler.Tests", ("Tests.cs",)):
        stem = os.path.basename(path).removesuffix("Tests.cs")
        w(f"| `{stem}Tests` | {line_count(os.path.join(nova, path)):,} | {TEST_PHASES.get(stem, '**unmapped**')} |")
    w("")
    w("| Corpus family | `.nova` files | Other files | Phase |")
    w("|---|---:|---:|---|")
    corpus = os.path.join(nova, "tests/corpus")
    for family in sorted(os.listdir(corpus)):
        if not os.path.isdir(os.path.join(corpus, family)):
            continue
        names_in = os.listdir(os.path.join(corpus, family))
        nova_files = sum(1 for n in names_in if n.endswith(".nova"))
        w(f"| `{family}` | {nova_files} | {len(names_in) - nova_files} | {CORPUS_PHASES.get(family, '**unmapped**')} |")
    w("")

    text = "\n".join(out) + "\n"
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    unmapped = text.count("**unmapped**") + text.count("**no emitter**")
    print(f"inventory: wrote {args.output} ({len(cs_files)} sources, {len(commands)} commands, {len(options)} options, "
          f"{len(codes)} codes; {unmapped} unmapped)")


if __name__ == "__main__":
    main()
