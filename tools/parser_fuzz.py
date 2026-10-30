#!/usr/bin/env python3
"""Writes broken variants of real Nova files, to drive the parser's error recovery (docs/p2-frontend.md §6).

Each variant takes one source file and applies 1-4 mutations: delete a span of bytes, delete or duplicate a line,
insert a token fragment, swap two lines, or cut the file short. The seed makes a run reproducible.

usage: tools/parser_fuzz.py OUT_DIR N SEED SOURCE_FILE...
"""

import os
import random
import sys

FRAGMENTS = [
    b"fn", b"let", b"var", b"{", b"}", b"(", b")", b"[", b"]", b";", b",", b":", b".", b"..", b"=>", b"->", b"<", b">",
    b">>", b">=", b"=", b"==", b"?", b"!", b"&&", b"||", b"if", b"else", b"match", b"while", b"for", b"in", b"return",
    b"struct", b"enum", b"impl", b"interface", b"extern \"C\"", b"@", b"@effects()", b"borrow", b"mut", b"move", b"_",
    b"x", b"Self", b"this", b"static", b"0", b"1.5", b"\"s\"", b"'c'", b"null", b"as", b"unsafe", b"defer", b"using",
    b"import", b"namespace", b"region", b"dyn", b"public", b"drop", b"type", b"class",
]


def mutate(rng, data):
    for _ in range(rng.randint(1, 4)):
        lines = data.split(b"\n")
        r = rng.random()
        if r < 0.25 and data:
            a = rng.randrange(len(data))
            data = data[:a] + data[a + rng.randint(1, 12):]
        elif r < 0.4 and len(lines) > 1:
            del lines[rng.randrange(len(lines))]
            data = b"\n".join(lines)
        elif r < 0.55 and lines:
            k = rng.randrange(len(lines))
            lines.insert(k, lines[k])
            data = b"\n".join(lines)
        elif r < 0.8:
            a = rng.randrange(len(data) + 1)
            data = data[:a] + b" " + rng.choice(FRAGMENTS) + b" " + data[a:]
        elif r < 0.9 and len(lines) > 1:
            i, j = rng.randrange(len(lines)), rng.randrange(len(lines))
            lines[i], lines[j] = lines[j], lines[i]
            data = b"\n".join(lines)
        elif data:
            data = data[:rng.randrange(len(data))]
    return data


def main():
    out, n, seed, sources = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
    os.makedirs(out, exist_ok=True)
    rng = random.Random(seed)
    texts = []
    for path in sorted(sources):
        with open(path, "rb") as f:
            texts.append(f.read())
    for i in range(n):
        with open(os.path.join(out, f"m{i:05}.nova"), "wb") as f:
            f.write(mutate(rng, rng.choice(texts)))
    print(f"parser_fuzz: wrote {n} variants (seed {seed}) of {len(texts)} files to {out}")


if __name__ == "__main__":
    main()
