#!/usr/bin/env python3
"""find which LLVM optimization pass introduces a timing leak into a function

Usage:
    python3 tools/blame.py <file.c> <function> <branch|div> [clang flags...]

Example:
    python3 tools/blame.py controls/select.c ctl_select branch \
        -O2 --target=riscv64-linux-gnu -ffreestanding
"""