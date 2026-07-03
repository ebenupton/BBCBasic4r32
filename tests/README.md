# Self-test for the 65C02-optimised BASIC 4r32 ROM

`selftest.bas` is a self-checking BASIC program distilled from
`../bbc_basic_test_plan.md`. It covers integer and floating-point
arithmetic, the documented LN/ATN accuracy quirks (printed, not
asserted — compare against the baseline ROM's output), strings
(including zero-length stores, which exercise the L91EF string-store
path changed in Change 16), FOR/NEXT (bare NEXT, named NEXT, STEP up
and down, float loops, nesting), REPEAT/UNTIL, GOTO/GOSUB/ON,
PROC/FN (including recursion), READ/DATA/RESTORE, arrays, hex
formatting, and ON ERROR/ERR. It finishes with four TIME-based
benchmark loops (bare NEXT, integer increment, STR$ + string store,
REPEAT/UNTIL) and a `PASS=nn FAIL=nn` summary.

Expected result on both the baseline and optimised ROM: `PASS=52 FAIL=0`,
with `LN1000=6.90775639`, `LNB=3.07692308E-2`, `ATNB=0.753140099`
(these are the ROM's documented pre-existing values, not the
mathematically correct ones). Benchmark expectations (centiseconds,
Master 128): baseline B1=266 B2=355 B3=706 B4=670; with Change 19
(single-digit literal fast path) B2≈335 and B4≈653, others unchanged.

Error messages are compressed (Change 18): after any change to the
message dictionary, also run an error battery covering each entry —
LN(0), NEXT at top level, SQR(-1), DIM A(6000), PRINT ZZZ, DIM Q(-1),
READ with no DATA, PRINT "A"+1, LET 5, ON 1, 12 nested FORs, and
PRINT LEFT$("A")+ for the legacy "Missing ," pseudo-token.

## Running under jsbeeb (Master 128)

The ROM needs a 65C02, so use the Master model. `basic432.ssd` (built by
`tools/mkssd.py`, see below) contains the ROM image as `NEWROM` and the
self-test as a text file `STEST` that can be `*EXEC`d in.

1. Open https://bbc.godbolt.org/?model=Master (or a local jsbeeb with
   the Master model selected).
2. Load `tests/basic432.ssd` into drive 0 (Discs menu → local file).
3. Type:
   ```
   *SRLOAD NEWROM 8000 4 Q
   ?&2A5=&40
   *FX 142,4
   ```
   The `BASIC 4r32` banner (title `BASIC`) appears and it is now the current language, so
   error handling (BRK → REPORT) works normally.
4. `*EXEC STEST` — types the self-test in and runs it. Expect
   `PASS=52 FAIL=0` and benchmarks near B1=266 B2=337 B3=707 B4=661.

Why the poke: MOS 3.20 builds its ROM-type table at &02A1+bank at
reset, with the empty sideways-RAM banks unplugged, so a freshly
SRLOADed bank gets "This is not a language" from `*FX 142`. Writing
&40 (language bit only) into the bank-4 entry fixes that for the
session. Use &40, not &C0/&E0: registering the bank with the service
bit lets the MOS route service calls to it, which upsets the bundled
TERMINAL ROM's unknown-*-command handling in the emulator — `*SRLOAD`,
`*INFO` and `OSCLI` then hang in TERMINAL's poll loop. That happens
with the unmodified baseline ROM too (emulator environment issue, not
a ROM defect; the ROM's own service handler is fine — unit-tested via
`CALL &802C`). After a BREAK the poke is lost: repeat steps 3.

To rebuild the disc after changing the ROM or the test:

```
python3 -c "src=open('tests/selftest.bas').read().strip().split('\n'); \
  open('tests/selftest.txt','wb').write(('\r'.join(src)+'\rRUN\r').encode())"
tools/mkssd.py tests/basic432.ssd \
  NEWROM=disassembly/Basic432.bin,8000,8000 STEST=tests/selftest.txt
```
