# Basic432_fast: BBC BASIC 4r32, tuned for speed

`roms/Basic432_fast.rom` is BBC BASIC 4r32 with the same language,
the LN/ATN accuracy fix, and a set of interpreter fast paths, still
in exactly 16K. It requires a 65C02 (Master 128, or a B fitted with
one). Build it from the single conditional source with
`beebasm -i disassembly/Basic432.asm -D BASICV=0` (see the Makefile).

## Where the space came from

Sophie Wilson's interpreter is extraordinarily dense; the usable slack
is in the cold code, not the hot code. The bytes were found by:

- **Error-message dictionary compression** (~40 bytes): the error
  strings share fragments (" range", "No ", "Too many ", " space",
  "Bad ", ...) which are factored into a small dictionary; messages
  become mixtures of literal characters and dictionary references,
  decoded only when an error is actually reported.
- **A map-free rewrite of RENUMBER** (~45 bytes): references are
  patched before the line headers are rewritten, resolving each
  target by walking the program and accumulating start+step per line.
  This trades O(refs x lines) time in an immediate-mode command for
  the entire old-number map — which also abolishes the
  `RENUMBER space` error.
- **Service-call frills stripped** (~37 bytes net): the ROM's `*HELP`
  text and unknown-*-command matcher are removed. `*BASIC` still
  works (the MOS selects languages by ROM type byte); `*HELP` simply
  no longer lists this ROM's version line.
- **ROM header trims** (~24 bytes): the title's NUL doubles as the
  version separator and the copyright string is the MOS-minimum
  `(C)`.
- **Cold-path extraction** (~50 bytes): repeated instruction
  sequences in the assembler, LIST, TRACE, RENUMBER and the
  PROC-definition scanner are folded into shared helpers and
  tail-calling wrappers. Each costs ~12 cycles at its call sites,
  which is why only paths executed at human or I/O speed were
  touched; three such merges that turned out to sit on warm statement
  paths (PROC dispatch, PROC argument binding, string-function
  argument fetch) were later re-inlined in this variant.
- **65C02 idioms and micro-restructures** (~25 bytes): PHY/PLY,
  BRA, STZ, a pointer-advance merge, and the classic
  `LDA #x / EQUB $2C / LDA #y` skip trick for two-entry constant
  loaders.

One layout constraint governs everything: the last few hundred bytes
of the ROM (from &BE95) hold a constant pool and tables that are
addressed by fixed low bytes with the high byte implied, so that
region is pinned at its original addresses; all savings and additions
happen below it, with a build-time assertion that the boundary hasn't
moved.

## What the space bought

The fast paths target what tight BASIC loops actually execute:

- **Resident integer variables (`@%`-`Z%`) in expressions.** These
  live at fixed page-4 addresses, but stock BASIC finds them through
  the general variable parser every time. A gate at the factor entry
  recognises `letter %` not followed by `(`, `!` or `?` and copies
  the value straight from page 4 into the integer accumulator.
- **... and in assignments.** The twin gate on the statement path
  recognises `X% =` and enters the assignment machinery with the
  page-4 slot address directly, skipping the general name parse.
- **Single-digit numeric literals.** A digit whose successor cannot
  continue a numeric literal is delivered immediately, skipping the
  full mantissa/exponent parser (~70 cycles on the commonest literal
  there is).
- **Forward line search for GOTO/GOSUB/THEN-line.** When the target
  line number is greater than or equal to the current line's, the
  search starts from the current line instead of the top of the
  program. A backward jump falls back to the full search, so a miss
  can never turn a valid target into an error.
- **PROC/FN call-site cache.** One cache entry remembers the last
  call site (text pointer key) and its resolved definition; a
  same-site call — the shape of every PROC in a loop, and of
  recursion — skips the name lookup entirely. The cache is
  invalidated whenever variables are cleared. Procedure calls run
  ~36% faster than stock.
- **Statement-advance entry fast path.** The routine that steps over
  a statement's terminator ran a wasted pre-decrement dance on entry;
  the common no-leading-space case now tests the character directly
  (3 cycles per statement executed via the main loop).
- **Assorted micro-wins** carried by both variants: 2 cycles per
  string store, 7 per printed digit, 4 per service call.
- **The LN/ATN fix** (see the README): LN, ATN, ASN and ACS return
  correct values.

## Benchmarks

ClockSp 2.10 (J.G.Harston), Master 128 under jsbeeb, fresh boot, ROM
in sideways RAM. Figures are effective MHz relative to a 2MHz BBC B;
higher is better. The stock column is the unmodified 4r32 image run
the same way. (For context, the Master's built-in BASIC 4.00 averages
2.49 on the same setup — 4r32 itself was already a substantial
speedup, mostly in the transcendentals.)

| ClockSp test        | stock 4r32 | FAST | change |
|---------------------|-----------|------|--------|
| Real REPEAT loop    | 2.36 | 2.39 | +1% |
| Variant REPEAT loop | 2.36 | 2.37 | — |
| Integer REPEAT loop | 2.24 | 2.52 | **+12.5%** |
| Real FOR loop       | 2.35 | 2.52 | **+7%** |
| Variant FOR loop    | 2.36 | 2.50 | **+6%** |
| Integer FOR loop    | 2.18 | 2.60 | **+19%** |
| Trig/Log test       | 7.00 | 6.92 | -1% |
| String manipulation | 2.66 | 2.70 | +1.5% |
| Procedure call      | 2.12 | 2.89 | **+36%** |
| GOSUB call          | 2.07 | 2.08 | — |
| **Unweighted average** | **2.77** | **2.94** | **+6%** |

The self-test's timing loops (centiseconds, lower is better; 2MHz
Master 128):

| loop | stock 4r32 | FAST | change |
|------|-----------|------|--------|
| B1: bare `FOR I%=1 TO 20000:NEXT` | 317 | 266 | **-16%** |
| B2: `A%=A%+1` in a 5000-iteration FOR | 367 | 318 | **-13%** |
| B3: `A$=STR$(I%)` x2000 | 718 | 703 | -2% |
| B4: `REPEAT S%=S%+1 UNTIL` x5000 | 669 | 624 | **-7%** |

## Compatibility notes

- The language is unchanged: any BASIC 4 program runs identically,
  and `PASS=55 FAIL=0` on the `tests/selftest.bas` battery (which
  asserts the *correct* LN/ATN values — stock 4r32 scores 52).
- `*HELP` no longer prints the ROM's version line.
- `RENUMBER` of a very large, reference-heavy program takes longer
  than stock (it re-walks the program per reference), and the
  `RENUMBER space` error no longer exists.
- The `COLOR` spelling of `COLOUR` is accepted, as in stock.
- Remaining known slow spots vs stock, all statement-level:
  ~12 cycles on statements that evaluate an argument expression
  through the shared copy at L9C0A (e.g. `MODE`, `COLOUR`), and on
  the `#channel` parse of file operations. Error reporting decodes
  compressed messages (slower, but errors are exceptional).

`tests/README.md` documents how to load the ROM and run the suites
under jsbeeb.
