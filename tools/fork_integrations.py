#!/usr/bin/env python3
"""Writes integrations/cosmoos/ at the fork (Decision 0006's companion): Nova's CosmoOS checks from v0.6.0.

Run once. After that the directory is CeeSafe's, edited by hand (the scripts were then adapted to ceesafec), and
this tool refuses to overwrite it. It is kept as the record of what the first text was.

- `.nova` programs become `.cee` files under CeeSafe's names (tools/names.py's forward map), as do the C harnesses
  and headers, which meet ceesafec's C, and the Python scripts;
- the proposal patch (a change to CosmoOS's own tree) is copied as it is.

usage: python3 tools/fork_integrations.py --nova NOVA_CHECKOUT_AT_v0.6.0
"""
import argparse
import os
import subprocess
import sys

from names import map_forward

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TAG = "v0.6.0"
TOP = "integrations/cosmoos"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--nova", required=True)
    args = parser.parse_args()
    nova = os.path.abspath(args.nova)
    if os.path.exists(os.path.join(ROOT, TOP)):
        sys.exit(f"fork_integrations: {TOP}/ exists; it is CeeSafe's since the fork")
    listing = subprocess.run(["git", "-C", nova, "ls-tree", "-r", "--name-only", TAG, TOP], capture_output=True,
                             check=True, text=True).stdout.split()
    counts = {}
    for path in listing:
        data = subprocess.run(["git", "-C", nova, "show", f"{TAG}:{path}"], capture_output=True, check=True).stdout
        target = path
        if path.endswith(".patch"):
            kind = "copied"
        else:
            data = map_forward(data)
            target = map_forward(path)
            kind = "renamed"
        full = os.path.join(ROOT, target)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
        if path.endswith(".py"):
            os.chmod(full, 0o755)
        counts[kind] = counts.get(kind, 0) + 1
    print(f"fork_integrations: {', '.join(f'{n} {k}' for k, n in sorted(counts.items()))} from Nova {TAG} into {TOP}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
