#!/bin/sh
# Builds ceesafec from a checkout with only the pinned novac (Decision 0002 §3): novac cannot read CeeSafe's names, so
# it builds the last commit with Nova's names (ANCHOR), and the ceesafec that makes builds the tree at REVISION.
#
# usage: tools/bootstrap.sh [NOVAC] [REVISION] [OUTPUT]
#        defaults: ~/.nova/0.6.0/bin/novac, HEAD, out/ceesafec
set -eu

ANCHOR=3d6ac40 # the last legacy-named commit (bootstrap/reference.md)
NOVAC=${1:-$HOME/.nova/0.6.0/bin/novac}
REVISION=${2:-HEAD}
OUTPUT=${3:-out/ceesafec}

repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

mkdir -p "$work/anchor" "$work/tree"
git -C "$repo" archive "$ANCHOR" nova.toml src | tar -x -C "$work/anchor"
(cd "$work/anchor" && "$NOVAC" build -o "$work/stage0")
git -C "$repo" archive "$REVISION" ceesafe.toml src | tar -x -C "$work/tree"
(cd "$work/tree" && "$work/stage0" build -o "$work/ceesafec")
mkdir -p "$(dirname "$OUTPUT")"
cp "$work/ceesafec" "$OUTPUT"
"$OUTPUT" --version
