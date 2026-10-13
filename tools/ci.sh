#!/usr/bin/env bash
# Run optiLeak's checks and write a Markdown report.
# Locally report goes to  terminal; in GitHub Actions to the job summary.
set -euo pipefail
cd "$(dirname "$0")/.."            # always run from repo root
OUT=${GITHUB_STEP_SUMMARY:-/dev/stdout}

run() {
  echo "### \`blame.py $*\`" >>"$OUT"
  echo '```' >>"$OUT"
  python3 tools/blame.py "$@" >>"$OUT" 2>&1
  echo '```' >>"$OUT"
}

echo "## optiLeak on $(uname -m) – $(clang --version | head -1)" >>"$OUT"

# 1. Positive control first: if  oracle misses a known leak, no result counts
#    Fail-closed: require positive evidence, never just the absence of a message.
control=$(python3 tools/blame.py controls/leaky.c ctl_leaky secret \
            --harness controls/harness.c -O2 -Iinclude 2>&1) || true
if ! grep -qE "^ctl_leaky: [1-9][0-9]* secret" <<<"$control"; then
  echo "::error::positive control not detected - valgrind oracle is broken"
  echo "$control"
  exit 1
fi
echo "Positive control detected " >>"$OUT"

# 2. known compiler-introduced leaks
run controls/frommsg.c ctl_frommsg secret --harness controls/harness_frommsg.c -Os -Iinclude
run controls/frommsg.c ctl_frommsg branch -O2
run controls/select.c ctl_select branch -O2 --target=riscv64-linux-gnu -ffreestanding
run controls/compress.c ctl_compress1 div -O0