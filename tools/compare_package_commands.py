#!/usr/bin/env python3
"""Compares ceesafec's package commands with the pinned novac's (docs/p8-plan.md S3), after the reference's
PackageManagerTests and AgentFilesTests.

Each scenario builds a tree of packages (and git repositories, a package index, a remote) twice: with Nova's names for
novac (nova.toml, nova.lock, .nova) and with CeeSafe's for ceesafec (ceesafe.toml, ceesafe.lock, .cee), each with its own
home ($NOVA_HOME, $CEESAFE_HOME) and index ($NOVA_INDEX, $CEESAFE_INDEX). Then the same commands run in both trees and
must give the same exit status, stdout and stderr, and leave the same lock and agent files, once ceesafec's names are
mapped back (tools/names.py) and the parts that must differ are normalised: each tree's root, commit ids (the trees'
repositories hold different file names) and package hashes. The hashes ceesafec writes are checked separately against
this script's own SHA-256 over the CeeSafe tree (tooling.md §4.3).

usage: python3 tools/compare_package_commands.py --ceesafec out/ceesafec --novac ~/.nova/0.6.0/bin/novac [scenario...]
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

from names import map_back

FLAVOURS = {
    "nova": {"manifest": "nova.toml", "lock": "nova.lock", "ext": ".nova", "home": "NOVA_HOME", "index": "NOVA_INDEX"},
    "cee": {"manifest": "ceesafe.toml", "lock": "ceesafe.lock", "ext": ".cee", "home": "CEESAFE_HOME",
            "index": "CEESAFE_INDEX"},
}

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "GIT_AUTHOR_DATE": "2026-10-31T00:00:00Z", "GIT_COMMITTER_DATE": "2026-10-31T00:00:00Z"}


class Tree:
    """One flavour of a scenario: files under `root`, with that flavour's names."""

    def __init__(self, root, flavour):
        self.root = root
        self.f = FLAVOURS[flavour]
        self.flavour = flavour
        self.home = os.path.join(root, "home")
        self.index = os.path.join(root, "index")

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def write(self, relative, text):
        relative = relative.replace("{manifest}", self.f["manifest"]).replace("{lock}", self.f["lock"])
        if relative.endswith(".nova"):
            relative = relative[:-5] + self.f["ext"]
        full = self.path(relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def package(self, directory, manifest, sources=None):
        self.write(f"{directory}/{{manifest}}", manifest)
        for name, text in (sources or {}).items():
            self.write(f"{directory}/{name}", text)

    def git(self, directory, *arguments):
        p = subprocess.run(["git", "-C", self.path(directory)] + list(arguments), capture_output=True, text=True,
                           env={**os.environ, **GIT_ENV})
        if p.returncode != 0:
            raise RuntimeError(f"git {' '.join(arguments)} in {directory}: {p.stderr}")
        return p.stdout.strip()

    def commit_all(self, directory, message="c"):
        self.git(directory, "add", "-A")
        self.git(directory, "commit", "-q", "-m", message)
        return self.git(directory, "rev-parse", "HEAD")

    def init_repo(self, directory):
        self.git(directory, "init", "-q", "-b", "main")
        return self.commit_all(directory)

    def env(self):
        return {**os.environ, **GIT_ENV, self.f["home"]: self.home, self.f["index"]: self.index}


def normalise(tree, text):
    text = text.replace(os.path.realpath(tree.root).encode(), b"ROOT").replace(tree.root.encode(), b"ROOT")
    text = re.sub(rb"sha256:[0-9a-f]{64}", b"sha256:HASH", text)
    text = re.sub(rb"\b[0-9a-f]{40}\b", b"COMMIT", text)
    text = re.sub(rb"\b[0-9a-f]{12}\b", b"SHORT", text)
    return text


def files_of(tree, relatives):
    out = {}
    for r in relatives:
        r = r.replace("{manifest}", tree.f["manifest"]).replace("{lock}", tree.f["lock"])
        if r.endswith(".nova"):
            r = r[:-5] + tree.f["ext"]
        full = tree.path(r)
        out[r] = open(full, "rb").read() if os.path.exists(full) else None
    return out


def package_hash(directory, manifest_name, ext, sources=("src",), c_files=()):
    """tooling.md §4.3's hash, computed here: path, NUL, bytes, NUL over the sources, C files and manifest."""
    files = {}
    for s in sources:
        base = os.path.join(directory, s)
        for d, _, names in os.walk(base):
            for n in names:
                if n.endswith(ext):
                    full = os.path.join(d, n)
                    files[os.path.relpath(full, directory).replace(os.sep, "/")] = full
    for c in c_files:
        files[c] = os.path.join(directory, c)
    files[manifest_name] = os.path.join(directory, manifest_name)
    sha = hashlib.sha256()
    for relative in sorted(files, key=lambda r: r.encode("utf-16-le")):
        if os.path.exists(files[relative]):
            sha.update(relative.encode() + b"\0" + open(files[relative], "rb").read() + b"\0")
    return "sha256:" + sha.hexdigest()


# ---- Scenarios: each takes a tree and returns the steps, (directory, arguments) or ("files", [paths]) ----

LIB = "/// The area.\npublic fn area(w: i32, h: i32) -> i32 => w * h;\n"
MAIN = "fn main() {\n    Console.writeLine(geometry.area(2, 3));\n}\n"

BAD_MANIFESTS = [
    "[package]\nname = app\n", "[package]\nname = \"app\"\nname = \"b\"\n", "[package]\nname = \"a\\q\"\n",
    "[dependencies]\n", "[package]\nname = \"fn\"\n", "[package]\nname = \"core\"\n",
    "[package]\nname = \"app\"\nkind = \"binary\"\n", "[package]\nname = \"app\"\nedition = \"2026\"\n",
    "[package]\nname = \"app\"\n[tools]\n", "[package]\nname = \"app\"\n[dependencies]\ng = { path = \"../g\", git = \"x\" }\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = { git = \"x\" }\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = { path = \"../g\", tag = \"v1\" }\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = \"1.x\"\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = { version = \"1.0\", tag = \"v1\" }\n",
    "[package]\nname = \"app\"\nversion = \"1.0\"\n",
    # More of the TOML subset and the fields.
    "[package]\nname = \"app\"\nfloat = 1\n", "[package]\nname = \"app\"\nsources = []\n",
    "[package]\nname = \"app\"\nkernel = \"cosmoos\"\n", "[package]\nname = \"app\"\nc = \"x.c\"\n",
    "x = \"1\"\n[package]\nname = \"app\"\n", "[package]\n[package]\nname = \"app\"\n",
    "[package]\nname = \"app\"\nsources = [\"src\", 3]\n", "[package]\nname = \"app\" # a comment\n\n[dependencies]\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = { path = \"../g\" \n", "[package]\nname = \"app\"\n[dependencies]\n1g = \"1\"\n",
    "[package]\nname = \"app\"\n[dependencies]\ng = 1\n", "[package]\nname = \"app\"\nversion = \"01.2.3\"\n",
    "[package]\nname = \"app\"\nprofile = \"freestanding\"\nkernel = \"linux\"\n", "[package\nname = \"app\"\n",
    "[package]\nname = \"app\"\ntrusted = \"yes\"\n", "[[package]]\nname = \"app\"\n",
]


def scenario_bad_manifests(t):
    steps = []
    for k, text in enumerate(BAD_MANIFESTS):
        t.package(f"bad{k}", text, {"src/main.nova": "fn main() {}\n"})
        steps += [(f"bad{k}", ["check"]), (f"bad{k}", ["check", "--diagnostics-format=json"]), (f"bad{k}", ["fetch"])]
    return steps


def scenario_path(t):
    t.package("geometry", "[package]\nname = \"geometry\"\nkind = \"library\"\n", {"src/geometry.nova": LIB})
    t.package("app", "[package]\nname = \"app\"\n\n[dependencies]\ngeometry = { path = \"../geometry\" }\n",
              {"src/main.nova": MAIN})
    return [("app", ["check"]), ("app", ["parse"]), ("app", ["fetch"]), ("files", ["app/{lock}"]), ("app", ["check"]),
            ("app", ["parse", "--dump-ast"]), ("app", ["fmt", "--check"]), ("app", ["doc"]), ("app", ["fix", "--dry-run"]),
            ("app", ["check", "--dump-hir"]), ("app", ["fetch", "--offline"]), ("app", ["fetch", "--bogus"]),
            ("edit", ("app/{manifest}", "[package]\nname = \"app\"\n\n[dependencies]\ngeometry = { path = \"../geometry\" }\n"
                      "shapes = { path = \"../shapes\" }\n")),
            ("app", ["check"]), ("app", ["fetch"]),
            ("edit", ("shapes/{manifest}", "[package]\nname = \"shapes\"\nkind = \"library\"\n")),
            ("edit", ("shapes/src/s.nova", "public fn one() -> i32 => 1;\n")),
            ("app", ["check"]), ("app", ["fetch"]), ("app", ["check"]), ("files", ["app/{lock}"])]


def scenario_graph(t):
    lib = "[package]\nname = \"{0}\"\nkind = \"library\"\n\n[dependencies]\n{1}"
    t.package("app", "[package]\nname = \"app\"\n\n[dependencies]\nb = { path = \"../b\" }\nc = { path = \"../c\" }\n",
              {"src/main.nova": "fn main() {}\n"})
    t.package("b", lib.format("b", "shared = { path = \"../shared1\" }\n"), {"src/b.nova": "public fn b() {}\n"})
    t.package("c", lib.format("c", "shared = { path = \"../shared2\" }\n"), {"src/c.nova": "public fn c() {}\n"})
    for s in ("shared1", "shared2"):
        t.package(s, lib.format("shared", ""), {"src/s.nova": "public fn s() {}\n"})
    # The same dependency reached twice.
    t.package("app2", "[package]\nname = \"app2\"\n\n[dependencies]\nb = { path = \"../b2\" }\nc = { path = \"../c2\" }\n",
              {"src/main.nova": "fn main() {}\n"})
    t.package("b2", lib.format("b", "shared = { path = \"../shared1\" }\n"), {"src/b.nova": "public fn b() {}\n"})
    t.package("c2", lib.format("c", "shared = { path = \"../shared1\" }\n"), {"src/c.nova": "public fn c() {}\n"})
    # Cycles.
    t.package("cy1", "[package]\nname = \"app\"\n\n[dependencies]\nb = { path = \"../cb1\" }\n", {"src/main.nova": "fn main() {}\n"})
    t.package("cb1", lib.format("b", "a = { path = \"../ca1\" }\n"), {"src/b.nova": "public fn b() {}\n"})
    t.package("ca1", lib.format("a", "b = { path = \"../cb1\" }\n"), {"src/a.nova": "public fn a() {}\n"})
    t.package("cy2", "[package]\nname = \"app\"\n\n[dependencies]\nb = { path = \"../cb2\" }\n", {"src/main.nova": "fn main() {}\n"})
    t.package("cb2", lib.format("b", "app = { path = \"../cy2\" }\n"), {"src/b.nova": "public fn b() {}\n"})
    # Missing dependencies.
    t.package("geometry", "[package]\nname = \"geometry\"\nkind = \"library\"\n", {"src/g.nova": LIB})
    t.package("tool", "[package]\nname = \"tool\"\n", {"src/main.nova": "fn main() {}\n"})
    for k, dependency in enumerate(["geometry = { path = \"../missing\" }\n", "geom = { path = \"../geometry\" }\n",
                                    "tool = { path = \"../tool\" }\n"]):
        t.package(f"miss{k}", "[package]\nname = \"app\"\n\n[dependencies]\n" + dependency, {"src/main.nova": "fn main() {}\n"})
    steps = []
    for d in ("app", "app2", "cy1", "cy2", "miss0", "miss1", "miss2"):
        steps += [(d, ["fetch"]), (d, ["check"])]
    return steps + [("files", ["app2/{lock}"])]


def git_package(t, directory, name, version=None, dependencies=""):
    manifest = f"[package]\nname = \"{name}\"\nkind = \"library\"\n"
    if version:
        manifest += f"version = \"{version}\"\n"
    manifest += "\n[dependencies]\n" + dependencies
    t.package(directory, manifest, {f"src/{name}.nova": f"/// {name}.\npublic fn {name}Value() -> i32 => 7;\n"})


def scenario_git(t):
    git_package(t, "geometry", "geometry")
    first = t.init_repo("geometry")
    t.git("geometry", "tag", "v1")
    t.write("geometry/src/more.nova", "public fn more() -> i32 => 8;\n")
    t.commit_all("geometry")
    url = t.path("geometry")
    steps = []
    for k, reference in enumerate(["tag = \"v1\"", "branch = \"main\"", f"rev = \"{first}\"", "tag = \"v9\""]):
        t.package(f"app{k}", f"[package]\nname = \"app{k}\"\n\n[dependencies]\ngeometry = {{ git = \"{url}\", {reference} }}\n",
                  {"src/main.nova": "fn main() {\n    Console.writeLine(geometry.geometryValue());\n}\n"})
        steps += [(f"app{k}", ["fetch"]), ("files", [f"app{k}/{{lock}}"]), (f"app{k}", ["check"])]
    # Offline with a fresh home, then a changed checkout.
    steps += [("hash", "app0"), ("hash", "app1"), ("hash", "app2"), ("home", "fresh"), ("app0", ["check"]),
              ("app0", ["check", "--offline"]), ("app0", ["fetch", "--offline"]), ("app0", ["fetch"]), ("hash", "app0"),
              ("tamper", "geometry"), ("app0", ["check"])]
    return steps


def scenario_registry(t):
    # Packages in git, published in a local index.
    git_package(t, "shapes", "shapes", "1.0.0")
    t.init_repo("shapes")
    shapes = {}
    shapes["1.0.0"] = t.git("shapes", "rev-parse", "HEAD")
    hashes = {"1.0.0": package_hash(t.path("shapes"), t.f["manifest"], t.f["ext"])}
    for v in ("1.2.0", "2.0.0"):
        git_package(t, "shapes", "shapes", v, "colour = \"0.3\"\n" if v == "1.2.0" else "")
        shapes[v] = t.commit_all("shapes")
        hashes[v] = package_hash(t.path("shapes"), t.f["manifest"], t.f["ext"])
    git_package(t, "colour", "colour", "0.3.1")
    colour = t.init_repo("colour")
    colour_hash = package_hash(t.path("colour"), t.f["manifest"], t.f["ext"])
    entries = ""
    for v in ("1.0.0", "1.2.0", "2.0.0"):
        entries += (f"[[version]]\nversion = \"{v}\"\ngit = \"{t.path('shapes')}\"\ncommit = \"{shapes[v]}\"\n"
                    f"hash = \"{hashes[v]}\"\n")
        if v == "1.2.0":
            entries += "dependencies = { colour = \"0.3\" }\n"
        entries += "\n"
    t.write("index/packages/shapes.toml", entries)
    t.write("index/packages/colour.toml", f"[[version]]\nversion = \"0.3.1\"\ngit = \"{t.path('colour')}\"\n"
                                           f"commit = \"{colour}\"\nhash = \"{colour_hash}\"\n")
    t.write("index/packages/bad.toml", "[[version]]\nversion = \"1\"\n")
    t.init_repo("index")
    steps = []
    for k, requirement in enumerate(["1.0", "1", "=1.0.0", ">=3", "*", "0.1"]):
        t.package(f"app{k}", f"[package]\nname = \"app{k}\"\n\n[dependencies]\nshapes = \"{requirement}\"\n",
                  {"src/main.nova": "fn main() {\n    Console.writeLine(shapes.shapesValue());\n}\n"})
        steps += [(f"app{k}", ["fetch"]), ("files", [f"app{k}/{{lock}}"]), (f"app{k}", ["check"])]
    t.package("conflict", "[package]\nname = \"conflict\"\n\n[dependencies]\nshapes = \"1.2\"\ncolour = \"0.4\"\n",
              {"src/main.nova": "fn main() {}\n"})
    t.package("missing", "[package]\nname = \"missing\"\n\n[dependencies]\nnothing = \"1\"\n", {"src/main.nova": "fn main() {}\n"})
    t.package("invalid", "[package]\nname = \"invalid\"\n\n[dependencies]\nbad = \"1\"\n", {"src/main.nova": "fn main() {}\n"})
    steps += [("conflict", ["fetch"]), ("missing", ["fetch"]), ("invalid", ["fetch"]),
              ("app1", ["fetch", "--update"]), ("app1", ["fetch", "--update", "shapes"]), ("files", ["app1/{lock}"]),
              ("app1", ["fetch", "--offline"]), ("index", ["index-check"]), ("index", ["index-check", "--offline"]),
              (".", ["index-check", "index"]), (".", ["index-check", "a", "b"])]
    return steps


def scenario_publish(t):
    git_package(t, "remote", "lib1", "0.2.0")
    t.init_repo("remote")
    t.git(".", "clone", "-q", "--bare", t.path("remote"), t.path("origin.git")) if False else None
    subprocess.run(["git", "clone", "-q", "--bare", t.path("remote"), t.path("origin.git")], check=True, env=t.env())
    t.git("remote", "remote", "add", "origin", t.path("origin.git"))
    t.git("remote", "fetch", "-q", "origin")
    t.package("exe", "[package]\nname = \"exe\"\nversion = \"1.0.0\"\n", {"src/main.nova": "fn main() {}\n"})
    t.package("noversion", "[package]\nname = \"noversion\"\nkind = \"library\"\n", {"src/l.nova": "public fn f() {}\n"})
    t.package("local", "[package]\nname = \"local\"\nkind = \"library\"\nversion = \"1.0.0\"\n\n[dependencies]\n"
              "x = { path = \"../x\" }\n", {"src/l.nova": "public fn f() {}\n"})
    t.package("broken", "[package]\nname = \"broken\"\nkind = \"library\"\nversion = \"1.0.0\"\n",
              {"src/l.nova": "public fn f() -> i32 => true;\n"})
    t.package("nogit", "[package]\nname = \"nogit\"\nkind = \"library\"\nversion = \"1.0.0\"\n", {"src/l.nova": "public fn f() {}\n"})
    return [("remote", ["publish"]), ("remote", ["publish", "--x"]), ("exe", ["publish"]), ("noversion", ["publish"]),
            ("local", ["publish"]), ("broken", ["publish"]), ("edit", ("remote/src/extra.nova", "public fn g() {}\n")),
            ("remote", ["publish"])]


SECTION_OLD = "# Mine\n\nKeep this.\n\n<!--{0} START-->\nold text\n<!--{0} END-->\n\nAfter.\n"


def scenario_agents(t):
    t.package("p", "[package]\nname = \"p\"\n", {"src/main.nova": "fn main() {}\n"})
    marker = "NOVA" if t.flavour == "nova" else "CEESAFE"
    t.package("q", "[package]\nname = \"q\"\n", {"src/main.nova": "fn main() {}\n"})
    t.write("q/AGENTS.md", SECTION_OLD.format(marker))
    t.write("q/CLAUDE.md", "Rules.\n@AGENTS.md\n")
    t.write("q/GEMINI.md", "Gemini rules, no import")
    t.write("q/.mcp.json", "{}\n")
    t.package("r", "[package]\nname = \"r\"\n", {"src/main.nova": "fn main() {}\n"})
    t.write("r/AGENTS.md", "")
    files = [f"{d}/{n}" for d in ("p", "q", "r") for n in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".mcp.json",
                                                             ".gemini/settings.json", ".github/copilot-instructions.md",
                                                             ".vscode/mcp.json", ".cursor/mcp.json")]
    files += ["p/.cursor/rules/MDC", "q/.cursor/rules/MDC"]
    return [("p", ["agents"]), ("p", ["agents", "--agent", "claude,gemini", "--agent=copilot,CURSOR"]),
            ("p", ["agents", "--agent", "all"]), ("p", ["agents", "--no-agent"]), ("p", ["agents", "x"]),
            ("p", ["agents", "--agent"]), ("p", ["agents", "--agent", "claude", "--no-agent"]),
            ("q", ["agents", "--agent", "claude,gemini,copilot,cursor"]),
            ("q", ["agents", "--agent", "claude,gemini,copilot,cursor"]), ("r", ["agents"]),
            ("p/src", ["agents", "--agent", "cursor"]), (".", ["agents"]), ("files", files)]


def scenario_new(t):
    os.makedirs(t.path("full"), exist_ok=True)
    t.write("full/x.txt", "x")
    os.makedirs(t.path("empty"), exist_ok=True)
    steps = [(".", ["new", "hello"]), (".", ["new", "lib1", "--lib", "--no-agent"]), (".", ["new", "fn"]),
             (".", ["new", "core"]), (".", ["new", "full"]), (".", ["new", "empty", "--agent", "claude"]),
             (".", ["new"]), (".", ["new", "a", "b"]), (".", ["new", "--lib"]), (".", ["new", "sub/deep/"]),
             (".", ["new", "x", "--agent", "bogus"]), ("hello", ["check"]), ("lib1", ["doc"]),
             ("hello", ["fmt", "--check"])]
    files = [f"{d}/{n}" for d in ("hello", "lib1", "empty", "sub/deep")
             for n in ("{manifest}", "src/main.nova", "src/lib.nova", ".gitignore", "AGENTS.md", "CLAUDE.md", ".mcp.json")]
    return steps + [("files", files)]


SCENARIOS = {"bad-manifests": scenario_bad_manifests, "path": scenario_path, "graph": scenario_graph,
             "git": scenario_git, "registry": scenario_registry, "publish": scenario_publish,
             "agents": scenario_agents, "new": scenario_new}


def run_scenario(name, cee, novac, work):
    # Directory names of one length, so spans over paths underline alike.
    trees = {f: Tree(os.path.realpath(os.path.join(work, f[0])), f) for f in ("nova", "cee")}
    plans = {}
    for f, tree in trees.items():
        os.makedirs(tree.root)
        plans[f] = SCENARIOS[name](tree)
    problems = []
    runs = 0
    for k in range(len(plans["nova"])):
        outcomes = {}
        for f, tree in trees.items():
            step, argument = plans[f][k]
            compiler = novac if f == "nova" else cee
            if step == "files":
                paths = [p.replace("MDC", "nova.mdc" if f == "nova" else "ceesafe.mdc") for p in argument]
                found = files_of(tree, paths)
                outcomes[f] = [None if v is None else normalise(tree, v if f == "nova" else map_back(v))
                               for v in found.values()]
            elif step == "edit":
                tree.write(*argument)
                outcomes[f] = None
            elif step == "home":
                shutil.rmtree(tree.home, ignore_errors=True)
                outcomes[f] = None
            elif step == "tamper":
                # Change every checkout of the repository in the cache.
                for base, _, files in os.walk(os.path.join(tree.home, "git", "checkouts")):
                    for n in files:
                        if n.endswith(tree.f["ext"]):
                            with open(os.path.join(base, n), "a") as fh:
                                fh.write("// changed\n")
                outcomes[f] = None
            elif step == "hash":
                outcomes[f] = None
                if f == "cee":
                    problems += check_hashes(tree, argument)
            else:
                runs += 1
                p = subprocess.run([compiler] + argument, cwd=tree.path(step), capture_output=True, env=tree.env())
                out, err = p.stdout, p.stderr
                if f == "cee":
                    out, err = map_back(out), map_back(err)
                outcomes[f] = (p.returncode, normalise(tree, out), normalise(tree, err))
        if outcomes["nova"] != outcomes["cee"]:
            step = plans["nova"][k]
            problems.append(f"{name}: step {k} {step[0]} {step[1] if step[0] != 'files' else ''}: differs\n"
                            f"    novac:    {repr(outcomes['nova'])[:600]}\n    ceesafec: {repr(outcomes['cee'])[:600]}")
    return runs, problems


def check_hashes(tree, directory):
    """The hashes in ceesafec's lock equal this script's SHA-256 over each checkout."""
    problems = []
    lock = tree.path(directory, tree.f["lock"])
    if not os.path.exists(lock):
        return [f"hash: no {lock}"]
    text = open(lock, encoding="utf-8").read()
    pinned = re.findall(r'commit = "([0-9a-f]{40})"\nhash = "(sha256:[0-9a-f]{64})"', text)
    if not pinned:
        problems.append(f"hash: {lock} pins no git package")
    for commit, digest in pinned:
        checkouts = [os.path.join(base, d) for base, dirs, _ in os.walk(os.path.join(tree.home, "git", "checkouts"))
                     for d in dirs if d == commit]
        if not checkouts:
            problems.append(f"hash: no checkout of {commit}")
            continue
        expected = package_hash(checkouts[0], tree.f["manifest"], tree.f["ext"])
        if expected != digest:
            problems.append(f"hash: {commit[:12]}: lock {digest}, computed {expected}")
        tree.hashes_checked = getattr(tree, "hashes_checked", 0) + 1
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ceesafec", required=True)
    parser.add_argument("--novac", required=True)
    parser.add_argument("scenarios", nargs="*")
    options = parser.parse_args()
    cee, novac = os.path.abspath(options.ceesafec), os.path.expanduser(options.novac)
    names = options.scenarios or list(SCENARIOS)
    total_runs = 0
    problems = []
    for name in names:
        with tempfile.TemporaryDirectory() as work:
            runs, found = run_scenario(name, cee, novac, work)
        total_runs += runs
        problems += found
        print(f"  {name}: {runs} runs, {'identical' if not found else f'{len(found)} differ'}")
    for p in problems[:40]:
        print("differ:", p)
    print(f"compare_package_commands: {len(names)} scenarios, {total_runs} runs, {len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
