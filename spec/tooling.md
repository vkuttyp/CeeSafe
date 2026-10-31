# Tooling (M10)

The commands of `ceesafec` beside `build`, `check` and `run`. The formatter has its own document (`formatting.md`).

## 1. Documentation generator (T2)

```sh
ceesafec doc file.cee...                 # Markdown for the files' public items, on standard output
ceesafec doc lib/core -o spec/api/core.md --title "lib/core"
ceesafec doc --missing file.cee...       # list the public items without a doc comment; exit 1 if there are any
```

The files are one package, as for `check` (a directory means every `.cee` file under it, in ordinal path order).
`lib/core` is documented only when it is named. A file with a syntax error stops the command: its diagnostics are
printed and nothing is written. The package does not have to type-check: documentation is made from the syntax, so it
can be written for code that does not build yet.

### 1.1 What is documented

- Every item declared `public`: a function, a constant, a struct, an enum, an interface, and a function in an
  `extern "C"` block.
- Inside a public struct: its `public` fields, its `public` methods, and whether it has a `drop` block. Inside a public
  enum: every variant. Inside a public interface: every method.
- An `impl I for T` block, listed under `T` as "Implements `I`" when `T` is a public struct or enum of the package.

Nothing else is listed. Items in a `namespace` are listed under their simple names, as the language names them today
(type-system.md §1).

### 1.2 The page

The output is deterministic: the same files give the same bytes.
- A title (`--title`, or the first file's name without its extension) as a level-1 heading, then a list of the
  documented items, each a link to its section.
- One level-2 section per item, in the order of the files as given and of the items in each file. Its heading is the
  item's kind and name (`struct Volatile`, `fn sortBy`).
- The item's **signature** in a `ceesafe` code block: the item's attributes and its declaration up to its body (the
  `{ … }` or `=> …` of a function, the members of a struct), as `ceesafec fmt` prints them (formatting.md). A struct's
  block lists its public fields; an enum's, its variants; an interface's, its methods.
- The item's **doc comment** (grammar.md §1.2): its lines as written, which are Markdown. An item without one has
  only its signature.
- A struct's public methods follow as level-3 sections (`StructName.method`), each with its signature and doc
  comment; then "Implements `I`" for each `impl`.

### 1.3 Missing documentation

`--missing` writes nothing but a line per public item without a doc comment, `path:line: kind name`, and exits 1 if
there is any. It is a lint for a package's public surface; nothing requires it to pass.

### 1.4 In the repository

`spec/api/core.md` is generated from `lib/core` with `ceesafec doc lib/core -o spec/api/core.md --title "lib/core"`, run
on the embedded `lib/core` (its sources under CeeSafe's names). `tools/spec_check.py` fails if it is out of date
(Nova's `DocTests`).

## 2. Language server (T3)

```sh
ceesafec lsp        # a Language Server Protocol server on standard input and output
```

The server speaks LSP 3.17 over JSON-RPC 2.0, with `Content-Length` framing, on standard input and output. It is part
of `ceesafec` and has no dependency beyond CeeSafe's own libraries. The editor starts it; `editors/vscode` is a VS Code
extension that does (§2.4).

### 2.1 What a document is checked with

A document that is a source of a package (a `ceesafe.toml` above it whose sources include it) is checked with its
package, as `ceesafec check` in the package would check it (§4.4): the editor's text for the document, the package's
other files from disk, and the dependencies its `ceesafe.lock` names, never fetching; the manifest's profile and `float`
apply. Any other document, or one whose package does not resolve, is checked as a package of its own, with
`lib/core`, as `ceesafec check file.cee` would check it, using the text the editor holds. Its profile is hosted, unless
its first line is `// profile: freestanding` (the corpus convention, `testing.md` §3).

### 2.2 Capabilities

| Request or notification | What the server does |
|---|---|
| `initialize` | Answers with the capabilities below: full-text synchronisation, hover, definition, document symbols, formatting, quick fixes |
| `textDocument/didOpen`, `didChange`, `didClose` | Keeps the text; after an open or change, checks the document (§2.1) and publishes its diagnostics. A close clears them |
| `textDocument/publishDiagnostics` (sent) | Every diagnostic of the check: its range, severity, code (`N0205`) and message, with each note as related information |
| `textDocument/hover` | On a name or an expression: its type, as CeeSafe writes it. On a local or parameter, `let x: T` or `var x: T`; on a function or method, its signature; on a field, `name: T` |
| `textDocument/definition` | On a local, parameter, function, method, field, struct, enum or interface name: the location of its declaration, if it is in the document |
| `textDocument/documentSymbol` | The document's items and their members, as a tree: functions, structs (fields and methods), enums (variants), interfaces, constants |
| `textDocument/formatting` | The document formatted by `ceesafec fmt` (`formatting.md`), as one edit; nothing if it has a syntax error |
| `textDocument/codeAction` | The fixes (§5.2) of the diagnostics in the requested range, as `quickfix` actions (§5.5) |
| `shutdown`, `exit` | Stops |

Anything else is answered with the JSON-RPC error `MethodNotFound` (requests) or ignored (notifications).

Positions are LSP positions: zero-based lines, and columns in UTF-16 code units, which the server converts to and from
the documents' UTF-8 bytes. Hover and definition use the typed tree of the last check; if the document does not parse,
they answer null and only the diagnostics are shown.

### 2.3 Errors

The server never stops on a bad document. A request that fails inside the compiler is answered with the JSON-RPC
error `InternalError` and the exception's message, and the server goes on. A message that is not valid JSON-RPC is
answered with `ParseError` when it has an id.

### 2.4 The VS Code extension

`editors/vscode` holds:
- a TextMate grammar for `.cee` files (keywords, literals, comments, attributes), whose keyword list is the
  compiler's (`editors/vscode/test/keywords.test.mjs` compares them; Nova's `LspTests`);
- a language configuration (comments, brackets, auto-closing pairs);
- the client, which starts `ceesafec lsp` (the `ceesafe.server.path` setting, default `ceesafec` on the `PATH`) through the
  `vscode-languageclient` library, bundled with it into `dist/extension.cjs`.

It is built with [Vite+](https://viteplus.dev/) (`vp`), not with `ceesafec`:

```sh
cd editors/vscode
vp install            # the dependencies, pinned by pnpm-lock.yaml
vp test               # the grammar and the server tests below
vp run check          # lint and formatting
vp run package        # bundle the client (vp pack) and make ceesafe-language-0.1.0.vsix (vsce)
```

Its tests: `test/grammar.test.mjs` tokenizes CeeSafe lines with `vscode-textmate`, as VS Code does, and checks the scope
each token gets; `test/server.test.mjs` drives a built `ceesafec lsp` through `vscode-jsonrpc`, the library under VS
Code's client (diagnostics, hover, definition, an unknown method, shutdown and exit).

## 3. Debugging (T4)

A CeeSafe program is debugged as the C it compiles to, with the C mapped back to CeeSafe lines. No debugger needs to
know about CeeSafe.

### 3.1 A debug build

`ceesafec build -g file.cee -o program` writes `#line` directives into the C (`c-backend.md`, source maps) and compiles
it with `-g -O0`. A debugger then shows CeeSafe files and lines: breakpoints set by CeeSafe line stop there, and stepping
goes from one CeeSafe statement to the next. A line can take more than one step, since one CeeSafe statement can be several
C statements (a checked addition, a temporary).

| | lldb | gdb |
|---|---|---|
| Stop at a CeeSafe line | `breakpoint set -f demo.cee -l 12` (`b demo.cee:12`) | `break demo.cee:12` |
| Stop when a check fails, before the program aborts | `b ceesafe_panic` | `break ceesafe_panic` |
| Where am I | `bt` | `bt` |

### 3.2 Names

The C names follow `c-backend.md` §2.1, so a CeeSafe name can be found in the debugger:

| CeeSafe | C |
|---|---|
| function `length` | `ceeF_length` |
| method `Counter.bump` | `ceeM_7Counter_bump` (the type's name, prefixed by its length) |
| local or parameter `sum` | `v_sum_1` (a number makes each local's name unique in its function) |
| a temporary the compiler made | `t_3` |
| field `x` | `f_x` |
| struct `Point` | `ceeT_Point` |

### 3.3 CeeSafe names in the debugger

`editors/debug/ceesafe_lldb.py` and `editors/debug/ceesafe_gdb.py` add two commands, which print with CeeSafe names:
- `ceesafe-locals`: the current frame's locals and parameters, `name = value`, without the compiler's temporaries; struct
  values show their fields by their CeeSafe names;
- `ceesafe-bt`: the backtrace, one frame a line, `CeeSafe name at file:line` (`Counter.bump at demo.cee:3`).

Load them with `command script import editors/debug/ceesafe_lldb.py` (lldb) or `source editors/debug/ceesafe_gdb.py` (gdb).

Split C (`--split`, c-backend.md §2.4) renames the program's functions to `ceeF_<program>_…`: set `CEESAFE_PROGRAM` to
the program's name before starting the debugger, and the helpers read them as before.

### 3.4 What is checked

`tools/debugger_check.py` (Nova's `DebuggerTests`) builds a program with `-g` and runs it under lldb (macOS) or gdb (Linux), in batch mode. A breakpoint
at a CeeSafe line must stop at that line, `ceesafe-locals` must show the locals by their CeeSafe names, and a breakpoint on
`ceesafe_panic` must give a backtrace whose frames are CeeSafe functions at CeeSafe lines. On a machine with neither debugger,
the test does nothing, and the run log says which debugger ran.

## 4. Packages (T6, ADR 0013)

### 4.1 The manifest

A package is a directory with `ceesafe.toml`. Its sources are the `.cee` files under the directories `sources` names
(default `src`), in ordinal path order. The manifest is a subset of TOML: `[table]` headers, `key = value` lines
whose value is a string, a boolean, an array of strings or an inline table of strings, and `#` comments.

```toml
[package]
name = "app"                 # required: an identifier, not a keyword and not "core"
version = "0.1.0"            # optional; required to publish (§4.8), MAJOR.MINOR.PATCH
kind = "executable"          # "executable" (default), "library", or "object" (profiles.md §4.3)
profile = "hosted"           # or "freestanding"
float = true                 # false is --no-float (type-system.md §35.9)
kernel = "cosmoos"           # with profile = "freestanding": include lib/kernel, as --kernel cosmoos (ADR 0025)
trusted = true               # its types may be declared @threadSafe (ADR 0025 §3.2); listed for reviewers
sources = ["src"]
c = ["src/shim.c"]           # C files compiled and linked with an executable (type-system.md §28.6)

[dependencies]
geometry = { path = "../geometry" }
lz4 = { git = "https://example.org/lz4-nova.git", tag = "v1.2.0" }      # or rev = "<commit>", or branch = "main"
shapes = "2.1"               # from the registry (§4.6): a version requirement
json = { version = "0.9", index = "https://example.org/my-index.git" }   # from another index
```

A dependency's key is its package's `name`: a dependency is known by the name its own manifest gives it. A
dependency of kind `executable` is N0321: only a library's items are used. Errors in the manifest are N0320 (its
syntax) and N0321 (a missing, unknown or invalid field), with the line.

### 4.2 Resolving dependencies

From the package being built, every dependency is resolved, and then its dependencies, recursively:
- `path` is a directory relative to the manifest that names it, holding the dependency's `ceesafe.toml`;
- `git` is a repository; `rev` names a commit, `tag` and `branch` are resolved to one (§4.3). The commit is
  checked out into the cache, `$CEESAFE_HOME/git/checkouts/<repository>/<commit>` (default `~/.ceesafe`), and the
  dependency is the package at the checkout's root.

A package name reached by two different sources (two paths, two commits, a path and a commit) is N0326, naming both
dependents. A package that depends on itself, directly or not, is N0327. A missing directory or manifest is N0322.
Nothing runs during resolution except `git` (ADR 0013 D5).

### 4.3 The lock file

`ceesafe.lock`, beside `ceesafe.toml`, records the resolution so that every build uses the same code:

```toml
# Written by ceesafec fetch. Commit it with ceesafe.toml.
[[package]]
name = "lz4"
source = "git+https://example.org/lz4-nova.git"
commit = "3f2a9c0d…"         # the full commit id
hash = "sha256:…"            # of the checkout's manifest and sources

[[package]]
name = "geometry"
source = "path+../geometry"
```

- `ceesafec fetch` resolves every dependency, fetching git repositories and resolving tags and branches (`git
  ls-remote`, `git fetch`), and writes the lock. A `rev` is used as written; a `tag` or `branch` is the commit it names
  at that moment, until the next `ceesafec fetch`.
- Every other command reads the lock. It fails with N0324 if the manifest has a dependency the lock lacks or
  records differently (run `ceesafec fetch`), and with N0325 if a git checkout's manifest and sources no longer have the
  lock's hash. A missing checkout of a locked commit is fetched, unless `--offline` is given (N0323 if it cannot be).
- A path dependency has no hash: it is code being worked on beside the package.
- The hash is SHA-256 over, for the manifest and each source file in ordinal order, the path relative to the package
  root, a zero byte, the file's bytes and a zero byte.

### 4.4 Commands

- `ceesafec new <name>` makes `<name>/ceesafe.toml` and `<name>/src/main.cee` (a `main` that prints a line); `--lib`
  makes a library with `src/lib.cee` instead. It also writes `.gitignore` (`out/`) and the agent instructions of
  §7: `AGENTS.md` by default, others with `--agent`, none with `--no-agent`.
- `ceesafec agents [--agent …]` writes or refreshes the agent instructions of the package in the current directory or
  above it (§7.3).
- `ceesafec fetch [--offline] [--update [name]]` resolves and writes `ceesafe.lock` (§4.7).
- `ceesafec publish` checks that the package can be published and prints its index entry (§4.8).
- `ceesafec build`, `check`, `run`, `doc` and `fmt` without file arguments use the package of the nearest `ceesafe.toml` in
  the current directory or above it. `build` writes `out/<name>` (an executable, or `out/<name>.o` for `object`), or
  the C sources with `--emit c`; the manifest's profile, `float` and C files apply, and command-line options add to
  them. `fmt` formats the package's own sources, not its dependencies'.
- The language server (§2.1) checks a document that belongs to a package (a `ceesafe.toml` above it, whose sources
  include it) with that package: the open document's text, the package's other files from disk, and its locked
  dependencies. Without a lock, or outside a package, the document is checked alone as before.

### 4.5 Errors

| Code | Meaning |
|---|---|
| N0320 | `ceesafe.toml` or `ceesafe.lock` is not valid in the TOML subset of §4.1 |
| N0321 | A manifest field is missing, unknown, or has an invalid value |
| N0322 | A path dependency's directory or manifest is missing, or a dependency is named differently from its key |
| N0323 | A git dependency cannot be fetched or resolved, or is needed with `--offline` and absent |
| N0324 | The lock file is missing or does not match the manifest: run `ceesafec fetch` |
| N0325 | A git checkout's manifest and sources do not match the lock's hash |
| N0326 | One package name reached through two different sources |
| N0327 | A dependency cycle |
| N0328 | An invalid version, version requirement, or index entry |
| N0329 | No versions satisfy the requirements: the chain of requirements that conflict |
| N0335 | `ceesafec publish`: the package cannot be published as it is |

### 4.6 The registry (M13 G6, ADR 0017)

A **registry dependency** names a package and a **version requirement**. The package is found in an **index**: a git
repository, by default `https://github.com/vkuttyp/CeeSafe-index`, or `$CEESAFE_INDEX`, or the dependency's `index`.

- **Versions** are `MAJOR.MINOR.PATCH`, three decimal numbers with no leading zeros, compared numerically. There
  are no pre-release or build suffixes in v1.
- **Requirements** are one or more comparators separated by commas, all of which must hold:
  - `"1.4"`, `"^1.4"` and `"^1.4.2"` are caret requirements: at least that version, below the next major version, or
    below the next minor for `0.x` (`"0.3"` is `>=0.3.0, <0.4.0`) and the next patch for `0.0.x`.
  - `"=1.4.2"` means exactly that version.
  - `">=1.4"`, `">1.4"`, `"<2"` and `"<=1.9.3"` compare. A missing minor or patch is 0.
  - `"*"` means any version.
- **The index** holds `packages/<name>.toml`, with one `[[version]]` table per published version, in publishing order:
  ```toml
  [[version]]
  version = "1.4.0"
  git = "https://github.com/someone/geometry.git"
  commit = "3f2a9c0d…"                      # a full commit id
  hash = "sha256:…"                         # of the commit's manifest and sources (§4.3)
  dependencies = { shapes = "2.1" }         # its registry requirements, as its ceesafe.toml writes them
  yanked = false                            # optional; a yanked version is never chosen for a new resolution
  ```
  Entries are only appended. A published package's dependencies are all registry dependencies, and those without
  an `index` come from the index that published the package.

### 4.7 Version solving

`ceesafec fetch` resolves path and git dependencies as before (§4.2), gathering the registry requirements of the root
and of every path and git package. It then chooses one version of each registry package, transitively, from the
index's entries:

- The **newest** version that satisfies every requirement on it is chosen, and so on through its own dependencies.
  On a conflict, the solver backtracks.
- A version the lock already records is preferred while it satisfies the requirements, so `ceesafec fetch` changes
  nothing that needs no change. `--update` prefers the newest for every package, and `--update <name>` for that one.
- **One version per package name** (OD-26). A name reached through a path or git dependency and through the registry
  is N0326.
- If no choice satisfies every requirement, N0329 shows the requirements on the package that could not be chosen,
  and where each came from:
  `no version of 'shapes' satisfies ^2.1 (from geometry 1.4.0) and ^1.0 (from plot 0.3.0)`.
- Each chosen version's commit is checked out as for a git dependency (§4.2). Its hash must be the index's (N0325),
  and its manifest's name and version must be the entry's (N0328).
- The lock records each as `source = "registry+<index>"` with `version`, `repository` (the git URL), `commit` and
  `hash`. Other commands use the lock: an entry whose version no longer satisfies the manifest's requirement is
  N0324.

### 4.8 Publishing

`ceesafec publish` (no network but `git`, and nothing written) checks the package in the current directory:

- it is a library with a valid `version`;
- every dependency is a registry dependency;
- it type-checks with its dependencies;
- its git working tree is clean, and its commit is on a remote branch.

It then prints the index entry for the version: the remote's URL, the commit, the hash and the requirements. To
publish, add that entry to `packages/<name>.toml` in the index by pull request. The index's continuous integration
runs `ceesafec index-check`, which checks every new entry:
- the commit exists;
- its manifest has the entry's name and version;
- its hash and dependencies are the entry's;
- the version is newer than every earlier entry.

A new package name is reviewed by the index's maintainers. Later versions from the same repository merge after the
checks pass.

## 5. Diagnostics for programs (M12 A1)

People read diagnostics as text (`diagnostics.md`, "Format"). Programs, AI agents and editors among them, read the
same diagnostics as JSON, and can apply the fixes the compiler is sure of.

### 5.1 `--diagnostics-format=json`

`check`, `build`, `run` and `parse` accept `--diagnostics-format=json` (or `=text`, the default). With `json`,
diagnostics are not written to standard error; instead one JSON document is written to standard output, as one line,
after the command's own work. `build` still writes its outputs, and `run` still runs the program, if there are no
errors; the program's own output then precedes the document. The exit status is unchanged.

```json
{
  "version": 1,
  "errors": 1,
  "warnings": 0,
  "diagnostics": [
    {
      "code": "N0249",
      "severity": "error",
      "file": "main.cee",
      "start": { "line": 7, "column": 10 },
      "end": { "line": 7, "column": 11 },
      "message": "this parameter is 'borrow mut': write 'mut' before the argument to let the call modify it",
      "summary": "`mut` argument marker missing or misplaced",
      "notes": [ { "file": "main.cee", "start": { … }, "end": { … }, "message": "…" } ],
      "fixes": [
        { "title": "write 'mut' before the argument",
          "edits": [ { "file": "main.cee", "start": { "line": 7, "column": 10 }, "end": { "line": 7, "column": 10 },
                       "newText": "mut " } ] }
      ]
    }
  ]
}
```

- `version` is the format's version: fields may be added within a version, never removed or changed.
- Positions are 1-based lines and columns, columns in UTF-16 code units, as in the text form. `end` is exclusive.
- `file` is the path as the text form prints it.
- `summary` is the code's "Meaning" in `diagnostics.md`, which `ceesafec` embeds.
- Diagnostics are in the order the text form prints them. Keys are written in the order shown.

### 5.2 Fixes

A fix is a list of edits that the compiler is sure resolves the diagnostic. It is offered only where the
intent is unambiguous; a diagnostic with several plausible repairs offers none. Applying a fix removes that
diagnostic and introduces none at the edited place (checked by Nova's `FixTests` for every kind below, and in CeeSafe by applying every corpus fix as novac 0.6.0 does, `tools/compare_cli.py`, on every corpus
case that offers it). The kinds:

| Code | When | Edit |
|---|---|---|
| N0249 | an argument for a `borrow mut` parameter lacks `mut`, and is a place that can be borrowed mutably | insert `mut ` before the argument; if the place is a `let` local, also `let` → `var` at its declaration (one fix) |
| N0249 | an argument for a shared parameter has `mut` | delete the `mut ` |
| N0211 | assignment to a `let` local declared in the function | `let` → `var` at its declaration |
| N0248 | `borrow mut` (or a `borrow mut this` call) of a `let` local declared in the function | `let` → `var` at its declaration |
| N0208 | `e as T` between integer types that can lose information | `truncate<T>(e)` (wrap-around, as the message says) |
| N0100 | `expected ';'`, with no earlier error in the file, after a declaration, assignment, `return`, or a call statement (not after an expression that cannot be a statement, N0225) | insert `;` after the previous token |

### 5.3 `ceesafec fix`

`ceesafec fix [FILES]` (or the package, without files) applies every fix, writes the files, checks again, and repeats
until no fix applies or after 8 rounds. It then prints the remaining diagnostics, as text or with
`--diagnostics-format=json`, and exits 1 if errors remain. With `--dry-run` it changes no file and prints the
edits of the first round. Edits to one file never overlap: when two fixes would, the later one waits for the next
round.

### 5.4 `ceesafec explain`

`ceesafec explain N0249` prints the code's row of `diagnostics.md` (its meaning and example) and the paragraphs of
`diagnostics.md` that mention it. An unknown code is exit status 2.

### 5.5 In the language server

`textDocument/codeAction` returns the fixes of the diagnostics that touch the requested range as `quickfix` actions,
each with its diagnostic and a `WorkspaceEdit` for the document (§2.2). A fix that would edit another file is not
offered.

## 6. The MCP server (M12 A2)

`ceesafec mcp` serves the [Model Context Protocol](https://modelcontextprotocol.io) on standard input and output, so an
AI agent's host (Claude Code, an IDE, any MCP client) can use CeeSafe's compiler, interpreter and documentation as
tools. It is part of `ceesafec`, with no other dependency, and serves the documents embedded in that `ceesafec`, so the
answers always match the compiler that gives them.

```json
{ "mcpServers": { "ceesafe": { "command": "ceesafec", "args": ["mcp"] } } }
```

### 6.1 Protocol

- JSON-RPC 2.0, one message per line of UTF-8 on standard input and output; nothing else is written to standard
  output. The server stops at the end of its input.
- `initialize` negotiates the protocol version: the client's, if it is one the server supports (`2025-06-18`,
  `2025-03-26`, `2024-11-05`), otherwise the newest of those. The server declares `tools`, `resources` and `prompts`,
  none of which change while it runs, and gives brief usage `instructions`.
- `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list` and `prompts/get` are
  answered; other requests are `MethodNotFound` (-32601); notifications are ignored.
- With version `2025-06-18`, each tool declares an `outputSchema` and its result carries `structuredContent`, with the
  same data as JSON text in `content`. With earlier versions, only `content`.
- A tool call that the tool cannot carry out (a file it cannot read, a source that does not parse when it needs to)
  is a result with `isError: true` and the reason. Unknown tools and invalid arguments are `InvalidParams` (-32602).
  The server never stops on a bad request.

### 6.2 Sources

Every tool that compiles takes its program as either
- `files`: an array of `{ "path": "main.cee", "text": "…" }`, compiled as one package, with nothing read from disk; or
- `paths`: an array of `.cee` file paths, read from disk relative to the server's working directory;

plus `profile` (`hosted`, the default, or `freestanding`) and `noFloat` (default false). Paths in results are the
paths given.

### 6.3 Tools

| Tool | Input (besides §6.2) | Result |
|---|---|---|
| `ceesafe_check` | | the diagnostics document of §5.1, with fixes |
| `ceesafe_fix` | | `files`: each file's text with every fix applied, over rounds as `ceesafec fix` does (§5.3); `applied`: the number of fixes; `diagnostics`: what remains. Nothing is written to disk |
| `ceesafe_format` | `text`, `path` (optional) | `text`: formatted (`formatting.md`); or an error with the syntax diagnostics |
| `ceesafe_run` | `stdin` (text), `args`, `maxSteps` (default 10,000,000), `maxOutputBytes` (default 65,536) | `outcome` (`exited`, `panicked`, `fault`, `not-compiled`), `exitCode`, `stdout`, `stderr`, `truncated`, and the diagnostics if it did not compile |
| `ceesafe_emit_c` | `explain`: any of `allocations`, `bounds-checks`, `overflow-checks` | `files`: the generated C (`main.c`, and `ceesafe_exports.h` when there is one; not the runtime); `explanations`: the `--explain-*` text |
| `ceesafe_explain` | `code` | `code`, `meaning`, `example`, `paragraphs` of `diagnostics.md` (§5.4) |
| `ceesafe_spec_search` | `query`, `limit` (default 10) | `results`: the sections whose heading or text contain every word of the query, best first: `document`, `heading`, `snippet`, `uri` |
| `ceesafe_spec_section` | `document` (`type-system`, `grammar`, …), `section` (`31.2`, or heading text) | `text` of that section, with its subsections |
| `ceesafe_symbol` | `path`, `line`, `column` (1-based) | the type or signature under the position, and its declaration's location, as hover and definition give them (§2.2) |

`ceesafe_run` runs the program in the interpreter (`run --interp`) **sandboxed**:
- files, sockets and processes are refused (a fault that names the refusal);
- `maxSteps` statements at most (a fault), and `maxOutputBytes` of each output kept (`truncated` says if more was
  written; the program goes on);
- 256 MiB of interpreter memory at most: the heap then reports out of memory, which the program sees as
  `AllocError.OutOfMemory`; a local or static allocation beyond it is a fault;
- standard input is `stdin`, the arguments are `args`, and the run has no access to the server's environment.

A fault's exit code is 70 and a panic's 134, as for `run --interp`.

### 6.4 Resources

Each embedded document is a resource `ceesafe://docs/<path>` (for example `ceesafe://docs/docs/type-system.md`,
`ceesafe://docs/site/guide/basics.md`), `text/markdown`, named by its first heading. `resources/read` returns its text.
An unknown URI is the error -32002 (resource not found).

### 6.5 Prompts

| Prompt | Arguments | What it asks |
|---|---|---|
| `write-ceesafe` | `task` | To write CeeSafe for the task: the agent guide (`guide/for-agents.md`), then the task, with the edit-check loop of `ceesafe_check` and `ceesafe_fix` |
| `port-c-to-ceesafe` | `file`, `api` | To port a C file to CeeSafe as C6 and C9 did: imported C structs from the header, safe code over slices, `unsafe` only at the exported boundary, and the C's own tests, a differential test and a benchmark (`cosmoos/c9-report.md`) |

## 7. Agent instructions in packages (M12 A4)

AI coding agents read a file of instructions at the root of a project. `ceesafec new` writes one, so that an agent
working in a new CeeSafe package knows from the start what CeeSafe is, which commands check its work, and the mistakes to
avoid. The convention follows Vite+'s (`vp create`).

### 7.1 The CeeSafe section

`AGENTS.md` holds the **CeeSafe section**, between the lines `<!--CEESAFE START-->` and `<!--CEESAFE END-->`: what CeeSafe is and
where its guide for agents is; the package's layout; the commands (`check`, `fix`, `run --interp`, `build`, `fmt`,
`explain`, `--diagnostics-format=json`); how to use the MCP server; a checklist before finishing; and the common
mistakes of the agent guide. The text is embedded in `ceesafec` (`templates/AGENTS.md`) and is the same for every
package. Everything outside the markers belongs to the package's authors: ceesafec never changes it.

### 7.2 Agents

`--agent` takes one or more of these names, separated by commas or by repeating the option; the default is `agents`.
Each name writes the files below; `AGENTS.md` is written whenever any agent is chosen, since the others refer to it.

| Name | Agent | Instructions | MCP configuration (`ceesafec mcp`, §6) |
|---|---|---|---|
| `agents` | Codex, Amp, OpenCode and others that read `AGENTS.md` | `AGENTS.md` | — |
| `claude` | Claude Code | `CLAUDE.md`: `@AGENTS.md` (Claude Code's import) | `.mcp.json` |
| `gemini` | Gemini CLI | `GEMINI.md`: `@AGENTS.md` (Gemini CLI's import) | `.gemini/settings.json` |
| `copilot` | GitHub Copilot | `.github/copilot-instructions.md`: a copy of the CeeSafe section | `.vscode/mcp.json` |
| `cursor` | Cursor | `.cursor/rules/ceesafe.mdc`: a copy of the CeeSafe section, applied always | `.cursor/mcp.json` |

An unknown name is a usage error (exit status 2), and so is `--agent` with `--no-agent`. The MCP configurations name
the server `ceesafe`, with command `ceesafec` and argument `mcp`, in each tool's format: `{"mcpServers": {"ceesafe": …}}`, or
`{"servers": {"ceesafe": {"type": "stdio", …}}}` for VS Code.

### 7.3 `ceesafec agents`

In a package, `ceesafec agents [--agent …]` writes the chosen agents' files (default `agents`):
- a missing file is written as `ceesafec new` writes it;
- in an instructions file that has the markers, the text between them is replaced with the current CeeSafe section,
  and the rest is kept; a file without them gets the CeeSafe section appended, after a blank line; a file that only
  imports `AGENTS.md` (`@AGENTS.md`) is left as it is;
- an MCP configuration that exists is left as it is, and the command says so: it may hold the authors' other servers.

It prints what it wrote and what it left. Run it after updating `ceesafec`, so the instructions match the compiler.

## 8. The C compiler (`ceesafec build`)

`ceesafec build` writes C and gives it to a C compiler. It needs no configuration when a usual compiler is installed.

### 8.1 Which compiler

`--cc <compiler>` names it; otherwise `$CC`; otherwise:
- on Linux and macOS, `cc`;
- on Windows, the first of these that exists: `clang` on `PATH`; `%ProgramFiles%\LLVM\bin\clang.exe` (where the LLVM
  installer, `winget install LLVM.LLVM`, puts it); `gcc` on `PATH` (MinGW-w64); `cl` on `PATH`; Visual Studio's `cl`
  (§8.2). clang and gcc are fully supported; MSVC is best effort (`c-backend.md` §1.1).

With none, the error names what was looked for and how to install one.

### 8.2 Visual Studio's environment (Windows)

clang on Windows and `cl` compile against Visual Studio's C library and the Windows SDK, which they find through the
environment that Visual Studio's developer prompt sets (`INCLUDE`, `LIB`, `PATH`). When that environment is missing
(`INCLUDE` unset) and the compiler is clang or `cl`, `ceesafec build` sets it up for the compiler, as the developer prompt
would:
1. find Visual Studio, or its Build Tools, with the C++ tools for this machine: `vswhere -latest -products *
   -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64` on an ARM64 Windows,
   `…VC.Tools.x86.x64` otherwise (other products that `vswhere` knows, such as SQL Server Management Studio, have no
   C++ tools and are not taken);
2. run its `VC\Auxiliary\Build\vcvarsall.bat` for the machine's architecture (`arm64` or `x64`) and take the
   environment it leaves;
3. run the compiler in that environment. The user's own environment is not changed.

Without Visual Studio, clang still works where the environment is already set; otherwise the error says to install
Visual Studio's "Desktop development with C++" workload (or the Build Tools), or MinGW-w64.

### 8.3 Flags

| Compiler | Flags |
|---|---|
| clang, gcc, `cc` | `c-backend.md` §1's: `-std=c11`, the strict warnings, `-ffp-contract=off -fno-math-errno`, `-O2` (or `-g -O0`), `--cflag`s, `-o <output>`; on Windows also the 8 MiB stack, `-Wl,/STACK:8388608` for clang and `-Wl,--stack,8388608` for gcc |
| `cl` (MSVC) | `/nologo /std:c11 /W3 /O2` (or `/Zi /Od` with `-g`), `--cflag`s, `/Fo:` the build directory (so no `.obj` lands in the project), `/Fe:<output>`, `/link /STACK:8388608` (`c-backend.md` §1.1) |

A compiler is MSVC when its file name is `cl` or `cl.exe`. `--emit obj` (one relocatable object) needs clang or gcc.

### 8.4 The output

The executable is `out/<name>` in a package, or `-o <path>`. On Windows, a path without an extension gets `.exe`, so
`ceesafec build` makes `out\hello.exe`. The output's directory is created if it does not exist.
