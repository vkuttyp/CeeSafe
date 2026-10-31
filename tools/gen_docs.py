#!/usr/bin/env python3
"""Writes src/library/documents.cee: the documents ceesafec embeds for `explain` and `mcp` (Nova's EmbeddedDocs).

By default they are CeeSafe's own (Decision 0006): spec/*.md, spec/api/*.md, spec/decisions/*.md, guide/*.md,
guide/coming-from/*.md and templates/AGENTS.md from the working tree. With --reference they are what novac 0.6.0
embeds, for the build that compares the section-finding algorithms with novac's (tools/reference_docs.py): Nova.Compiler.csproj's embedded `.md`
resources (docs/*.md, docs/api/*.md, docs/decisions/*.md, docs/cosmoos/profiles.md, site/guide/*.md,
site/guide/coming-from/*.md and templates/AGENTS.md, the template under CeeSafe's names as since S7), read with
`git show TAG:PATH` from a Nova repository.

Either way the documents are taken by repository path in ordinal order; as EmbeddedDocs.Load does, a leading BOM is
dropped and every line ending (CR LF, CR, NEL, LS, PS, FF) becomes "\\n". Each document is a run of string literals of
at most 4,000 bytes, as in src/library/runtime.cee. The places the tools look for (the specification's directory, the
diagnostics table, the agent guide, the introduction, the agent template) are written as functions beside them.

usage: python3 tools/gen_docs.py                                   (CeeSafe's documents, into src/library/documents.cee)
       python3 tools/gen_docs.py --reference [--nova PATH] [--tag TAG] [-o FILE]   (default ~/Nova, v0.6.0)
       (formats with $CEESAFEC, default out/ceesafec)
"""

import argparse
import os
import re
import subprocess

from gen_library import literal
from names import map_forward

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# (directory, whether every .md directly in it is embedded, or the one file embedded from it)
NOVA_PATTERNS = (("docs", None), ("docs/api", None), ("docs/decisions", None), ("docs/cosmoos", "profiles.md"),
                 ("site/guide", None), ("site/guide/coming-from", None), ("templates", "AGENTS.md"))
CEESAFE_PATTERNS = (("spec", None), ("spec/api", None), ("spec/decisions", None), ("guide", None),
                    ("guide/coming-from", None), ("templates", "AGENTS.md"))

# The places explain and mcp look for, in each set: (function, CeeSafe's path, novac's path).
PLACES = (("specDirectory", "spec/", "docs/"),
          ("diagnosticsDocument", "spec/diagnostics.md", "docs/diagnostics.md"),
          ("agentGuideDocument", "guide/for-agents.md", "site/guide/for-agents.md"),
          ("introductionDocument", "guide/introduction.md", "site/guide/introduction.md"),
          ("agentTemplateDocument", "templates/AGENTS.md", "templates/AGENTS.md"))

# .NET's String.ReplaceLineEndings: CR LF, then any of CR, LF, FF, NEL, LS, PS.
LINE_ENDINGS = re.compile("\r\n|[\r\n\f\u0085\u2028\u2029]")


def listed(nova, tag, directory):
    out = subprocess.run(["git", "-C", nova, "ls-tree", "--name-only", f"{tag}:{directory}"], capture_output=True,
                         check=True, text=True).stdout
    return [name for name in out.splitlines() if name.endswith(".md")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reference", action="store_true", help="novac 0.6.0's documents, not CeeSafe's")
    parser.add_argument("--nova", default=os.path.expanduser("~/Nova"))
    parser.add_argument("--tag", default="v0.6.0")
    parser.add_argument("-o", dest="out", default=os.path.join(ROOT, "src", "library", "documents.cee"))
    args = parser.parse_args()
    paths = []
    for directory, only in (NOVA_PATTERNS if args.reference else CEESAFE_PATTERNS):
        names = (listed(args.nova, args.tag, directory) if args.reference else
                 sorted(n for n in os.listdir(os.path.join(ROOT, directory)) if n.endswith(".md")))
        for name in names:
            if only is None or name == only:
                paths.append(f"{directory}/{name}")
    paths.sort(key=lambda p: p.encode("utf-16-le"))  # StringComparer.Ordinal compares UTF-16 code units
    files = []
    for path in paths:
        if args.reference:
            data = subprocess.run(["git", "-C", args.nova, "show", f"{args.tag}:{path}"], capture_output=True,
                                  check=True).stdout
        else:
            with open(os.path.join(ROOT, path), "rb") as f:
                data = f.read()
        text = data.decode("utf-8")
        if text.startswith("\ufeff"):
            text = text[1:]
        text = LINE_ENDINGS.sub("\n", text)
        if args.reference and path == "templates/AGENTS.md":
            text = map_forward(text)
        files.append((path, text))
    chunks = []
    for k, (_, t) in enumerate(files):
        current, size = [], 0
        for ch in t:
            n = len(ch.encode("utf-8"))
            if size + n > 4000:
                chunks.append((k, "".join(current)))
                current, size = [], 0
            current.append(ch)
            size += n
        chunks.append((k, "".join(current)))
    counts = [sum(1 for f, _ in chunks if f == k) for k in range(len(files))]
    firsts, total = [], 0
    for n in counts:
        firsts.append(total)
        total += n
    names = "\n".join(f"    {k} => \"{n}\"," for k, (n, _) in enumerate(files[:-1]))
    count_arms = "\n".join(f"    {k} => {n}," for k, n in enumerate(counts[:-1]))
    first_arms = "\n".join(f"    {k} => {f}," for k, f in enumerate(firsts[:-1]))
    chunk_arms = "\n".join(f"    {j} => {literal(text)}," for j, (_, text) in enumerate(chunks[:-1]))
    origin = (f"novac 0.6.0's documents (Nova {args.tag}), for tools/reference_docs.py" if args.reference else
              "CeeSafe's specification, guide and agent template (Decision 0006)")
    column = 1 if args.reference else 0
    places = "\n".join(f"fn {name}() -> StringView => \"{where[column]}\";" for name, *where in PLACES)
    source = f"""// The documents ceesafec embeds for `explain` and `mcp` (the reference's EmbeddedDocs: the specification, the
// guide and the agent template), by repository path in ordinal order: {origin}. GENERATED by tools/gen_docs.py:
// rerun it, do not edit. Each document is a run of chunks of at most 4,000 bytes (C11 §5.2.4.1).

// Where the tools look: the specification's documents (explain's tables, spec_section's short names), the diagnostics
// table, the agent guide (the write prompt), the introduction, the agent template (new, agents).
{places}

fn documentCount() -> usize => {len(files)};

fn documentPath(k: usize) -> StringView => match (k) {{
{names}
    _ => "{files[-1][0]}",
}};

fn documentChunkCount(k: usize) -> usize => match (k) {{
{count_arms}
    _ => {counts[-1]},
}};

fn documentFirstChunk(k: usize) -> usize => match (k) {{
{first_arms}
    _ => {firsts[-1]},
}};

fn documentChunk(j: usize) -> StringView => match (j) {{
{chunk_arms}
    _ => {literal(chunks[-1][1])},
}};

/// Appends the whole text of document `k`.
fn appendDocumentText(out: borrow mut Vector<u8>, k: usize) -> Result<void, AllocError> {{
    for (j in 0..documentChunkCount(k)) {{
        appendText(out, documentChunk(documentFirstChunk(k) + j))?;
    }}
    return Ok();
}}

/// The index of the document at `path`, or null (EmbeddedDocs.Read).
fn documentIndex(path: Slice<u8>) -> usize? {{
    for (k in 0..documentCount()) {{
        if (sameBytes(documentPath(k).bytes(), path)) {{
            return k;
        }}
    }}
    return null;
}}
"""
    out = args.out
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(source)
    formatter = os.environ.get("CEESAFEC", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out", "ceesafec"))
    subprocess.run([formatter, "fmt", out], check=True)


if __name__ == "__main__":
    main()
