#!/usr/bin/env python3
"""Hunt for compiler-introduced timing leaks in a whole crypto library.

For every optimization level: build the library, run the harness under
valgrind, list every function with secret-dependent branches/addresses,
then ask blame.py which LLVM pass introduced each leak.

Usage:
    python3 tools/hunt.py <target> [-O0 -O1 ...]
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import blame

KYBER_REF_SOURCES = ["kem.c", "indcpa.c", "polyvec.c", "poly.c", "ntt.c", "cbd.c",
                     "reduce.c", "verify.c", "symmetric-shake.c", "fips202.c",
                     "randombytes.c"]

TARGETS = {
    # Kyber reference just before the Clangover fix (CVE-2024-37880): known positive.
    "kyber-ref-2023": dict(
        repo="https://github.com/pq-crystals/kyber.git",
        commit="b628ba78711bc28327dc7d2d5c074a00f061884e",
        subdir="ref", sources=KYBER_REF_SOURCES, harness="targets/kyber/harness.c",
    ),
    # Same code after the fix: should come out clean.
    "kyber-ref-2024": dict(
        repo="https://github.com/pq-crystals/kyber.git",
        commit="9b8d30698a3e7449aeb34e62339d4176f11e3c6c",
        subdir="ref", sources=KYBER_REF_SOURCES, harness="targets/kyber/harness.c",
    ),
}
LEVELS = ["-O0", "-O1", "-O2", "-O3", "-Os"]


def fetch(name, t):
    """Clone the target once and check out the pinned commit."""
    path = Path("third_party") / name
    if not path.exists():
        subprocess.run(["git", "clone", "--quiet", t["repo"], str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "checkout", "--quiet", t["commit"]], check=True)
    return path / t["subdir"]


def build(srcdir, sources, flags, outdir):
    """Compile every library source into its own object file."""
    outdir.mkdir(parents=True, exist_ok=True)
    objs = {}
    for s in sources:
        obj = outdir / (Path(s).stem + ".o")
        subprocess.run(["clang", "-g", *flags, "-c", str(srcdir / s), "-o", str(obj)],
                       capture_output=True, text=True, check=True)
        objs[s] = obj
    return objs


def leaks(harness, objs, flags, outdir):
    """Run the harness under valgrind; return {function: (file, line)}."""
    exe, xml = outdir / "harness", outdir / "valgrind.xml"
    incs = [f for f in flags if f.startswith("-I")]
    subprocess.run(["clang", "-O0", "-g", *incs, harness, *map(str, objs.values()),
                    "-o", str(exe)], capture_output=True, text=True, check=True)
    run = subprocess.run(["valgrind", "--xml=yes", f"--xml-file={xml}", str(exe)],
                         capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"harness failed (exit {run.returncode}): wrong result?")
    found = {}
    for err in ET.parse(xml).getroot().iter("error"):
        if err.findtext("kind") in ("UninitCondition", "UninitValue"):
            frame = err.find("stack/frame")
            found.setdefault(frame.findtext("fn"),
                             (frame.findtext("file"), frame.findtext("line")))
    return found


def main(name, levels):
    t = TARGETS[name]
    srcdir = fetch(name, t)
    flags_common = [f"-I{srcdir}", "-Iinclude"]
    blame.HARNESS = t["harness"]
    version = subprocess.run(["clang", "--version"], capture_output=True,
                             text=True).stdout.splitlines()[0]
    print(f"# {name} @ {t['commit'][:10]}  ({version})\n")
    for level in levels:
        flags = [level, *flags_common]
        outdir = Path("build/hunt") / name / level.lstrip("-")
        objs = build(srcdir, t["sources"], flags, outdir)
        found = leaks(t["harness"], objs, flags, outdir)
        if not found:
            print(f"{level}: no secret-dependent branches or addresses")
            continue
        for fn, (file, line) in found.items():
            print(f"{level}: LEAK in {fn} ({file}:{line})")
            # Bisect only this function's file; link everything else as-is.
            src = Path(file).name
            if src in t["sources"]:
                blame.LINK = [str(o) for s, o in objs.items() if s != src]
                blame.main(str(srcdir / src), fn, "secret", flags)
            print()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TARGETS:
        sys.exit(__doc__ + "\nTargets: " + ", ".join(TARGETS))
    main(sys.argv[1], sys.argv[2:] or LEVELS)