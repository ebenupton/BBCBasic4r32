# Basic432_basicv: BBC BASIC 4r32 with BASIC V structured programming

`roms/Basic432_basicv.rom` is BBC BASIC 4r32 extended with the two
BASIC V structured-programming constructs that BASIC IV most
obviously lacks — `WHILE`/`ENDWHILE` loops and multi-line
`IF`/`ELSE`/`ENDIF` — still in exactly 16K, at essentially stock
speed, with the LN/ATN accuracy fix. It requires a 65C02 (Master 128,
or a B fitted with one). Build it with
`beebasm -i disassembly/Basic432.asm -D BASICV=1` (see the Makefile).

## The features

- **`WHILE <expr>` ... `ENDWHILE`** — the condition is re-evaluated
  at `ENDWHILE`, so the forward scan for the matching `ENDWHILE` runs
  at most once per loop, not once per iteration. Nests freely with
  itself, `FOR`/`NEXT` and `REPEAT`/`UNTIL` (it shares the REPEAT
  stack and its depth limit).
- **`IF <expr> THEN`** at the end of a line ... **`ELSE`** (first on
  a line) ... **`ENDIF`** — multi-line IF with an optional ELSE
  clause and full nesting. `THEN` as the last item on the line is
  what opens a block, exactly as in BASIC V; single-line
  `IF ... THEN ... ELSE ...` is completely unchanged.

Both are real tokens, entered through the ROM's tokeniser (typed,
`*EXEC`, or `LOAD` of a file it saved), with the abbreviations `W.`,
`ENDW.` and `ENDI.`, and `LIST` round-trips them. Programs written
with them behave identically under BASIC V on the Archimedes. A
taste — `tests/basic432.ssd` carries this as a tokenised program
(`CHAIN "BSEARCH"`):

```
   10 DIM A%(9)
   20 FOR I% = 0 TO 9: A%(I%) = I%*2+1: NEXT
   30 key% = 13
   40 lo% = 0: hi% = 9: found% = -1
   50 WHILE (lo% <= hi%) AND (found% = -1)
   60   mid% = (lo% + hi%) DIV 2
   70   IF A%(mid%) = key% THEN
   80     found% = mid%
   90   ELSE
  100     IF A%(mid%) < key% THEN
  110       lo% = mid% + 1
  120     ELSE
  130       hi% = mid% - 1
  140     ENDIF
  150   ENDIF
  160 ENDWHILE
  170 IF found% = -1 THEN
  180   PRINT key%; " not found"
  190 ELSE
  200   PRINT key%; " found at index "; found%
  210 ENDIF
```

Every one-byte token code was already taken in BASIC 4, so `WHILE`,
`ENDWHILE` and `ENDIF` are two-byte tokens behind an escape prefix
(the otherwise line-initial `OFF` token, $87). Two consequences:
they are unrepresentable in any pre-existing program (no false
matches), and they are invisible to host-side tokenisers — programs
using them must be entered through this ROM (jsbeeb's own
`load_basic`, BeebEm's paste-as-BASIC etc. do not know the tokens).

New errors, using BASIC IV's spare error numbers: `No REPEAT` (43,
stray `ENDWHILE`), `Too many REPEATs` (44, the shared loop stack is
full), `No ENDWHILE` (46) and `No ENDIF` (47) for an unterminated
false branch.

## Where the space came from

The constructs cost about 250 bytes (keyword-table entries, the token
dispatcher, a unified forward scanner for both constructs' false
paths, the executed-ELSE hook, loop machinery and four error
messages). The ROM had no free space, so:

- **This fork's own speed features were reverted** in this variant —
  the resident-integer fast paths, the GOTO/GOSUB forward search and
  the PROC/FN call-site cache described in [FAST.md](FAST.md) are
  conditionally assembled out. That is the fundamental trade: the
  16K image can hold the speed features or the language features,
  not both.
- The same shared savings as the fast variant: error-message
  dictionary compression, the map-free RENUMBER rewrite, the
  service-call frill strip, ROM header trims, cold-path extraction
  into shared helpers, and 65C02 idioms (see FAST.md for details).

## Performance

Close enough to stock 4r32 that ClockSp cannot reliably tell them
apart. Same setup as FAST.md (ClockSp 2.10, Master 128 under jsbeeb,
fresh boot; effective MHz vs a 2MHz BBC B, higher is better):

| ClockSp test        | stock 4r32 | BASICV |
|---------------------|-----------|--------|
| Real REPEAT loop    | 2.36 | 2.36 |
| Variant REPEAT loop | 2.36 | 2.36 |
| Integer REPEAT loop | 2.24 | 2.24 |
| Real FOR loop       | 2.35 | 2.35 |
| Variant FOR loop    | 2.36 | 2.35 |
| Integer FOR loop    | 2.18 | 2.18 |
| Trig/Log test       | 7.00 | 7.00 |
| String manipulation | 2.66 | 2.67 |
| Procedure call      | 2.12 | 2.09 |
| GOSUB call          | 2.07 | 2.03 |
| **Unweighted average** | **2.77** | **2.76** |

Self-test timing loops (centiseconds, lower is better):

| loop | stock 4r32 | BASICV |
|------|-----------|--------|
| B1: bare `FOR I%=1 TO 20000:NEXT` | 317 | 318 |
| B2: `A%=A%+1` in a 5000-iteration FOR | 367 | 368 |
| B3: `A$=STR$(I%)` x2000 | 718 | 712 |
| B4: `REPEAT S%=S%+1 UNTIL` x5000 | 669 | 674 |

The residual costs, all bounded and by design: the statement
dispatcher checks for the $87 escape and a statement-position `ELSE`
(~4 cycles per non-keyword statement — the B4 delta above), and
three cold-path merges still sit on warm paths (~12 cycles each on
PROC/FN dispatch, PROC argument binding, and string-function argument
fetch — the PROC and GOSUB rows above). The interpreter core —
expression evaluation, assignment, `UNTIL`, `NEXT`, the real-variable
store — runs the original code. And as in the fast variant, string
stores, digit output and service calls are a few cycles *faster*
than stock, which is why B3 wins.

The `WHILE` loop itself runs at `REPEAT` speed plus one condition
evaluation per iteration (the condition is re-evaluated at
`ENDWHILE`, where `REPEAT` evaluates at `UNTIL`); the forward scan on
loop entry with a false condition is a fast tokenised-byte scan, once
per loop.

## Compatibility notes

- Any BASIC 4 program that doesn't use the new keywords as variable
  names runs identically (`WHILEX=42` still parses as the variable
  `WHILEX` — the new keywords are only recognised via the tokeniser's
  usual longest-match rules). `PASS=55 FAIL=0` on
  `tests/selftest.bas`, plus dedicated batteries for the new
  constructs: `tests/whiletest.bas` (15 checks) and `tests/iftest.bas`
  (26 checks, including nesting, ELSE binding, strings/REMs
  containing the keywords, and the new errors).
- `*HELP`, `RENUMBER` and `COLOR` notes as in FAST.md.
- Programs SAVEd with the new tokens LOAD and LIST only under this
  ROM.

`tests/README.md` documents how to load the ROM and run the suites
under jsbeeb.
