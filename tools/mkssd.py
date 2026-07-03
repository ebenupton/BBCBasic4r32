#!/usr/bin/env python3
"""Build a single-sided 80-track Acorn DFS disc image (.ssd).

Usage:
    mkssd.py OUTPUT.ssd NAME=path[,load[,exec]] ...

Each argument adds one file. NAME is the DFS name (up to 7 chars,
optionally prefixed "d." for directory d). load/exec are hex addresses
and default to 0 (use 8000 for a sideways ROM image).

Example (build the test disc for the 65C02 BASIC ROM):
    tools/mkssd.py tests/basic432.ssd \
        NEWROM=disassembly/Basic432.bin,8000,8000 \
        STEST=tests/selftest.txt
"""
import sys


def build(files, title="B432TEST"):
    ntracks = 80
    disc = bytearray(ntracks * 10 * 256)
    t = (title + " " * 12)[:12]
    disc[0:8] = t[:8].encode()
    disc[256:260] = t[8:12].encode()
    disc[260] = 1                      # cycle count
    disc[261] = len(files) * 8         # catalogue entries * 8
    nsect = ntracks * 10
    disc[262] = (nsect >> 8) & 3       # boot option 0 (no action)
    disc[263] = nsect & 0xFF
    sector = 2
    for i, (name, dirc, load, exe, data) in enumerate(files):
        off = 8 + i * 8
        disc[off:off + 7] = (name + "       ")[:7].encode()
        disc[off + 7] = ord(dirc)
        o2 = 256 + 8 + i * 8
        ln = len(data)
        disc[o2 + 0] = load & 0xFF
        disc[o2 + 1] = (load >> 8) & 0xFF
        disc[o2 + 2] = exe & 0xFF
        disc[o2 + 3] = (exe >> 8) & 0xFF
        disc[o2 + 4] = ln & 0xFF
        disc[o2 + 5] = (ln >> 8) & 0xFF
        disc[o2 + 6] = ((((exe >> 16) & 3) << 6) | (((ln >> 16) & 3) << 4)
                       | (((load >> 16) & 3) << 2) | ((sector >> 8) & 3))
        disc[o2 + 7] = sector & 0xFF
        disc[sector * 256: sector * 256 + ln] = data
        sector += (ln + 255) // 256
    return bytes(disc)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out = sys.argv[1]
    files = []
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        parts = rest.split(",")
        path = parts[0]
        load = int(parts[1], 16) if len(parts) > 1 else 0
        exe = int(parts[2], 16) if len(parts) > 2 else load
        dirc = "$"
        if len(name) > 2 and name[1] == ".":
            dirc, name = name[0], name[2:]
        data = bytearray(open(path, "rb").read())
        files.append((name, dirc, load, exe, data))
    open(out, "wb").write(build(files))
    print(f"wrote {out}: " + ", ".join(f[0] for f in files))


if __name__ == "__main__":
    main()
