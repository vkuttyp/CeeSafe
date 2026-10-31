---
layout: home

hero:
  name: CeeSafe
  text: Memory-safe systems programming, compiled to C
  image:
    src: /logo.svg
    alt: CeeSafe
  tagline: Ownership and borrowing with C#-style syntax, deterministic destruction, explicit allocation, and readable C11 that runs anywhere C runs, including inside an operating system kernel. Its compiler is written in CeeSafe.
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: What CeeSafe is
      link: /guide/introduction
    - theme: alt
      text: Specification
      link: /reference/

features:
  - title: Safe by construction
    details: Values have one owner. Borrows follow the one-writer-or-many-readers rule, checked at compile time with almost no annotations. Overflow, bounds and allocation failure are checked in every build.
  - title: Explicit, pluggable allocation
    details: Boxes, arenas, pools, scratch frames and your own allocators. Allocation failure is a Result. A box that cannot escape lives on the stack.
  - title: C you can read
    details: Structured, warning-clean C11 for clang, gcc and MSVC, with source maps back to CeeSafe lines and a reference interpreter that checks the same programs.
  - title: Ready for kernels
    details: A freestanding profile, context effects that reject sleeping under a spin lock, imported C structs, lock guards and kernel objects.
  - title: Self-hosted
    details: ceesafec is written in CeeSafe and rebuilds itself to the same bytes, generation after generation, on macOS, Linux and Windows.
  - title: Tools included
    details: A formatter, a documentation generator, a language server with a VS Code extension, debugger commands, packages, and an MCP server for AI agents.
---
