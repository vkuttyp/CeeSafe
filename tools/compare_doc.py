#!/usr/bin/env python3
"""Compares `ceesafec doc` with the pinned novac's (docs/p8-plan.md S2).

Each .nova file of a Nova checkout alone, then lib/core, lib/std and lib/kernel each as one page (lib/core's is
Nova's docs/api/core.md) and CeeSafe's own sources as one: `doc FILES` and `doc --missing FILES` must give the same
exit status, stdout and stderr, and `doc -o page.md --title T FILES` the same page.

usage: python3 tools/compare_doc.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root NOVA_CHECKOUT [--jobs N]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from names import map_back

HERE = os.path.dirname(os.path.abspath(__file__))


def run(compiler, arguments, cwd):
    p = subprocess.run([compiler] + arguments, cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def same(mine, ref):
    return mine == ref or (mine[0], map_back(mine[1]), map_back(mine[2])) == ref


def compare(cee, novac, files, cwd):
    for arguments in (["doc"] + files, ["doc", "--missing"] + files):
        if not same(run(cee, arguments, cwd), run(novac, arguments, cwd)):
            return [f"{' '.join(arguments[:2])} {files[0]}{' …' if len(files) > 1 else ''}: differs"]
    with tempfile.TemporaryDirectory() as work:
        pages = []
        for compiler, name in ((cee, "c.md"), (novac, "n.md")):
            run(compiler, ["doc", "-o", os.path.join(work, name), "--title", "A title"] + files, cwd)
            page = os.path.join(work, name)
            if os.path.exists(page):  # no page after a syntax error
                with open(page, "rb") as f:
                    pages.append(f.read())
            else:
                pages.append(None)
        if pages[0] != pages[1]:
            return [f"doc -o {files[0]}: the page differs"]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    root = os.path.abspath(options.root)
    files = []
    for base, directories, names in os.walk(root):
        directories[:] = sorted(d for d in directories if d not in (".git", "bin", "obj", "node_modules", "out"))
        files += sorted(os.path.relpath(os.path.join(base, n), root) for n in names if n.endswith(".nova"))
    jobs = [([f], root) for f in files]
    for library in ("lib/core", "lib/std", "lib/kernel"):
        jobs.append((sorted(f for f in files if f.startswith(library + "/")), root))
    own_root = os.path.normpath(os.path.join(HERE, ".."))
    own = sorted(subprocess.run(["git", "-C", own_root, "ls-files", "src/*.cee"], capture_output=True, text=True,
                                check=True).stdout.split())
    jobs.append((own, own_root))
    with ThreadPoolExecutor(options.jobs) as pool:
        results = list(pool.map(lambda job: compare(cee, novac, job[0], job[1]), jobs))
    problems = [p for r in results for p in r]
    for p in problems[:50]:
        print("differ:", p)
    print(f"compare_doc: {len(jobs)} pages ({len(files)} single files, 3 libraries, CeeSafe's {len(own)} sources), "
          f"{len(jobs) - len(problems)} identical, {len(problems)} differ")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
