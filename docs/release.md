# Releasing ceesafec

A tag `v<version>` pushed to GitHub runs `.github/workflows/release.yml`, which publishes `ceesafec` for six platforms
as a GitHub release, with `SHA256SUMS`. `site/public/install.sh` and `install.ps1` (served at
`https://vkuttyp.github.io/CeeSafe/install.sh` and `install.ps1`) install the latest release from it.

## How the binaries are made

One C seed for every platform, so every binary is built from the same C and checked against it:

1. **seed** (Ubuntu 22.04): downloads novac 0.6.0 (`bootstrap/reference.md`; the archive's SHA-256 is checked),
   bootstraps ceesafec (`tools/bootstrap.sh`), rebuilds it with itself, and writes ceesafec's own C (`build --emit
   c`, the default form). The C of the bootstrapped and the rebuilt compiler must be identical: the fixed point.
2. **build**, per platform: generation 1 is the seed compiled by the platform's C compiler (`cc`, or `cl` on Windows);
   generation 1 rebuilds ceesafec with its own `build` (the platform's clang, gcc or `cl`, as `ceesafec build` finds
   them); generation 1 and generation 2 must both emit the seed byte for byte. The macOS binaries are then signed with
   the Developer ID and notarized. A smoke test runs `--version`, the interpreter, a native build and the MCP server.
   `osx-x64` is built on an arm64 runner by ceesafec's own driver (`--cflag -arch --cflag x86_64`) and run under
   Rosetta when the runner has it.
3. **extension**: the VS Code extension's tests (the language server's run against the linux-x64 `ceesafec` just
   built) and its `.vsix`, `ceesafe-language-<version>.vsix`.
4. **publish**: `SHA256SUMS` (the archives and the `.vsix`) and the GitHub release.

| Archive | Built on | Contents |
|---|---|---|
| `ceesafec-linux-x64.tar.gz`, `ceesafec-linux-arm64.tar.gz` | Ubuntu 22.04 (glibc 2.35) | `ceesafec`, `COPYING`, `COPYING.RUNTIME` |
| `ceesafec-osx-arm64.tar.gz`, `ceesafec-osx-x64.tar.gz` | macOS (arm64), signed and notarized | the same |
| `ceesafec-win-x64.zip`, `ceesafec-win-arm64.zip` | Windows | `ceesafec.exe`, `COPYING`, `COPYING.RUNTIME` |
| `ceesafe-language-<version>.vsix` | Ubuntu | the VS Code extension (`guide/editors.md`) |

## Making a release

1. Set the version in `src/backend/c_program.cee`: `ceesafeVersion()` and `compilerBanner()` (`ceesafec <version>`)
   must agree, and the tag must name it; the workflow checks both. The version is a constant so that the generated C
   is reproducible. Set the same version in `editors/vscode/package.json`: the workflow checks it too.
2. Run the contract suite on the commit: `python3 tools/contract_tests.py --ceesafec out/ceesafec` (`spec/testing.md`;
   it includes the fixed point).
3. Tag and push: `git tag v<version> && git push origin v<version>`. Only such a tag runs the workflow (there is no
   manual or branch trigger); it builds, checks, signs and notarizes everything and publishes only if every job passes.
4. Move `main` to the next development version (`<next>-dev`).

## Secrets

The macOS steps need the repository secrets `APPLE_CERTIFICATE_P12` (the Developer ID Application certificate and key,
base64), `APPLE_CERTIFICATE_PASSWORD`, and for `notarytool` `ASC_P8` (the App Store Connect API key, base64),
`ASC_KEY_ID` and `ASC_ISSUER` (the issuer UUID). They were set on 2026-10-31.
