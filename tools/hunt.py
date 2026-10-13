#!/usr/bin/env python3
"""Hunt for compiler-introduced timing leaks in a whole crypto library.

For every optimization level: build the library, run the harness under
valgrind, list every function with secret-dependent branches/addresses,
then ask blame.py which LLVM pass introduced each leak.

Usage:
    python3 tools/hunt.py <target> [--cc clang-17] [--summary] [-O0 -O1 ...]
"""
import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import blame


def sh(cmd):
    """Run a command; on failure show its error output and stop."""
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{p.stderr}")
    return p


KYBER_REF_SOURCES = ["kem.c", "indcpa.c", "polyvec.c", "poly.c", "ntt.c", "cbd.c",
                     "reduce.c", "verify.c", "symmetric-shake.c", "fips202.c",
                     "randombytes.c"]

TARGETS = {
    # Kyber reference just before the Clangover fix (CVE-2024-37880): known positive.
    "kyber-ref-2023": dict(
        repo="https://github.com/pq-crystals/kyber.git",
        commit="b628ba78711bc28327dc7d2d5c074a00f061884e",
        subdir="ref",
        sources=KYBER_REF_SOURCES,
        harness="targets/kyber/harness.c",
    ),
    # Same code after the fix: should come out clean.
    "kyber-ref-2024": dict(
        repo="https://github.com/pq-crystals/kyber.git",
        commit="9b8d30698a3e7449aeb34e62339d4176f11e3c6c",
        subdir="ref",
        sources=KYBER_REF_SOURCES,
        harness="targets/kyber/harness.c",
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


def build(cc, srcdir, sources, flags, outdir):
    """Compile every library source into its own object file."""
    outdir.mkdir(parents=True, exist_ok=True)
    objs = {}
    for s in sources:
        obj = outdir / (Path(s).stem + ".o")
        sh([cc, "-g", *flags, "-c", str(srcdir / s), "-o", str(obj)])
        objs[s] = obj
    return objs


def leaks(cc, harness, objs, flags, outdir):
    """Run the harness under valgrind; return {function: (file, line)}."""
    exe, xml = outdir / "harness", outdir / "valgrind.xml"
    incs = [f for f in flags if f.startswith("-I")]
    sh([cc, "-O0", "-g", *incs, harness, *map(str, objs.values()), "-o", str(exe)])
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


def main(name, levels, cc="clang", summary=False):
    t = TARGETS[name]
    srcdir = fetch(name, t)
    flags_common = [f"-I{srcdir}", "-Iinclude"]
    blame.HARNESS, blame.CC = t["harness"], cc
    version = subprocess.run([cc, "--version"], capture_output=True,
                             text=True).stdout.splitlines()[0]
    if not summary:
        print(f"# {name} @ {t['commit'][:10]}  ({version})\n")
    for level in levels:
        flags = [level, *flags_common]
        outdir = Path("build/hunt") / name / cc / level.lstrip("-")
        objs = build(cc, srcdir, t["sources"], flags, outdir)
        found = leaks(cc, t["harness"], objs, flags, outdir)
        if not found:
            print(f"| {cc} | {level} | – | – |" if summary
                  else f"{level}: no secret-dependent branches or addresses")
            continue
        for fn, (file, line) in found.items():
            src = Path(file).name
            if not summary:
                print(f"{level}: LEAK in {fn} ({file}:{line})")
            cause = "?"
            if src in t["sources"]:
                # Bisect only this function's file; link everything else as-is.
                blame.LINK = [str(o) for s, o in objs.items() if s != src]
                cause = blame.main(str(srcdir / src), fn, "secret", flags, verbose=not summary)
            if summary:
                print(f"| {cc} | {level} | `{fn}` | {cause.split(' on ')[0]} |")
            else:
                print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__, allow_abbrev=False)
    ap.add_argument("target", choices=TARGETS)
    ap.add_argument("--cc", default="clang", help="compiler, e.g. clang-17")
    ap.add_argument("--summary", action="store_true", help="one Markdown table row per result")
    args, levels = ap.parse_known_args()
    main(args.target, levels or LEVELS, args.cc, args.summary)
