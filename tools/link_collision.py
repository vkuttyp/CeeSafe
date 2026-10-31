#!/usr/bin/env python3
"""The link-collision test (Decision 0004): one C program linking a library built by novac and one built by ceesafec.

Each library is a package with an `@export` function that allocates (so its runtime is linked in), compiled from its
emitted C; a C `main` calls both. Since the fork the runtimes and generated names are disjoint (`nova_*`/`nv*` against
`ceesafe_*`/`cee*`), so the program must link and print both results. As a control, two novac-built libraries must not
link: their runtimes define the same symbols, which is what the prefix switch is for.

usage: python3 tools/link_collision.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac [--cc cc]
"""
import argparse
import glob
import os
import subprocess
import sys
import tempfile

LIBRARY = """@export
fn NAME(n: u32) -> u64 {
    var values = Vector<u64>.create();
    for (k in 0..n) {
        values.push(k as u64)!;
    }
    var total: u64 = 0;
    for (x in values.view()) {
        total += x * FACTOR;
    }
    return total;
}
"""

MAIN = """#include <stdio.h>
#include <stdint.h>
uint64_t LEFT(uint32_t n);
uint64_t RIGHT(uint32_t n);
int main(void) {
    printf("%llu %llu\\n", (unsigned long long)LEFT(10), (unsigned long long)RIGHT(10));
    return 0;
}
"""


def library(work, compiler, name, factor, extension, cc):
    """The objects of a library built by `compiler`, exporting `name`."""
    directory = os.path.join(work, name)
    os.makedirs(directory)
    source = os.path.join(directory, "lib" + extension)
    with open(source, "w", encoding="utf-8") as f:
        f.write(LIBRARY.replace("NAME", name).replace("FACTOR", str(factor)))
    c = os.path.join(directory, "c")
    subprocess.run([compiler, "build", "--emit", "c", source, "-o", c], check=True, capture_output=True)
    objects = os.path.join(directory, "o")
    os.makedirs(objects)
    for file in sorted(glob.glob(os.path.join(c, "*.c"))):
        subprocess.run([cc, "-std=c11", "-O2", "-I", c, "-c", file, "-o",
                        os.path.join(objects, os.path.basename(file) + ".o")], check=True, capture_output=True)
    return sorted(glob.glob(os.path.join(objects, "*.o")))


def link(work, cc, left, right, objects, name):
    main = os.path.join(work, name + ".c")
    with open(main, "w", encoding="utf-8") as f:
        f.write(MAIN.replace("LEFT", left).replace("RIGHT", right))
    exe = os.path.join(work, name)
    linked = subprocess.run([cc] + objects + [main, "-o", exe], capture_output=True, text=True)
    return exe if linked.returncode == 0 else None, linked.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    cee, novac = os.path.abspath(args.ceesafec), os.path.expanduser(args.novac)
    problems = []
    with tempfile.TemporaryDirectory() as work:
        nova_left = library(work, novac, "left_sum", 1, ".nova", args.cc)
        cee_right = library(work, cee, "right_double", 2, ".cee", args.cc)
        exe, errors = link(work, args.cc, "left_sum", "right_double", nova_left + cee_right, "mixed")
        if exe is None:
            problems.append(f"novac's and ceesafec's libraries do not link together:\n{errors[:1500]}")
        else:
            out = subprocess.run([exe], capture_output=True, text=True).stdout
            if out != "45 90\n":
                problems.append(f"the mixed program printed {out!r}, not '45 90'")
        nova_right = library(work, novac, "right_triple", 3, ".nova", args.cc)
        exe, errors = link(work, args.cc, "left_sum", "right_triple", nova_left + nova_right, "control")
        if exe is not None:
            problems.append("control: two novac-built libraries linked, so the test would not see a collision")
        elif "duplicate" not in errors and "multiple definition" not in errors:
            problems.append(f"control: the link failed, but not for duplicate symbols:\n{errors[:800]}")
    for p in problems:
        print("FAIL", p)
    print(f"link_collision: a novac-built and a ceesafec-built library in one program, and the novac-novac control: "
          f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
