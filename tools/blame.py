#!/usr/bin/env python3
"""Find which LLVM optimization pass introduces a timing leak into a function.

Usage:
    python3 tools/blame.py <file.c> <function> <branch|div|secret> [--harness H.c] [clang flags...]

  branch / div  static: count instructions in the disassembly (any target)
  secret        dynamic: run harness H.c under valgrind and count secret-dependent
                branches/addresses inside <function> (host architecture only)

Examples:
    python3 tools/blame.py controls/select.c ctl_select branch \
        -O2 --target=riscv64-linux-gnu -ffreestanding
    python3 tools/blame.py controls/frommsg.c ctl_frommsg secret \
        --harness controls/harness_frommsg.c -Os -Iinclude
"""
import argparse
import difflib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PATTERNS = {
    "branch": re.compile(r"^(b\.\w+|cbn?z|tbn?z|j(?!mp)[a-z]+|"
                         r"beq|bne|blt|bge|bltu|bgeu|beqz|bnez|blez|bgez|bltz|bgtz)$"),
    "div": re.compile(r"^([us]div|i?div[bwlq]?|divu?w?|remu?w?)$"),
}
# Backend switches known to turn selects into branches (or keep divisions).
BACKEND_SWITCHES = [
    "-global-isel=0",
    "-x86-cmov-converter=false",
    "-disable-cgp-select2branch=true",
]
SYM = re.compile(r"^[0-9a-f]+ <(.+)>:$")
INSN = re.compile(r"^\s*[0-9a-f]+:\s+(\S+)")
BISECT = re.compile(r"BISECT: running pass \((\d+)\) (.+)$")
OBJ = Path("build/blame.o")
MAX_DIFF = 40 # lines of diff to print 


def clang(src, flags, extra=(), out=OBJ, emit=()):
    return subprocess.run(["clang", *flags, *emit, *extra, "-c", src, "-o", str(out)],
                          capture_output=True, text=True, check=True)


def count(fn, kind):
    """Number of `kind` instructions inside function `fn` of the last build."""
    asm = subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", str(OBJ)],
                         capture_output=True, text=True, check=True).stdout
    cur, n = None, 0
    for line in asm.splitlines():
        if m := SYM.match(line):
            if not m.group(1).startswith(".L"):
                cur = m.group(1)
        elif cur == fn and (m := INSN.match(line)) and PATTERNS[kind].match(m.group(1)):
            n += 1
    return n


HARNESS = None   # set from --harness


def valgrind_reports(fn, flags):
    """Link the last build with the harness, run valgrind, count reports inside fn."""
    exe, xml = Path("build/blame_exe"), Path("build/blame_vg.xml")
    incs = [f for f in flags if f.startswith("-I")]
    subprocess.run(["clang", "-O0", "-g", *incs, HARNESS, str(OBJ), "-o", str(exe)],
                   capture_output=True, text=True, check=True)
    subprocess.run(["valgrind", "--xml=yes", f"--xml-file={xml}", str(exe)],
                   capture_output=True, text=True)
    n = 0
    for err in ET.parse(xml).getroot().iter("error"):
        if err.findtext("kind") in ("UninitCondition", "UninitValue"):
            if err.findtext("stack/frame/fn") == fn:   # innermost frame
                n += 1
    return n


def measure(src, fn, kind, flags, extra=()):
    clang(src, ["-g", *flags], extra)
    return valgrind_reports(fn, flags) if kind == "secret" else count(fn, kind)


def passes(src, flags):
    """List of (number, description) of every pass the optimizer runs."""
    err = clang(src, flags, ["-mllvm", "-opt-bisect-limit=-1"]).stderr
    return [(int(m.group(1)), m.group(2)) for m in map(BISECT.search, err.splitlines()) if m]


def asm_after(src, fn, flags, limit):
    """Disassembly of fn after only `limit` passes (addresses stripped for diffing)."""
    clang(src, flags, ["-mllvm", f"-opt-bisect-limit={limit}"])
    asm = subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", "--no-leading-addr",
                          str(OBJ)], capture_output=True, text=True, check=True).stdout
    lines, cur = [], None
    for line in asm.splitlines():
        if line.endswith(">:"):
            name = line.split("<")[1][:-2]
            if not name.startswith(".L"):
                cur = name
        elif cur == fn and line.strip():
            lines.append(line.strip())
    return lines


def ir_after(src, fn, flags, limit):
    out = Path("build/blame.ll")
    clang(src, flags, ["-mllvm", f"-opt-bisect-limit={limit}"], out=out,
          emit=["-S", "-emit-llvm"])
    text = out.read_text()
    m = re.search(rf"^define [^\n]*@{re.escape(fn)}\(.*?^\}}", text, re.S | re.M)
    return m.group(0).splitlines() if m else []


def main(src, fn, kind, flags):
    Path("build").mkdir(exist_ok=True)

    def at(limit):  # how many risky instructions with only `limit` passes enabled
        return measure(src, fn, kind, flags, ["-mllvm", f"-opt-bisect-limit={limit}"])

    full = measure(src, fn, kind, flags)
    if full == 0:
        print(f"{fn}: no {kind} with {' '.join(flags)}, nothing to blame.")
        return
    all_passes = passes(src, flags)
    base = at(0)
    print(f"{fn}: {full} {kind}(s) with all {len(all_passes)} passes, {base} with none.")

    if full > base:
        lo, hi = 0, len(all_passes)       # invariant: at(lo) == base, at(hi) > base
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if at(mid) > base:
                hi = mid
            else:
                lo = mid
        print(f"First pass that adds a {kind}: ({hi}) {dict(all_passes)[hi]}")
        before, after = ir_after(src, fn, flags, lo), ir_after(src, fn, flags, hi)
        what = "IR"
        if before == after:   # machine-level pass: IR unchanged, look at the assembly
            before, after = asm_after(src, fn, flags, lo), asm_after(src, fn, flags, hi)
            what = "assembly"
        print(f"{what} of {fn} before -> after this pass:")
        for line in difflib.unified_diff(before, after, "before", "after", lineterm="", n=1):
            print("   " + line)
    if base > 0 and kind != "secret":
        print(f"{base} {kind}(s) exist even with no optimization passes:")
        print("-> front-end or backend (instruction selection / lowering).")
        for sw in BACKEND_SWITCHES:
            try:
                n = measure(src, fn, kind, flags, ["-mllvm", sw])
            except subprocess.CalledProcessError:
                continue  # switch not available for this target
            if n < full:
                print(f"   -mllvm {sw}: {full} -> {n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__, allow_abbrev=False)
    ap.add_argument("src")
    ap.add_argument("function")
    ap.add_argument("kind", choices=["branch", "div", "secret"])
    ap.add_argument("--harness")
    args, clang_flags = ap.parse_known_args()   # everything unknown goes to clang
    if args.kind == "secret" and not args.harness:
        ap.error("kind 'secret' needs --harness")
    HARNESS = args.harness
    main(args.src, args.function, args.kind, clang_flags)