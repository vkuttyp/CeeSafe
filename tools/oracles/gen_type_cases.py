#!/usr/bin/env python3
"""Writes tests/types/run-pass/type-table.nova from the reference's TypeTable (docs/p3-plan.md, S0).

The oracle (tools/oracles/type-table, built against Nova at the pinned tag) builds a fixed sequence of types and prints
each one's name, layout and properties, and a matrix of lossless casts. This script copies that output into the test
as its expected stdout; the test's body builds the same sequence with src/types/types.nova. Edit both sides together.

usage: python3 tools/oracles/gen_type_cases.py ORACLE_BINARY   (then format with the pinned novac; review the diff)
"""

import os
import subprocess
import sys

BODY = r'''
fn yes(b: bool) -> StringView => if (b) "1" else "0";

fn main() {
    var t = TypeTable.create(lp64())!;
    let nul: u32 = 1000;
    let some: u32 = 1001;
    let ok: u32 = 1002;
    let err: u32 = 1003;
    let payload: u32 = 1004;
    var all = Vector<u32>.create();
    let arena = t.arena;
    let i32 = t.i32;
    let i64 = t.i64;
    let u8 = t.u8;
    all.push(i32)!;
    all.push(u8)!;
    all.push(t.usize)!;
    all.push(t.f64)!;
    all.push(t.boolType)!;
    all.push(t.voidType)!;
    let view = t.stringView;
    all.push(view)!;
    let ri = t.referenceTo(i32, false)!;
    all.push(ri)!;
    all.push(t.referenceTo(i32, true)!)!;
    all.push(t.referenceTo(ri, true)!)!;
    all.push(t.arrayOf(i32, 4)!)!;
    all.push(t.arrayOf(u8, -1)!)!;
    all.push(t.sliceOf(u8, false)!)!;
    all.push(t.sliceOf(i64, true)!)!;
    let a3 = t.arrayOf(u8, 3)!;
    all.push(t.arrayOf(a3, 2)!)!;
    all.push(t.pointerTo(u8, false)!)!;
    all.push(t.pointerTo(i32, true)!)!;
    let pu8 = t.pointerTo(u8, false)!;
    all.push(t.pointerTo(pu8, true)!)!;
    let oi = t.optionOf(i32, nul, some, payload)!;
    all.push(oi)!;
    all.push(t.optionOf(ri, nul, some, payload)!)!;
    all.push(t.referenceTo(oi, false)!)!;
    all.push(t.referenceTo(oi, true)!)!;
    let b = t.boolType;
    let v = t.voidType;
    all.push(t.resultOf(i32, b, ok, err, payload)!)!;
    all.push(t.resultOf(v, b, ok, err, payload)!)!;
    all.push(t.resultOf(ri, b, ok, err, payload)!)!;
    let bx = t.boxOf(i32, arena, true)!;
    all.push(bx)!;
    all.push(t.boxOf(i64, arena, false)!)!;
    all.push(t.poolBoxOf(i32)!)!;
    all.push(t.optionOf(bx, nul, some, payload)!)!;
    all.push(t.optionOf(view, nul, some, payload)!)!;
    all.push(t.vectorOf(i32, arena, true)!)!;
    all.push(t.vectorOf(none(), arena, true)!)!;
    all.push(t.vectorOf(none(), arena, false)!)!;
    all.push(t.vectorOf(u8, arena, false)!)!;
    all.push(t.vectorOf(ri, arena, true)!)!;
    all.push(t.containerOf(TypeKind.StableVector, i32, arena, true)!)!;
    all.push(t.containerOf(TypeKind.SlotMap, i32, arena, false)!)!;
    all.push(t.handleOf(i32)!)!;
    all.push(t.threadOf(i32)!)!;
    let u16 = t.u16;
    all.push(t.poolOf(u16)!)!;
    let ib: [u32; 2] = [i32, b];
    all.push(t.functionTo(ib[..], i32, 3)!)!;
    let nothing = Vector<u32>.create();
    all.push(t.functionTo(nothing.view(), v, 3)!)!;
    let just: [u32; 1] = [i32];
    all.push(t.functionTo(just[..], b, 1)!)!;
    all.push(t.functionPointerTo(just[..], u8)!)!;
    let closure = t.closureTo(just[..], b, 2)!;
    all.push(closure)!;
    all.push(t.referenceTo(closure, true)!)!;
    all.push(t.dynFunctionOf(just[..], v, 0, true, true)!)!;
    all.push(t.dynFunctionOf(nothing.view(), i64, 3, false, false)!)!;
    let string = t.vectorOf(none(), arena, true)!;
    all.push(t.resultOf(string, b, ok, err, payload)!)!;
    let ou8 = t.optionOf(u8, nul, some, payload)!;
    all.push(t.arrayOf(ou8, 3)!)!;

    Console.write("same reference: ");
    Console.write(if (t.referenceTo(i32, false)! == ri) "True" else "False");
    Console.write(", same option: ");
    Console.writeLine(if (t.optionOf(i32, nul, some, payload)! == oi) "True" else "False");
    for (k in 0..all.length) {
        let x = all[k];
        var line = Vector<u8>.create();
        appendDecimal(mut line, k as u64)!;
        line.push(' ')!;
        appendBytes(mut line, t.name(x))!;
        appendText(mut line, " | ")!;
        if (t.hasLayout(x)) {
            let l = t.layoutOf(x);
            if (l.size < 0) {
                line.push('-')!;
                appendDecimal(mut line, truncate<u64>(0 - l.size))!;
            } else {
                appendDecimal(mut line, truncate<u64>(l.size))!;
            }
            line.push('/')!;
            appendDecimal(mut line, l.align as u64)!;
        } else {
            line.push('-')!;
        }
        appendText(mut line, " copy ")!;
        appendText(mut line, yes(t.isCopy(x)))!;
        appendText(mut line, " drop ")!;
        appendText(mut line, yes(t.needsDrop(x)))!;
        appendText(mut line, " scoped ")!;
        appendText(mut line, yes(t.isScoped(x)))!;
        appendText(mut line, " send ")!;
        appendText(mut line, yes(t.isSendType(x)!))!;
        appendText(mut line, " region ")!;
        appendText(mut line, yes(t.holdsRegionValue(x)))!;
        appendText(mut line, " niche ")!;
        appendText(mut line, yes(t.isNicheOptional(x)))!;
        line.push('\n')!;
        Console.writeBytes(line.view());
    }
    let scalars: [u32; 13] = [t.i8, t.i16, i32, i64, t.isize, u8, u16, t.u32, t.u64, t.usize, t.f32, t.f64, b];
    for (from in scalars) {
        var line = Vector<u8>.create();
        appendText(mut line, "lossless ")!;
        appendBytes(mut line, t.name(from))!;
        appendText(mut line, ": ")!;
        for (to in scalars) {
            appendText(mut line, yes(t.isLosslessCast(from, to)))!;
        }
        line.push('\n')!;
        Console.writeBytes(line.view());
    }
}
'''


def main():
    oracle = sys.argv[1]
    out = subprocess.run([oracle], capture_output=True, text=True, check=True).stdout
    expect = "\n".join(f"// expect-stdout: {line}" for line in out.rstrip("\n").split("\n"))
    source = ("// src/types/types.nova against the reference's TypeTable. GENERATED by tools/oracles/gen_type_cases.py from\n"
              "// tools/oracles/type-table: edit the generator (both sides), not this file.\n" + expect + "\n" + BODY)
    path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "tests", "types", "run-pass",
                                         "type-table.nova"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(source)
    novac = os.environ.get("NOVAC", os.path.expanduser("~/.nova/0.4.1/bin/novac"))
    subprocess.run([novac, "fmt", path], check=True)
    print(f"wrote {path} ({out.count(chr(10))} expected lines)")


if __name__ == "__main__":
    main()
