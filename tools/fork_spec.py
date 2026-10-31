#!/usr/bin/env python3
"""Writes CeeSafe's specification at the fork (Decision 0006): spec/, guide/ and templates/AGENTS.md from Nova v0.6.0.

Run once. After that the documents are CeeSafe's, edited by hand, and this tool refuses to overwrite them. It is kept
as the record of what the first text was.

- Nova's normative documents become `spec/` (docs/cosmoos/profiles.md becomes spec/profiles.md, docs/api/ becomes
  spec/api/), the guide (site/guide/) becomes `guide/`, and the agent template stays templates/AGENTS.md. Their text
  is renamed by tools/names.py's forward map, with URLs kept as they are, so code blocks and the guide's check
  directives become `ceesafe` (`<!-- ceesafe: fail N0241 -->`).
- Nova's ADRs become `spec/decisions/` with their text unchanged (a historical record) under a header that says so.
- Links and repository paths are rewritten to the new places. A link to a document CeeSafe did not fork (milestones,
  reports, research, the roadmap) goes to Nova's repository at the tag. The guide's site links (`./basics`,
  `/reference/type-system`) become links to the files.

usage: python3 tools/fork_spec.py --nova NOVA_CHECKOUT_AT_v0.6.0
"""
import argparse
import os
import posixpath
import re
import subprocess
import sys

from names import map_forward

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TAG = "v0.6.0"
NOVA_URL = f"https://github.com/vkuttyp/Nova/blob/{TAG}/"

SPEC = ("architecture", "c-backend", "diagnostics", "formatting", "grammar", "intermediate-representation",
        "language-spec", "lifetimes", "memory-model", "optimisations", "ownership", "testing", "tooling",
        "type-system", "unsafe")

HEADER = """
> **Inherited from Nova.** This is Nova's ADR {number}, which CeeSafe inherited at the fork (Nova `{tag}`; CeeSafe's
> Decision 0006). Its text is Nova's record and is not changed: read Nova and `novac` as the language and compiler
> CeeSafe forked from, `.nova` as `.cee`, and Nova's C names as CeeSafe's (`spec/c-backend.md`). Links to documents
> CeeSafe did not fork go to Nova's repository.
"""

LINK = re.compile(r"(\]\()([^)\s]+)(\))")
URL = re.compile(r"https?://[^\s)>`\"']+")


def target_of(nova_path):
    """CeeSafe's path for a Nova document, or None when it is not forked."""
    if nova_path.startswith("docs/") and nova_path.count("/") == 1 and nova_path[5:-3] in SPEC:
        return "spec/" + nova_path[5:]
    if nova_path == "docs/cosmoos/profiles.md":
        return "spec/profiles.md"
    if nova_path.startswith(("docs/api/", "docs/decisions/")) and nova_path.endswith(".md"):
        return "spec/" + nova_path[5:]
    if nova_path.startswith("site/guide/") and nova_path.endswith(".md"):
        return nova_path[5:]
    if nova_path == "templates/AGENTS.md":
        return nova_path
    return None


def site_path(link):
    """The repository path a VitePress link names (`/reference/x` is docs/x.md, `/guide/x` site/guide/x.md)."""
    if link.startswith("/reference/"):
        rest = link[len("/reference/"):]
        return "docs/" + (rest if rest.endswith(".md") else rest + ".md")
    if link.startswith("/guide/"):
        rest = link[len("/guide/"):]
        return "site/guide/" + ((rest or "index") if rest.endswith(".md") else (rest + "index.md" if rest.endswith("/")
                                                                                 or not rest else rest + ".md"))
    return None


def rewrite_link(link, source, guide):
    if re.match(r"[a-z]+:", link) or link.startswith("#"):
        return link
    path, _, anchor = link.partition("#")
    if guide and path.startswith("/"):
        nova = site_path(path)
    elif guide and not path.endswith((".md", "/")) and "." not in posixpath.basename(path):
        nova = posixpath.normpath(posixpath.join(posixpath.dirname(source), path + ".md"))
    elif guide and path.endswith("/"):
        nova = posixpath.normpath(posixpath.join(posixpath.dirname(source), path, "index.md"))
    else:
        nova = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if nova is None:
        return link
    new = target_of(nova)
    suffix = ("#" + anchor) if anchor else ""
    if new is None:
        return NOVA_URL + nova + suffix
    return posixpath.relpath(new, posixpath.dirname(target_of(source))) + suffix


PATHS = ((re.compile(r"docs/cosmoos/profiles\.md"), "spec/profiles.md"),
         (re.compile(r"(?<![A-Za-z0-9_/.-])(\.\./)?cosmoos/profiles\.md"), "profiles.md"),
         (re.compile(r"(?<![A-Za-z0-9_/.-])docs/(api|decisions)/"), r"spec/\1/"),
         (re.compile(r"(?<![A-Za-z0-9_/.-])docs/(" + "|".join(SPEC) + r")\.md"), r"spec/\1.md"),
         (re.compile(r"(?<![A-Za-z0-9_/.-])site/guide/"), "guide/"))


def convert(text, source, rename):
    """The document's text at its new place: links and URLs held out, renamed if `rename`, paths rewritten."""
    held = []

    def hold(value):
        held.append(value)
        return f"\x00{len(held) - 1}\x00"

    guide = source.startswith("site/guide/")
    text = LINK.sub(lambda m: m.group(1) + hold(rewrite_link(m.group(2), source, guide)) + m.group(3), text)
    text = URL.sub(lambda m: hold(m.group(0)), text)
    if rename:
        text = map_forward(text)
    for pattern, replacement in PATHS:
        text = pattern.sub(replacement, text)
    return re.sub("\x00(\\d+)\x00", lambda m: held[int(m.group(1))], text)


def listed(nova, directory):
    out = subprocess.run(["git", "-C", nova, "ls-tree", "--name-only", f"{TAG}:{directory}"], capture_output=True,
                         check=True, text=True).stdout
    return [f"{directory}/{n}" for n in out.splitlines() if n.endswith(".md")]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nova", required=True)
    args = parser.parse_args()
    nova = os.path.abspath(args.nova)
    tag = subprocess.run(["git", "-C", nova, "describe", "--tags"], capture_output=True, text=True).stdout.strip()
    if tag != TAG:
        sys.exit(f"fork_spec: {nova} must be a checkout of {TAG} (it is {tag or 'untagged'})")
    for existing in ("spec", "guide", "templates"):
        if os.path.exists(os.path.join(ROOT, existing)):
            sys.exit(f"fork_spec: {existing}/ exists; the specification is CeeSafe's since the fork (Decision 0006)")
    sources = [f"docs/{name}.md" for name in SPEC] + ["docs/cosmoos/profiles.md", "templates/AGENTS.md"]
    sources += listed(nova, "docs/api") + listed(nova, "docs/decisions")
    sources += listed(nova, "site/guide") + listed(nova, "site/guide/coming-from")
    counts = {}
    for source in sorted(sources):
        text = subprocess.run(["git", "-C", nova, "show", f"{TAG}:{source}"], capture_output=True,
                              check=True).stdout.decode("utf-8")
        decision = source.startswith("docs/decisions/")
        if source == "templates/AGENTS.md":
            text = map_forward(text)  # as tools/gen_docs.py wrote it at S7, URLs included
        else:
            text = convert(text, source, rename=not decision)
        if decision:
            title_end = text.index("\n") + 1
            number = os.path.basename(source)[:4]
            text = text[:title_end] + HEADER.format(number=number, tag=TAG) + text[title_end:]
        target = target_of(source)
        full = os.path.join(ROOT, target)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        top = target.split("/")[0] + ("/decisions" if decision else "")
        counts[top] = counts.get(top, 0) + 1
    print("fork_spec: " + ", ".join(f"{n} into {d}/" for d, n in sorted(counts.items())) + f" from Nova {TAG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
