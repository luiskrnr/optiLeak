#!/usr/bin/env python3
"""find which LLVM optimization pass introduces timing leak into a function

Usage:
    python3 tools/blame.py <file.c> <function> <branch|div> [clang flags...]

Example:
    python3 tools/blame.py controls/select.c ctl_select branch \
        -O2 --target=riscv64-linux-gnu -ffreestanding
"""


import difflib
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "branch": re.compile(r"^(b\.\w+|cbn?z|tbn?z|j(?!mp)[a-z]+|"
                         r"beq|bne|blt|bge|bltu|bgeu|beqz|bnez|blez|bgez|bltz|bgtz)$"),
    "div": re.compile(r"^([us]div|i?div[bwlq]?|divu?w?|remu?w?)$"),
}
# backend switches known to turn selects into branches / or keep revisions
BACKEND_SWITCHES = [
    "-global-isel=0",
    "-x86-cmov-converter=false",
    "-disable-cgp-select2branch=true",
]
SYM = re.compile(r"^[0-9a-f]+ <(.+)>:$")
INSN = re.compile(r"^\s*[0-9a-f]+:\s+(\S+)")
BISECT = re.compile(r"BISECT: running pass \((\d+)\) (.+)$")
OBJ = Path("build/blame.o")

def clang(src, flags, extra=(), out=OBJ, emit=()):
    return subprocess.run(["clang", *flags, *emit, *extra, "-c", src, "-o", str(out)],
                          capture_output=True, text=True, check=True)


def count(fn, kind):
    """Number of `kind` instructions inside function `fn` of  last build."""
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


def measure(src, fn, kind, flags, extra=()):
    clang(src, flags, extra)
    return count(fn, kind)




def passes(src, flags):
    """List of (number, description) of every pass the optimizer runs."""
    err = clang(src, flags, ["-mllvm", "-opt-bisect-limit=-1"]).stderr
    return [(int(m.group(1)), m.group(2)) for m in map(BISECT.search, err.splitlines()) if m]



## next step 
def ir_after(src, fn, flags, limit):
    out = Path("build/blame.ll")
    clang(src, flags, ["-mllvm", f"-opt-bisect-limit={limit}"], out=out,
          emit=["-S", "-emit-llvm"])
    text = out.read_text()
    m = re.search(rf"^define [^\n]*@{re.escape(fn)}\(.*?^\}}", text, re.S | re.M)
    return m.group(0).splitlines() if m else []


def main(src, fn, kind, flags):
    Path("build").mkdir(exist_ok=True)

    def at(limit):  # how many risky instructions with only 'limit' passes enabled
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
        print(f"IR of {fn} before -> after this pass:")
        diff = difflib.unified_diff(ir_after(src, fn, flags, lo), ir_after(src, fn, flags, hi),
                                    "before", "after", lineterm="", n=0)
        for line in diff:
            print("   " + line)
  
    if base > 0:
        print(f"{base} {kind}(s) exist even with no optimization passes:")
        print("-> front-end or backend (instruction selection / lowering).")
        for sw in BACKEND_SWITCHES:
           
            try:
                n = measure(src, fn, kind, flags, ["-mllvm", sw])
            except subprocess.CalledProcessError:
                continue  # switch not available for this target
            if n < full:
                print(f"   -mllvm {sw}: {full} -> {n}")
## works lets gooo