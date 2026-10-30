// Builds a fixed sequence of types with the reference's TypeTable and prints, for each, its name and properties, in
// the format tests/types/run-pass/type-table.nova expects (tools/oracles/gen_type_cases.py writes that test). The Nova
// side builds the same sequence with src/types/types.nova.
using Nova.Compiler.Semantics;
using Nova.Compiler.Syntax;
using System.Collections.Immutable;

var t = new TypeTable(TargetInfo.Lp64);
var s = new SymbolTable();
Symbol nul = s.Intern("null"), some = s.Intern("Some"), ok = s.Intern("Ok"), err = s.Intern("Err"), payload = s.Intern("_0");
var all = new List<NovaType>();
NovaType Add(NovaType x) { all.Add(x); return x; }

var i32 = Add(t.I32); Add(t.U8); Add(t.USize); Add(t.F64); Add(t.Bool); Add(t.Void); var view = Add(t.StringView);
var ri = Add(t.ReferenceTo(t.I32, false)); var rmi = Add(t.ReferenceTo(t.I32, true)); Add(t.ReferenceTo(ri, true));
Add(t.ArrayOf(t.I32, 4)); Add(t.ArrayOf(t.U8, -1)); Add(t.SliceOf(t.U8, false)); Add(t.SliceOf(t.I64, true));
Add(t.ArrayOf(t.ArrayOf(t.U8, 3), 2)); Add(t.PointerTo(t.U8, false)); Add(t.PointerTo(t.I32, true));
Add(t.PointerTo(t.PointerTo(t.U8, false), true));
var oi = Add(t.OptionOf(t.I32, nul, some, payload)); Add(t.OptionOf(ri, nul, some, payload));
Add(t.ReferenceTo(oi, false)); Add(t.ReferenceTo(oi, true));
Add(t.ResultOf(t.I32, t.Bool, ok, err, payload)); Add(t.ResultOf(t.Void, t.Bool, ok, err, payload));
Add(t.ResultOf(ri, t.Bool, ok, err, payload));
var bx = Add(t.BoxOf(t.I32, t.Arena, true)); Add(t.BoxOf(t.I64, t.Arena, false)); Add(t.PoolBoxOf(t.I32));
Add(t.OptionOf(bx, nul, some, payload)); Add(t.OptionOf(view, nul, some, payload));
Add(t.VectorOf(t.I32, t.Arena, true)); Add(t.VectorOf(null, t.Arena, true)); Add(t.VectorOf(null, t.Arena, false));
Add(t.VectorOf(t.U8, t.Arena, false)); Add(t.VectorOf(ri, t.Arena, true));
Add(t.ContainerOf(TypeKind.StableVector, t.I32, t.Arena, true)); Add(t.ContainerOf(TypeKind.SlotMap, t.I32, t.Arena, false));
Add(t.HandleOf(t.I32)); Add(t.ThreadOf(t.I32)); Add(t.PoolOf(t.U16));
Add(t.FunctionTo([t.I32, t.Bool], t.I32)); Add(t.FunctionTo([], t.Void)); Add(t.FunctionTo([t.I32], t.Bool, Nova.Compiler.Hir.Effects.Sleep));
Add(t.FunctionPointerTo([t.I32], t.U8)); Add(t.ClosureTo([t.I32], t.Bool, Nova.Compiler.Hir.Effects.Alloc));
Add(t.ReferenceTo(t.ClosureTo([t.I32], t.Bool, Nova.Compiler.Hir.Effects.Alloc), true));
Add(t.DynFunctionOf([t.I32], t.Void, Nova.Compiler.Hir.Effects.None, true, true));
Add(t.DynFunctionOf([], t.I64, NovaType.AllEffects, false));
Add(t.ResultOf(t.VectorOf(null, t.Arena, true), t.Bool, ok, err, payload));
Add(t.ArrayOf(t.OptionOf(t.U8, nul, some, payload), 3));

Console.WriteLine($"same reference: {ReferenceEquals(t.ReferenceTo(t.I32, false), ri)}, same option: {ReferenceEquals(t.OptionOf(t.I32, nul, some, payload), oi)}");
for (var k = 0; k < all.Count; k++)
{
    var x = all[k];
    string layout;
    try { var (size, align) = TypeTable.LayoutOf(x); layout = $"{size}/{align}"; } catch (InvalidOperationException) { layout = "-"; }
    string b(bool v) => v ? "1" : "0";
    Console.WriteLine($"{k} {x.Name} | {layout} copy {b(TypeTable.IsCopy(x))} drop {b(TypeTable.NeedsDrop(x))} scoped {b(TypeTable.IsScoped(x))} send {b(TypeTable.IsSend(x))} region {b(TypeTable.HoldsRegionValue(x))} niche {b(TypeTable.IsNicheOptional(x))}");
}
NovaType[] scalars = [t.I8, t.I16, t.I32, t.I64, t.ISize, t.U8, t.U16, t.U32, t.U64, t.USize, t.F32, t.F64, t.Bool];
foreach (var from in scalars)
{
    Console.WriteLine($"lossless {from.Name}: {string.Join("", scalars.Select(to => TypeTable.IsLosslessCast(from, to) ? "1" : "0"))}");
}
