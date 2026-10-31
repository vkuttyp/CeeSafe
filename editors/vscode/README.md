# CeeSafe for VS Code

Syntax highlighting for `.cee` files, and, through `ceesafec lsp` (Nova's docs/tooling.md §2), diagnostics as you type, hover
with types, go to definition, the outline, and formatting with `ceesafec fmt`'s style.

Build and install with [Vite+](https://viteplus.dev/) (`vp`); the extension needs `ceesafec` on the `PATH` or in the
`ceesafe.server.path` setting:

```sh
cd editors/vscode
vp install
vp test                 # grammar tests, and ceesafec lsp through vscode-jsonrpc
vp run package          # makes ceesafe-language-0.1.0.vsix
code --install-extension ceesafe-language-0.1.0.vsix
```
