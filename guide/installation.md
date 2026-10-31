# Installation

## Build ceesafec

CeeSafe has no released binaries yet (they are a step of the repository's `ROADMAP.md`, P9). `ceesafec` is written in
CeeSafe and builds itself; the first build of a checkout starts from novac 0.6.0, the Nova release CeeSafe forked
from, which you download from [Nova's releases](https://github.com/vkuttyp/Nova/releases/tag/v0.6.0) into
`~/.nova/0.6.0/bin/novac`.

```sh
git clone https://github.com/vkuttyp/CeeSafe.git
cd CeeSafe
sh tools/bootstrap.sh ~/.nova/0.6.0/bin/novac HEAD out/ceesafec
out/ceesafec --version
```

`tools/bootstrap.sh` has novac build the last commit that novac can read, and the `ceesafec` that makes build the tree
you checked out. After that, `ceesafec` rebuilds itself:

```sh
out/ceesafec build -o out/ceesafec.new && mv out/ceesafec.new out/ceesafec
```

`ceesafec` is one native executable: its runtime, its libraries and this specification are inside it, so it can be
copied anywhere, for example onto your `PATH` as `~/.local/bin/ceesafec`.

## Requirements

| | For | Notes |
|---|---|---|
| A C compiler: clang, gcc or MSVC | building `ceesafec`, and `ceesafec build` | clang and gcc are fully supported; MSVC is best-effort (`/std:c11`). `check`, `run --interp`, `fmt`, `lsp` and `mcp` need none |
| novac 0.6.0 | the first build of a checkout | not needed once you have a `ceesafec` |
| git | dependencies from git repositories | only for [packages](packages.md) that use them |
| Node.js and [Vite+](https://viteplus.dev/) | the VS Code extension | optional |

To check everything, run the contract suite (the repository's `spec/testing.md`; about an hour, since it compiles and
runs the corpus many times and compares the results with novac 0.6.0's):

```sh
python3 tools/contract_tests.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac --root <a Nova checkout at v0.6.0>
```

## Check that it works

```sh
cat > hello.cee <<'EOF'
fn main() {
    Console.writeLine("Hello, CeeSafe");
}
EOF
ceesafec build hello.cee -o hello && ./hello      # through C, to a native program
ceesafec run --interp hello.cee                   # or in the reference interpreter
```

`ceesafec build` uses the C compiler in `$CC`, or `cc`; `--cc clang` picks one. On Windows it finds one itself: clang
(`winget install LLVM.LLVM`), MinGW's gcc, or Visual Studio's `cl`, and it sets up Visual Studio's headers and
libraries for clang and `cl` when you are not in a developer prompt. So with LLVM and Visual Studio's "Desktop
development with C++" workload (or its Build Tools) installed, `ceesafec build` works from any terminal and makes
`out\hello.exe` ([tooling](../spec/tooling.md) §8).

## Editor support

The repository has a VS Code extension in `editors/vscode`: syntax highlighting, and through `ceesafec lsp` errors as you
type, hover, go to definition, the outline and formatting. See [Editors](editors.md) to build and install it, and to
use the language server from other editors.
