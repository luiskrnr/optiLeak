#!/usr/bin/env python3
"""Compile one C file for many compiler configs and count risky instructions.

Usage:
    python3 tools/scan.py <file.c> [extra compiler flags...]

Example:
    python3 tools/scan.py controls/select.c
    python3 tools/scan.py third_party/PQClean/crypto_kem/ml-kem-768/clean/verify.c \
        -Ithird_party/PQClean/common
"""
import re
import subprocess
import sys
from pathlib import Path

# (name, compiler command, architecture)
CONFIGS = [
    ("gcc",       ["gcc"],   "aarch64"),
    ("clang",     ["clang"], "aarch64"),
    ("clang-rv",  ["clang", "--target=riscv64-linux-gnu", "-ffreestanding"], "riscv64"),
    ("clang-rvz", ["clang", "--target=riscv64-linux-gnu", "-march=rv64gc_zicond",
                   "-ffreestanding"], "riscv64"),
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
# disassembly line: "   1c:   udiv  w0, w0, w1" -> captures "udiv"
INSN = re.compile(r"^\s*[0-9a-f]+:\s+(\S+)")


def mnemonics(obj):
    """Yield the instruction names in an object file."""
    out = subprocess.run(["llvm-objdump", "-d", "--no-show-raw-insn", str(obj)],
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        m = INSN.match(line)
        if m:
            yield m.group(1)


def main(src, extra):
    Path("build").mkdir(exist_ok=True)
    print(f"{'config':<11}" + "".join(f"{f:>9}" for f in FLAGS))
    for name, cmd, arch in CONFIGS:
        row = f"{name:<11}"
        for flag in FLAGS:
            obj = Path("build") / f"{Path(src).stem}_{name}{flag}.o"
            subprocess.run([*cmd, flag, *extra, "-c", src, "-o", str(obj)], check=True)
            ms = list(mnemonics(obj))
            divs = sum(1 for m in ms if DIV[arch].match(m))
            brs = sum(1 for m in ms if BRANCH[arch].match(m))
            row += f"{f'd{divs} b{brs}':>9}"
        print(row)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2:])