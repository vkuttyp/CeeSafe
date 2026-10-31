"""The rename contract between CeeSafe's names and Nova's (ROADMAP §3.4; Decisions 0002, 0004, 0005).

Since the fork point (docs/fork-point.md), novac 0.6.0's output is the frozen baseline: what ceesafec prints, with
CeeSafe's names mapped back to Nova's, must equal it byte for byte. `map_back` does that; `map_forward` is its inverse,
for the generators that take Nova's sources (the runtime, the libraries, the catalog, the agent template) and for
CeeSafe's copy of the corpus. Both apply one list of rules in order, the more specific first.

The rules cover the C names (Decision 0004: `nv`→`cee` at the start of a name (an identifier, or a part after `_`) before a capital or `_`,
`nova_`→`ceesafe_`, `NV_`→`CEE_`, `NOVA_`→`CEESAFE_`, `nova/rt.h`→`ceesafe/rt.h`), the compiler, the file extension and
the prose (`Nova`→`CeeSafe`). The ABI version lines ceesafec adds have no counterpart in novac's C and are dropped.

A mapping hides a missed rename, so `nova_names_in` finds Nova's C names left in ceesafec's raw C.
"""
import os
import re

# (CeeSafe's form, Nova's form, Nova's form, CeeSafe's form) as regular expressions over bytes and replacements:
# backward replaces the first by the second, forward the third by the fourth.
RULES = (
    (rb"https://github\.com/vkuttyp/CeeSafe-index", b"https://github.com/vkuttyp/nova-index",
     rb"https://github\.com/vkuttyp/nova-index", b"https://github.com/vkuttyp/CeeSafe-index"),
    (rb"(?<![A-Za-z_])ceesafec\b", b"novac", rb"(?<![A-Za-z_])novac\b", b"ceesafec"),
    (rb"\.cee\b", b".nova", rb"\.nova\b", b".cee"),
    (rb"ceesafe/", b"nova/", rb"nova/", b"ceesafe/"),
    (rb"CEESAFE_", b"NOVA_", rb"NOVA_", b"CEESAFE_"),
    (rb"ceesafe_", b"nova_", rb"nova_", b"ceesafe_"),
    (rb"(?<![A-Za-z0-9])CEE_", b"NV_", rb"(?<![A-Za-z0-9])NV_", b"CEE_"),
    (rb"(?<![A-Za-z0-9])cee(?=[A-Z_])", b"nv", rb"(?<![A-Za-z0-9])nv(?=[A-Z_])", b"cee"),
    (rb"CeeSafe", b"Nova", rb"Nova", b"CeeSafe"),
    (rb"(?<![A-Za-z_])CEESAFE\b", b"NOVA", rb"(?<![A-Za-z_])NOVA\b", b"CEESAFE"),
    (rb"(?<![A-Za-z_])ceesafe\b", b"nova", rb"(?<![A-Za-z_])nova\b", b"ceesafe"),
)

# Words (the compiler, the language's name in lower case) start after anything but a letter or `_`: `\u0060ceesafe`
# (a code fence in strict JSON) is the word `ceesafe`.

# The ABI version (Decision 0004): defined in ceesafe/rt.h, checked by every generated unit.
ABI_DEFINE = b"#define CEESAFE_ABI_VERSION 1\n"
ABI_CHECK = b'#if CEESAFE_ABI_VERSION != 1\n#error "this C was generated for CeeSafe\'s runtime ABI version 1"\n#endif\n'

def _json_escaped(text, levels):
    import json
    for _ in range(levels):
        text = json.dumps(text.decode("utf-8"), ensure_ascii=False)[1:-1].encode("utf-8")
    return text


# The ABI check as it appears in C embedded in JSON once (MCP's structuredContent) or twice (its text content).
_ABI_ESCAPED = (_json_escaped(ABI_CHECK, 2), _json_escaped(ABI_CHECK, 1))

_BACK = [(re.compile(cee), nova) for cee, nova, _, _ in RULES]
_FORWARD = [(re.compile(nova), cee) for _, _, nova, cee in RULES]
_MAIN_LINE = re.compile(rb'(#line )(\d+)( "main\.c")')
_C_LINE = re.compile(rb'(#line )(\d+)( "[^"\n]*\.[ch]")')
_C_STRING = re.compile(rb'"(?:[^"\\\n]|\\.)*"')
_NOVA_C_NAMES = re.compile(rb"(?<![A-Za-z0-9])nv(?=[A-Z_])|nova_|(?<![A-Za-z0-9])NV_|NOVA_|nova/rt\.h")


def map_back(output):
    """ceesafec's output with Nova's names, to compare with novac's."""
    if isinstance(output, str):
        return map_back(output.encode("utf-8")).decode("utf-8")
    at = output.find(ABI_CHECK)
    if at >= 0:
        # The check's three lines move what follows them in this file: `#line N "main.c"` (the -g form's way back to
        # the generated file) points three lines lower than novac's.
        first = output.count(b"\n", 0, at) + 1
        rest = _C_LINE.sub(lambda m: m.group(1) + str(int(m.group(2)) - 3).encode() + m.group(3)
                           if int(m.group(2)) > first else m.group(0), output[at + len(ABI_CHECK):])
        output = output[:at] + rest
    elif b'#include "ceesafe_program.h"' in output:
        # A unit of the split form: its `#line N "main.c"` lines point into the unsplit main.c, past its check.
        output = _MAIN_LINE.sub(lambda m: m.group(1) + str(int(m.group(2)) - 3).encode() + m.group(3)
                                if int(m.group(2)) > 4 else m.group(0), output)
    for escaped in _ABI_ESCAPED:
        output = output.replace(escaped, b"")
    output = output.replace(ABI_DEFINE, b"")
    for pattern, replacement in _BACK:
        output = pattern.sub(replacement, output)
    return output


def map_forward(text):
    """Nova's text with CeeSafe's names (the inverse of map_back, the ABI lines aside)."""
    if isinstance(text, str):
        return map_forward(text.encode("utf-8")).decode("utf-8")
    for pattern, replacement in _FORWARD:
        text = pattern.sub(replacement, text)
    return text


def nova_names_in(c_text):
    """The Nova C names in ceesafec's C outside string literals (none should be left since the fork): each line, distinct,
    sorted."""
    if isinstance(c_text, str):
        c_text = c_text.encode("utf-8")
    # String literals hold the program's own text (CeeSafe's embeds Nova's documents), not C names.
    c_text = _C_STRING.sub(b'""', c_text)
    found = set()
    for m in _NOVA_C_NAMES.finditer(c_text):
        start = c_text.rfind(b"\n", 0, m.start()) + 1
        found.add(c_text[start:c_text.find(b"\n", m.end()) if b"\n" in c_text[m.end():] else len(c_text)][:120]
                  .decode("utf-8", "replace"))
    return sorted(found)


# The corpus files whose point changed at the fork, and which are checked only against their own annotations, not
# compared with novac: they test that the runtime's C names are reserved (N0292), and CeeSafe reserves its own
# (`ceesafe_`, `cee_`, `CEE_`, `cee` and a capital) where Nova reserves `nova_`, `nv_`, `NV_` and `nv` and a capital.
FORK_DIVERGENCES = ("tests/corpus/check-fail/c-arrays.nova", "tests/corpus/check-fail/ffi-declarations.nova",
                    "tests/corpus/check-fail/imported-c-types.nova")

# CeeSafe's copy of the corpus (tools/fork_corpus.py), laid out as the Nova checkout is.
REFERENCE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "reference"))


def cee_path(path):
    """A Nova checkout's relative path to a `.nova` file as CeeSafe's copy names it."""
    return path[:-len(".nova")] + ".cee" if path.endswith(".nova") else path


def is_ceesafec(compiler):
    """Whether `compiler` is a ceesafec (by its file name; novac otherwise)."""
    return "ceesafe" in os.path.basename(compiler)


class Dialect:
    """What a compiler's programs and files are called: Nova's or, for ceesafec since the fork, CeeSafe's."""

    def __init__(self, cee):
        self.cee = cee
        self.ext = ".cee" if cee else ".nova"
        self.panic = "ceesafe panic: " if cee else "nova panic: "
        self.alloc = "ceesafe alloc: " if cee else "nova alloc: "
        self.alloc_report = "CEESAFE_ALLOC_REPORT" if cee else "NOVA_ALLOC_REPORT"
        self.fail_alloc_at = "CEESAFE_FAIL_ALLOC_AT" if cee else "NOVA_FAIL_ALLOC_AT"
        self.exports = "ceesafe_exports.h" if cee else "nova_exports.h"
        self.runtime_prefix = "ceesafe_rt_" if cee else "nova_rt_"

    def c(self, name):
        """A C name of Nova's runtime or generated code (`nova_alloc`) as this compiler spells it."""
        return map_forward(name) if self.cee else name

    def source(self, path):
        """A `.nova` path as this compiler's corpus names it."""
        return cee_path(path) if self.cee else path


def dialect(compiler):
    return Dialect(is_ceesafec(compiler))


def for_compiler(compiler, root, argv):
    """Where to run `compiler`, and with which arguments, on the Nova checkout `root`'s files: novac in the checkout;
    ceesafec in CeeSafe's copy (tests/reference), on the `.cee` names, any path into the checkout made one into the
    copy. Arguments that name nothing of the checkout's run as they are, in `root`."""
    if not is_ceesafec(compiler) or not any(a.endswith(".nova") or os.path.abspath(root) in a for a in argv):
        return root, argv  # novac, or nothing of the checkout's
    root = os.path.abspath(root)
    # The checkout itself, or its corpus directory (the run tools work there).
    target = os.path.join(REFERENCE, "tests", "corpus") if root.endswith(os.path.join("tests", "corpus")) else REFERENCE
    sources = [a for a in argv if a.endswith(".nova") and not os.path.isabs(a)]
    if sources and not os.path.exists(os.path.join(target, cee_path(sources[0]))):
        # Not the checkout's files (a tool's own, in its own directory): the caller wrote a `.cee` beside each.
        return root, [cee_path(a) for a in argv]
    out = []
    for a in argv:
        if root in a:
            a = a.replace(root, target)
        if a.endswith(".nova"):
            a = cee_path(a)
        out.append(a)
    return target, out


def output_of(compiler, data):
    """A compiler's output to compare: ceesafec's with Nova's names (map_back), novac's as it is."""
    return map_back(data) if is_ceesafec(compiler) else data


def compared_files(root, paths):
    """`paths` without the FORK_DIVERGENCES (relative to `root`, the Nova checkout)."""
    return [p for p in paths if os.path.relpath(os.path.join(root, p), root).replace(os.sep, "/") not in FORK_DIVERGENCES]
