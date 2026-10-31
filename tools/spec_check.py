#!/usr/bin/env python3
"""CeeSafe's specification against the compiler that embeds it (spec/testing.md §4, Decision 0006).

- explain: every diagnostic code in the catalog (src/diagnostics/catalog.cee) has an entry `ceesafec explain` finds
  (Nova's FixTests rule), and the embedded documents are the tree's (src/library/documents.cee is up to date);
- links: every relative link in spec/, guide/ and templates/ names a file that exists;
- api: spec/api/core.md is what `ceesafec doc lib/core --title "lib/core"` writes for the embedded lib/core (CeeSafe's
  copy in tests/reference/lib/core under CeeSafe's names, as tools/gen_library.py embeds it);
- names: no Nova C name, `.nova` file, `nova.toml` or `NOVA_HOME` outside URLs, the inherited ADRs and the places that
  name Nova's on purpose (ALLOWED).

usage: python3 tools/spec_check.py --ceesafec out/ceesafec
"""
import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile

from names import map_forward

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

NOVA_NAMES = re.compile(r"(?<![A-Za-z0-9])nv(?=[A-Z_])|nova_|(?<![A-Za-z0-9])NV_|NOVA_|nova/rt\.h|\.nova\b|nova\.toml|"
                        r"nova\.lock")
URL = re.compile(r"https?://[^\s)>`\"']+")

# (file, text on the line) where a Nova name is meant: the documents that say how CeeSafe relates to Nova.
ALLOWED = (("spec/c-backend.md", "Nova's runtime and generated names"),
           ("spec/c-backend.md", "In Nova before M7d, top-level functions were `nv_<name>`"),
           ("spec/c-backend.md", "the runtime's `nv_add_i32`"),
           ("guide/installation.md", "~/.nova/0.6.0/bin/novac"),
           ("spec/tooling.md", "`.nova` file, the same language at the fork"),  # §9: CosmoOS keeps its ports as Nova
           ("spec/tooling.md", "(default `~/.nova/bin/novac`"))


def documents():
    found = []
    for top in ("spec", "guide", "templates"):
        found += sorted(glob.glob(os.path.join(ROOT, top, "**", "*.md"), recursive=True))
    return found


def check_explain(cee, problems):
    with open(os.path.join(ROOT, "src", "diagnostics", "catalog.cee"), encoding="utf-8") as f:
        codes = sorted({int(n) for n in re.findall(r"^\s+(\d+) =>", f.read(), re.M)})
    missing = [c for c in codes
               if subprocess.run([cee, "explain", f"N{c:04d}"], capture_output=True).returncode != 0]
    for c in missing:
        problems.append(f"explain: N{c:04d} has no entry in the specification")
    with tempfile.TemporaryDirectory() as work:
        fresh = os.path.join(work, "documents.cee")
        subprocess.run([sys.executable, os.path.join(HERE, "gen_docs.py"), "-o", fresh], check=True,
                       env={**os.environ, "CEESAFEC": cee})
        with open(fresh, "rb") as a, open(os.path.join(ROOT, "src", "library", "documents.cee"), "rb") as b:
            if a.read() != b.read():
                problems.append("explain: src/library/documents.cee is not the tree's documents; run tools/gen_docs.py "
                                "and rebuild")
    return len(codes)


def check_links(problems):
    count = 0
    for path in documents():
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for m in re.finditer(r"\]\(([^)\s]+)\)", text):
            target = m.group(1)
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            count += 1
            if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), target.split("#")[0]))):
                problems.append(f"links: {os.path.relpath(path, ROOT)} links to {target}, which does not exist")
    return count


def check_api(cee, problems):
    with tempfile.TemporaryDirectory() as work:
        core = os.path.join(work, "lib", "core")
        os.makedirs(core)
        for source in sorted(glob.glob(os.path.join(ROOT, "tests", "reference", "lib", "core", "*.cee"))):
            with open(source, "rb") as f, open(os.path.join(core, os.path.basename(source)), "wb") as g:
                g.write(map_forward(f.read()))
        page = subprocess.run([cee, "doc", "lib/core", "--title", "lib/core"], cwd=work, capture_output=True)
    with open(os.path.join(ROOT, "spec", "api", "core.md"), "rb") as f:
        if page.returncode != 0 or page.stdout != f.read():
            problems.append("api: spec/api/core.md is not what `ceesafec doc lib/core` writes")


def check_names(problems):
    count = 0
    for path in documents():
        relative = os.path.relpath(path, ROOT).replace(os.sep, "/")
        if relative.startswith("spec/decisions/"):
            continue  # Nova's records, inherited unchanged (spec/README.md §2)
        with open(path, encoding="utf-8") as f:
            for number, line in enumerate(f, 1):
                bare = URL.sub("", line)
                if NOVA_NAMES.search(bare) and not any(relative == p and text in line for p, text in ALLOWED):
                    count += 1
                    problems.append(f"names: {relative}:{number}: {line.strip()[:120]}")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    args = parser.parse_args()
    cee = os.path.abspath(args.ceesafec)
    problems = []
    codes = check_explain(cee, problems)
    links = check_links(problems)
    check_api(cee, problems)
    check_names(problems)
    for p in problems:
        print("FAIL", p)
    print(f"spec_check: {len(documents())} documents, {codes} codes explained, {links} links, the API page, names: "
          f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
