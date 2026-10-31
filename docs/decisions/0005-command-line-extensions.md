# Decision 0005 — Which files the command line reads

- Status: **Proposed** at P8 S6 (2026-10-31), for the owner to accept.
- Relates to: Decision 0003 §2 ("Whether ceesafec later accepts only `.cee` files is P8's to decide, with the command
  line"), Decision 0004 (the C prefix switches at the fork point), `docs/p8-plan.md` S6 and S7.

## Context

Package mode reads only `ceesafe.toml` packages and their `*.cee` sources (Decision 0003 §1). Files named on the
command line are read whatever their extension, and `.c` files go to the C compiler, as with novac.

Every comparison with novac depends on that. The tools hand both compilers the same files: Nova's corpus (545 `.nova`
files at `v0.6.0`), its benchmarks and programs, the reference's test programs. Most of the 32 contract steps (all but
the self-build and package steps) read `.nova` files through ceesafec's command line, and S0–S5 added the CLI, fmt,
doc, interpreter and server comparisons on the same footing. Copying the corpus to `.cee` names would work for most
steps, but the diagnostics, dumps, C (`#line`, `-g`) and server transcripts all name the file, so every comparison
would need one more mapping on top of `tools/names.py`'s, which maps ceesafec's own `.cee` back to `.nova`.

## Options

1. **Only `.cee` (and `.c`) now.** A clean surface at once; every comparison tool copies inputs to `.cee` names and
   maps the names back. Work across the tools, for no change to what users see before the fork point.
2. **Any extension until the fork point, then only `.cee` and `.c`.** Nothing changes while novac is the reference.
   At S7, when the comparisons become regression tests against the fork point's output and CeeSafe takes its own
   corpus (Decision 0003 §3), ceesafec refuses other files with a usage error naming the extension, and the corpus is
   renamed once.
3. **Any extension, always.** No rule to keep; but a `.nova` file on the command line then looks like Nova support,
   which Decision 0003 rules out.

## Recommendation

Option 2: keep reading any named file until the fork point, and make `.cee`/`.c` the rule in S7's commit that switches
the C prefix, with the corpus renamed in the same slice. The message would be the usage error
`ceesafec: '<file>' is not a .cee or .c file` (exit status 2).

## Consequences

- S6 changes nothing on the command line; S7 gains this item beside the prefix switch.
- Until then, the help text keeps saying `<file.cee>`, which is what CeeSafe's users should write.
