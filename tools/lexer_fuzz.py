#!/usr/bin/env python3
"""Writes inputs that stress the lexer, for tools/compare_tokens.py (docs/p2-frontend.md §3).

`--cases DIR` writes the fixed edge cases below, one file each (committed as tests/syntax/lexer/, and the known
differences as tests/syntax/lexer-known/). `--random DIR N SEED`
writes N random files built from token fragments, bytes and broken UTF-8; the seed makes a run reproducible.
"""

import argparse
import os
import random

CASES = {
    "bom-one": b"\xef\xbb\xbffn main() {}\n",
    "bom-two": b"\xef\xbb\xbf\xef\xbb\xbffn main() {}\n",
    "bom-three": b"\xef\xbb\xbf\xef\xbb\xbf\xef\xbb\xbffn main() {}\n",
    "bom-inside": b"fn main() {\xef\xbb\xbf}\n",
    "line-ends": b"fn a() {}\r\nfn b() {}\rfn c() {}\n\r\n\n\rx",
    "form-feed": b"fn\x0cmain() {}\x0b\n",
    "nul-and-controls": b"let a = 1;\x00\x01\x1f\x7f\n",
    "ill-formed-utf8": b"let s = \"\xc3\x28 \xa0\xa1 \xe2\x28\xa1 \xf0\x90\x28\xbc \xf8\xa1\xa1\xa1\xa1 \xed\xa0\x80 \xc0\xaf\";\n"
                       b"\xff \xfe \xc3 \xe2\x82 \xf0\x9f\x98\n// \xff comment\n/// doc \xe2\x82 x\nfn f() {}\n",
    "non-ascii-outside": "let é = 1; let x = 1 → 2; 😀 ∑ \u2028 \u00a0;\n".encode(),
    "strings": "let a = \"plain\"; let b = \"tab\\t nl\\n q\\\" bs\\\\ z\\0 u\\u{1F600} é 😀\";\n"
               "let c = \"\\u{} \\u{1234567} \\u{D800} \\u{110000} \\u{41 \\q \\é end\";\n"
               "let d = \"unterminated\nlet e = \"also\r\nlet f = \"eof".encode(),
    "chars": "let a = 'x'; let b = '\\n'; let c = 'é'; let d = '😀'; let e = '\\u{41}';\n"
             "let f = ''; let g = 'ab'; let h = 'abc\nlet i = '\\q'; let j = '\\u{D800}'; let k = '\nlet l = '".encode(),
    "numbers": b"0 1 007 1_000 1__0 _1 1_ 0x 0xg 0xFF_FF 0x_1 0b102 0o78 0o 0b 0b_ 0b1_0\n"
               b"18446744073709551615 18446744073709551616 0xFFFFFFFFFFFFFFFF 0x10000000000000000\n"
               b"1.5 1. .5 1.5e3 1e3 1e+3 1e-3 1e 1e+ 1.e3 1.5e3f32 2f64 2.0f32 1.5u8 1u8 1i64 1usize 1isize 1u7 1xyz\n"
               b"1_000.5_0 1.5_ 1._5 1e_3 0x1.5 0b1.0 1..2 1...2 3.foo 0x1e3 1E3 1E-3_0\n",
    "punctuation": b"( ) { } [ ] , ; : @ ? ~ . .. ... -> => + - * / % ^ ! & | && || << >> >>= <<= <= >= == != = "
                   b"+= -= *= /= %= ^= &= |= ->= =>= !== &&= ||= # $ ` \\\n",
    "comments": b"// line\n/// doc one\n///   doc two\t\n//// not doc\n///\nfn a() {}\n/// orphan\n/* block */ /** blk */\n"
                b"/// before block\n/* x */ fn b() {}\n/// last\n/* unterminated\nfn c() {}",
    "comment-eof": b"fn a() {} //",
    "block-eof": b"/*",
    "block-star": b"/*/ fn x() {} */ /**/ /***/",
    "doc-crlf": b"/// one\r\n/// two\r\nfn a() {}\r\n",
    "keywords": b"as async await borrow break class const continue defer drop else enum extern false fn for if impl import in "
                b"interface internal let loop macro match move mut namespace null own private public return Self static struct "
                b"this true type unsafe using var where while yield _ __ _a a_ Self_ self SELF asx x9 9x\n",
    "empty": b"",
    "only-space": b" \t\r\n",
}

# Inputs where the reference and ceesafec are known to differ (docs/p2-frontend.md §2), kept apart so the cases above
# must match exactly.
KNOWN = {
    # The span of an invalid escape of a character above the BMP ends inside its surrogate pair in the reference.
    "escape-astral": "let s = \"a\\😀b\"; let c = '\\😀';\n".encode(),
}

FRAGMENTS = [
    "fn", "let", "var", "x", "_", "Self", "match", "=>", "->", "::", "..", ".", "<", ">", ">=", "<<=", "(", ")", "{", "}",
    "[", "]", ";", ",", "'", "\"", "\\", "\\u{", "}", "0x", "0b", "0o", "1_", "_0", "1.5", "e", "e+", "f32", "u8",
    "//", "///", "/*", "*/", "\n", "\r", "\r\n", " ", "\t", "\x0c", "é", "😀", "\u2028", "\ufeff", "#", "$", "@", "?",
    "9" * 25, "'a'", "'\\n'", "\"s\"", "\"\\t\"",
]

BYTES = [b"\xff", b"\xc3", b"\xe2\x82", b"\xf0\x9f\x98", b"\xed\xa0\x80", b"\xc0\xaf", b"\x00", b"\x80", b"\xef\xbb\xbf"]


def random_file(rng):
    parts = []
    for _ in range(rng.randint(0, 120)):
        r = rng.random()
        if r < 0.75:
            parts.append(rng.choice(FRAGMENTS).encode())
        elif r < 0.9:
            parts.append(rng.choice(BYTES))
        else:
            parts.append(bytes(rng.randrange(256) for _ in range(rng.randint(1, 4))))
    # A backslash before a character above the BMP is a known difference (KNOWN); keep the two apart.
    return b"".join(parts).replace(b"\\\xf0", b"\\ \xf0")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases")
    parser.add_argument("--random", nargs=3, metavar=("DIR", "N", "SEED"))
    args = parser.parse_args()
    if args.cases:
        os.makedirs(args.cases, exist_ok=True)
        for name, data in CASES.items():
            with open(os.path.join(args.cases, name + ".nova"), "wb") as f:
                f.write(data)
        known = args.cases.rstrip("/") + "-known"
        os.makedirs(known, exist_ok=True)
        for name, data in KNOWN.items():
            with open(os.path.join(known, name + ".nova"), "wb") as f:
                f.write(data)
        print(f"lexer_fuzz: wrote {len(CASES)} cases to {args.cases}, {len(KNOWN)} to {known}")
    if args.random:
        directory, n, seed = args.random[0], int(args.random[1]), int(args.random[2])
        os.makedirs(directory, exist_ok=True)
        rng = random.Random(seed)
        for i in range(n):
            with open(os.path.join(directory, f"r{i:05}.nova"), "wb") as f:
                f.write(random_file(rng))
        print(f"lexer_fuzz: wrote {n} random files (seed {seed}) to {directory}")


if __name__ == "__main__":
    main()
