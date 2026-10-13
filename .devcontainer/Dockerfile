FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang llvm valgrind python3 python3-yaml git make gdb ca-certificates \
 && rm -rf /var/lib/apt/lists/*