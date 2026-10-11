#!/usr/bin/env python3
"""Compile one C file for many compiler configs and count risky instructions."""
import re
import subprocess
import sys
from pathlib import Path

# (name, compiler command, architecture)
CONFIGS = [
    ("gcc",      ["gcc"],   "aarch64"),
    ("clang",    ["clang"], "aarch64"),
    ("clang-rv", ["clang", "--target=riscv64-linux-gnu", "-ffreestanding"], "riscv64"),
]
FLAGS = ["-O0", "-O1", "-O2", "-O3", "-Os"]

# variable-time division instructions per architecture
DIV = {
    "aarch64": re.compile(r"^[us]div$"),
    "riscv64": re.compile(r"^(div|divu|rem|remu)w?$"),
}
# conditional branches per architecture
BRANCH = {
    "aarch64": re.compile(r"^(b\.\w+|cbn?z|tbn?z)$"),
    "riscv64": re.compile(r"^(beq|bne|blt|bge|bltu|bgeu|beqz|bnez|blez|bgez|bltz|bgtz)$"),
}
# a disassembly line: "   1c:   udiv  w0, w0, w1" -> captures "udiv"
INSN = re.compile(r"^\s*[0-9a-f]+:\s+(\S+)")


def mnemonics(obj):
    """Yield the instruction names in an object file."""
    out = subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", str(obj)],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        m = INSN.match(line)
        if m:
            yield m.group(1)


def main(src):
    Path("build").mkdir(exist_ok=True)
    print(f"{'config':<10}" + "".join(f"{f:>9}" for f in FLAGS))
    for name, cmd, arch in CONFIGS:
        row = f"{name:<10}"
        for flag in FLAGS:
            obj = Path("build") / f"{Path(src).stem}_{name}{flag}.o"
            subprocess.run([*cmd, flag, "-c", src, "-o", str(obj)], check=True)
            ms = list(mnemonics(obj))
            divs = sum(1 for m in ms if DIV[arch].match(m))
            brs = sum(1 for m in ms if BRANCH[arch].match(m))
            row += f"{f'd{divs} b{brs}':>9}"
        print(row)


if __name__ == "__main__":
    main(sys.argv[1])