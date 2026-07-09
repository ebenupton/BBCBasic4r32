# Self-test for the 65C02-optimised BASIC 4r32 ROMs

`selftest.bas` is a self-checking BASIC program distilled from
`../bbc_basic_test_plan.md`. It covers integer and floating-point
arithmetic, the formerly buggy LN/ATN values (asserted against the
correct results), strings (including zero-length stores), FOR/NEXT
(bare NEXT, named NEXT, STEP up and down, float loops, nesting),
REPEAT/UNTIL, GOTO/GOSUB/ON, PROC/FN (including recursion),
READ/DATA/RESTORE, arrays, hex formatting, and ON ERROR/ERR. It
finishes with four TIME-based benchmark loops (bare NEXT, integer
increment, STR$ + string store, REPEAT/UNTIL) and a `PASS=nn FAIL=nn`
summary.

Expected result: `PASS=55 FAIL=0` on both variants (the LN1000,
LNFIX and ATNFIX checks assert the mathematically correct values;
stock 4r32 scores `PASS=52`). Benchmark expectations (centiseconds,
Master 128): BASICV variant B1=318 B2=368 B3=712 B4=674, FAST
variant B1=266 B2=318 B3=703 B4=624 (a couple of centiseconds of
timer jitter is normal). For reference, stock 4r32 measures
B1=317 B2=367 B3=718 B4=669.

`whiletest.bas` (on the disc as `WTEST`, also `*EXEC`-able) is the
WHILE/ENDWHILE acceptance battery: expect `PASS=15 FAIL=0`.
`iftest.bas` (`ITEST`) is the block IF...THEN/ELSE/ENDIF battery
(BASICV variant only): expect `PASS=26 FAIL=0`.
`bsearch.bas` (`BSEARCH`) is a demo rather than a test: a binary
search over a sorted array using a multi-line WHILE with a nested
block IF/ELSE/ENDIF inside the ELSE branch. On the disc it is a
tokenised BASIC program (`bsearch.tok`, produced by the BASICV
ROM's own tokeniser, since the two-byte WHILE/ENDIF tokens exist in
no other tokeniser): `CHAIN "BSEARCH"` prints `13 found at index 6`;
change line 30 to a key not in the array (e.g. 14) for the
`not found` branch. It LOADs and LISTs only under the BASICV ROM.
Note that WHILE programs must be entered through the ROM's own
tokeniser (typed, `*EXEC`, or LOAD of a ROM-tokenised file) —
host-side tokenisers such as jsbeeb's `load_basic` do not know the
new tokens.

Error messages are stored compressed: after any change to the
message dictionary, also run an error battery covering each entry —
LN(0), NEXT at top level, SQR(-1), DIM A(6000), PRINT ZZZ, DIM Q(-1),
READ with no DATA, PRINT "A"+1, LET 5, ON 1, 12 nested FORs, and
PRINT LEFT$("A")+ for the legacy "Missing ," pseudo-token.

## Running under jsbeeb (Master 128)

The ROMs need a 65C02, so use the Master model. `basic432.ssd` (built
by `tools/mkssd.py`, see below) contains both build variants
(`BASICV` and `FAST`) and the self-test as a text file `STEST` that
can be `*EXEC`d in.

1. Open https://bbc.godbolt.org/?model=Master (or a local jsbeeb with
   the Master model selected).
2. Load `tests/basic432.ssd` into drive 0 (Discs menu → local file).
3. Type (substitute FAST for BASICV to test the other variant):
   ```
   *SRLOAD BASICV 8000 4 Q
   ?&2A5=&40
   *FX 142,4
   ```
   The `BASIC` banner appears and it is now the current language, so
   error handling (BRK → REPORT) works normally.
4. `*EXEC STEST` — types the self-test in and runs it. Expect
   `PASS=55 FAIL=0` on both variants. On the BASICV variant,
   `*EXEC WTEST` runs the WHILE/ENDWHILE battery (expect
   `PASS=15 FAIL=0`) and `*EXEC ITEST` the block IF/ELSE/ENDIF
   battery (expect `PASS=26 FAIL=0`). Type `NEW` between `*EXEC`
   runs — `*EXEC` merges over the resident program, and leftover
   lines from a previous suite wreck the next one in confusing ways.
5. RENUMBER is map-free in these ROMs (O(refs x lines), no
   `RENUMBER space` error, `Failed at` reports the referencing
   line's old number). Spot-check: type a few GOTO/GOSUB lines,
   RENUMBER 100,25, LIST.

Why the poke: MOS 3.20 builds its ROM-type table at &02A1+bank at
reset, with the empty sideways-RAM banks unplugged, so a freshly
SRLOADed bank gets "This is not a language" from `*FX 142`. Writing
&40 (language bit only) into the bank-4 entry fixes that for the
session. Use &40, not &C0/&E0: registering the bank with the service
bit lets the MOS route service calls to it, which upsets the bundled
TERMINAL ROM's unknown-*-command handling in the emulator — `*SRLOAD`,
`*INFO` and `OSCLI` then hang in TERMINAL's poll loop. That happens
with the unmodified baseline ROM too (emulator environment issue, not
a ROM defect). After a BREAK the poke is lost: repeat step 3.

To rebuild the disc after changing the ROM or the tests: `make disc`
(regenerate the .txt files from the .bas sources first if you edited
those — CR line endings plus a trailing RUN; see the git history of
this file for the one-liner).
