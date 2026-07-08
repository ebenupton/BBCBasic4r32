# BBCBasic4r32
Here's an annotated disassembly of BBC Basic 4r32, the final version of Acorn's 6502 Basic interpreter,
suitable for assembly with beebasm.

Also here are some explorations of the algorithms used to calculate the log and trig functions,
with an aim to understanding the bugs mentioned in
[this thread](https://stardot.org.uk/forums/viewtopic.php?t=10111) on StarDot:

Function       | Basic 4r32    | Correct value
-------------- | ------------- | -------------
P.LN(1.03125)  | 3.07692308E-2 | 3.07716587E-2
P.ASN(0.03125) | 3.126527E-2   | 3.12550885E-2
P.ACS(0.03125) | 1.53953106    | 1.53954124
P.ATN(0.9375)  | 0.753140099   | 0.753151281

[Here's a c program](https://github.com/hoglet67/BBCBasic4r32/blob/master/c/log_test.c)
implementing the same algorithms as the Basic.

We were able to understand the bug and fix it. **As of Change 22 the
fix is applied in the ROM source, so both pre-built variants in
`roms/` return the correct values** (verified: LN(1000)=6.90775528,
LN(1.03125)=3.07716587E-2, ATN(0.9375)=0.753151281,
ASN(0.03125)=3.12550885E-2, ACS(0.03125)=1.53954124). For reference,
the original RAM-patch demonstration against an unmodified ROM at
&8000 was:
```
   10  T=1.03125
   20  REPORT
   30  PRINT
   40  PROCtest(T)
   50  P%=&A8CC
   60 [OPT 0
   70  CLC
   80  ADC #&F0
   90  .loop
  100  ADC #&0A
  110  DEY
  120  BPL loop
  130 ]
  140  PROCtest(T)
  150  END
  160  DEF PROCtest(A)
  170  PRINT A
  180  PRINT LN(A)
  190  PRINT A-EXP(LN(A))
  200  PRINT
  210  ENDPROC
```

Only six bytes need to be changed, the bug being in computing an index into a table,
which broke with entries near the end of a page.
See [these notes](https://github.com/hoglet67/BBCBasic4r32/blob/master/disassembly/examples/ln_1000/notes.txt#L120).

The original code:
```
        CLC
.LA8CD
        ADC     #$0A
        DEY
        BPL     LA8CD
        ADC     #$F1
```

Our fixed version:
```
        CLC
        ADC     #$F0
.LA8CF
        ADC     #$0A
        DEY
        BPL     LA8CF
```

This fixed code would now fail for entries near the beginning of a page, but that
doesn't happen.

We found it interesting that the same bug affected both LN and ATN, the reason being that both use the same coefficients (but with different signs) and therefore the same tables. ACS and ASN are computed from ATN, so they inherit the bug, and the fix.

## Structured programming: WHILE and block IF/ELSE/ENDIF

The `while` variant of the ROM adds two BASIC V-style structured
constructs to BASIC IV, still within the original 16K:

- `WHILE <expr>` ... `ENDWHILE` — condition re-evaluated at
  ENDWHILE, so the forward scan for the matching ENDWHILE runs at
  most once per loop; nests freely with itself, FOR/NEXT and
  REPEAT/UNTIL (it shares the REPEAT stack and its depth limit).
- `IF <expr> THEN` at the end of a line ... `ELSE` (first on a
  line) ... `ENDIF` — multi-line IF with an optional ELSE clause and
  full nesting. `THEN` as the last item on the line is what opens a
  block, exactly as in BASIC V; single-line
  `IF ... THEN ... ELSE ...` is completely unchanged.

Both are real tokens, entered through the ROM's tokeniser (typed,
`*EXEC`, or LOAD of a file it saved), abbreviations `W.`, `ENDW.`,
`ENDI.` included, and LIST round-trips them. Programs written with
them behave identically under BASIC V on the Archimedes. A taste —
`tests/basic432.ssd` carries this as a tokenised program
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

The space came from inside the ROM itself: reverting this project's
own speed features, a service-call frill strip, a map-free rewrite of
RENUMBER (which as a side effect abolishes the `RENUMBER space`
error), and a long tail of byte-scavenging described in
`OPTIMISATIONS.md` (Changes 21, 23–27). Every token code was already
taken, so WHILE, ENDWHILE and ENDIF are two-byte tokens behind an OFF
($87) escape prefix — unrepresentable in any pre-existing program,
and invisible to host-side tokenisers, which is why the constructs
must be entered through the ROM. New errors: `No REPEAT` (43, stray
ENDWHILE), `Too many REPEATs` (44), `No ENDWHILE` (46), `No ENDIF`
(47), matching BASIC IV's spare error-number space.

## Pre-built ROMs

Two ready-to-use 16K ROM images built from `disassembly/Basic432.asm`
(see `OPTIMISATIONS.md` for what each contains, and the `Makefile`
for how they are built and verified):

- `roms/Basic432_while.rom` — WHILE/ENDWHILE and block IF/ELSE/ENDIF
  as above, plus the LN/ATN fix; interpreter speed is within a few
  cycles per statement of the original 4r32
- `roms/Basic432_fast.rom` — no new constructs, instead the speed
  features (faster tight FOR/NEXT loops, single-digit constants,
  string stores, and direct page-4 access for `@%`-`Z%` in
  expressions — integer REPEAT loops run ~12% faster than stock
  4r32 on ClockSp), plus the LN/ATN fix

Both require a 65C02 (Master 128, or a B with a 65C02 fitted). The
two feature sets do not fit in 16K together — that trade and every
byte of how it was paid for are documented in `OPTIMISATIONS.md`.
`tests/README.md` has a recipe for running the ROMs and their test
suites under jsbeeb's Master 128.
