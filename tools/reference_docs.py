#!/usr/bin/env python3
"""Builds a ceesafec that embeds novac 0.6.0's documents instead of CeeSafe's (Decision 0006).

Since CeeSafe has its own specification, `explain` and the MCP server serve different text from novac's, so their
output can no longer be compared with novac's directly. The algorithms that find a code's row, split documents into
sections, rank them for a search and serve them as resources are unchanged, and this build checks that: it is the
tree's compiler with src/library/documents.cee written by `tools/gen_docs.py --reference`, and the CLI and server
comparisons (tools/compare_cli.py, tools/compare_servers.py) run it against novac. The shipped ceesafec is checked
against its own specification by tools/spec_check.py.

usage: python3 tools/reference_docs.py --ceesafec out/ceesafec --nova NOVA_CHECKOUT [-o out/ceesafec-refdocs]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))


def build(ceesafec, nova, out):
    with tempfile.TemporaryDirectory() as work:
        shutil.copy(os.path.join(ROOT, "ceesafe.toml"), work)
        shutil.copytree(os.path.join(ROOT, "src"), os.path.join(work, "src"))
        documents = os.path.join(work, "src", "library", "documents.cee")
        subprocess.run([sys.executable, os.path.join(HERE, "gen_docs.py"), "--reference", "--nova", nova, "-o",
                        documents], check=True, env={**os.environ, "CEESAFEC": ceesafec})
        built = subprocess.run([ceesafec, "build", "-o", out], cwd=work, capture_output=True, text=True)
        if built.returncode != 0:
            sys.exit(f"reference_docs: the build failed:\n{built.stderr}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--nova", required=True)
    parser.add_argument("-o", dest="out", default=os.path.join(ROOT, "out", "ceesafec-refdocs"))
    args = parser.parse_args()
    out = build(os.path.abspath(args.ceesafec), os.path.abspath(args.nova), os.path.abspath(args.out))
    print(f"reference_docs: {out} (ceesafec with novac 0.6.0's documents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
