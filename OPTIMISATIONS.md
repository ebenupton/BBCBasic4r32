# BBC BASIC 4r32: 65C02 Optimisations

## Introduction

BBC BASIC 4r32, the final revision of Acorn's 6502 BASIC interpreter,
is a remarkable piece of software engineering. Sophie Wilson packed a
full-featured floating-point BASIC — with IEEE-style 5-byte reals, a
recursive-descent expression parser, transcendental functions, assembler,
and operating system interface — into a single 16 KB ROM, while
maintaining the careful register and flag discipline that makes 6502
code fast. The code is dense but never obscure; nearly every instruction
earns its keep, and the architecture is clean enough that forty years
later the whole ROM can be read, understood, and reassembled from a
single annotated source file. It is a masterclass in economy.

This memo describes 20 changes to the ROM, targeting the 65C02. They
fall into seven categories (byte-saving, space-skip restructuring, the
bare-NEXT fast path, the NEXT continuation optimisation, second-round
byte savings, a bug fix plus error-message compression, and a
single-digit literal fast path):

**Byte-saving changes** (freeing 18 bytes): These exploit 65C02
instructions (PHY/PLY, BRA), dead code removal, a register substitution,
and a subroutine merge to shrink the ROM without costing execution time
on any hot path.

**Space-skip restructuring** (spending 1 of those bytes): One
space-skipping loop (L9C16, the assignment parser) is restructured to
use INY in the inner loop instead of INC zp / LDY zp, saving 6 cycles
per space character skipped. Five further candidates (Changes 6–10)
are documented below but not applied due to Y or X register conflicts
with their callers — see their entries and `tools/liveness.py` for
details.

**Bare-NEXT fast path** (spending 13 of those bytes): The NEXT handler
is augmented with an inline check for end-of-line ($0D) or colon
($3A), allowing the tightest `FOR I%=1 TO N: NEXT:` loops to skip
the full variable-name parser entirely, saving approximately 46 cycles
per iteration.

**NEXT continuation optimisation** (spending the remaining 4 bytes):
The NEXT loop-continuation path at LB5CF is optimised to use the
escape-check-only entry point L9C8E (instead of L9C8A which also sets
L0A), sets L0A and Y inline, and enters the interpreter dispatch loop
at L90D2 directly, saving 3 cycles per NEXT iteration by avoiding
redundant loads.

**Second-round byte savings** (Changes 15–16, freeing 4 more bytes):
a second dead-code removal (an unreachable LDA L31 after an RTS), and
removal of a redundant CPY #$00 in the string-store path, enabled by
reordering the two loads in LBE6B so the routine returns with Z/N
reflecting Y instead of A. All freed bytes flow into a SKIPTO pool
before LBE95, pinning the page-$BF floating-point constant pool (which
is addressed via #LO(...) immediates with an implied high byte of $BF,
and whose in-page layout the LN/ATN table-index code is sensitive to)
at its original address — see "Free-space pool" below.

**Bug fix and error-message compression** (Changes 17–18): Change 17
fixes a latent detokeniser bug exposed by the earlier byte-count
changes (a hard-coded keyword-table address in LBD77 that broke LIST
of AND and ABS). Change 18 compresses the BRK error-message texts with
an 11-entry substring dictionary and a 44-byte expander hooked into
REPORT's print loop, recovering 40 bytes net.

**Single-digit decimal-literal fast path** (Change 19, spending 43 of
those bytes): the factor evaluator delivers a single-digit integer
constant directly when the next character cannot continue a numeric
literal, bypassing the full float-capable parser at LA2DD. Saves ~72
cycles per single-digit constant — `A%=A%+1` loops run ~5% faster —
at a cost (after Change 20) of only ~8 cycles on multi-digit, decimal
or exponent literals.

Net effect: the ROM uses all 16384 bytes exactly, of which 1 byte
remains free in the SKIPTO pool. Assignment parsing benefits from
faster space-skipping. Tight FOR/NEXT loops with bare `NEXT` (followed
by `:` or end-of-line) save approximately 49 cycles per iteration.
String assignment saves 2 cycles per store, and single-digit constants
in expressions evaluate ~72 cycles faster.

All changes target the 65C02 and preserve the original semantics.

---

## Change 1: PHY/PLY in service call handler

**Location:** Lines 173–174 and 220–221 (label L802C)

**Rationale:** The service call entry point saves and restores Y via
the two-instruction sequences TYA/PHA and PLA/TAY. The 65C02 provides
PHY and PLY which do the same thing in one byte and one fewer cycle each.

**Saves:** 2 bytes, 4 cycles per service call.

```diff
 .L802C
         PHA
         TAX
-        TYA
-        PHA
+        PHY
         CPX     #$09
```

```diff
 .L806A
-        PLA
-        TAY
+        PLY
         LDX     LF4
         PLA
         RTS
```

---

## Change 2: LA2CC — use Y register instead of X push/pull

**Location:** Lines 6694–6700 (label LA2CC)

**Rationale:** The number-to-string character output routine saves and
restores X around an indexed store to the output buffer at $0600. Since
all 16 callers of LA2CC/LA2CA/LA2C9 do not depend on Y being preserved,
we can use Y as the index register instead, eliminating the PHX/PLX pair.

**Saves:** 2 bytes, 7 cycles per digit/character output.

```diff
 .LA2CC
-        PHX
-        LDX     L36
-        STA     L0600,X
-        PLX
+        LDY     L36
+        STA     L0600,Y
         INC     L36
         RTS
```

---

## Change 3: JMP → BRA in service call handler

**Location:** Line 193 (within L8040, address ~$8049)

**Rationale:** The forward jump to L806A is within BRA range
(offset ~ +31). BRA is one byte shorter than JMP on 65C02.

**Saves:** 1 byte, 0 cycles.

```diff
         JSR     OSBYTE

-        JMP     L806A
+        BRA     L806A
```

---

## Change 4: JMP → BRA in OSCLI handler

**Location:** Line 9387 (address ~$B047)

**Rationale:** The forward jump to LB0B0 is within BRA range
(offset ~ +103). BRA is one byte shorter.

**Saves:** 1 byte, 0 cycles.

```diff
         JSR     L995A

-        JMP     LB0B0
+        BRA     LB0B0
```

---

## Change 5: Remove dead RTS

**Location:** Line 6707 (between JMP L82DD and label LA2DD)

**Rationale:** The RTS at line 6707 immediately follows an unconditional
JMP and has no label — it is unreachable dead code.

**Saves:** 1 byte.

```diff
         CLC
         LDA     #$FF
         JMP     L82DD

-        RTS
-
 .LA2DD
```

---

## Change 6: L8F92 — variable-area space-skip restructure

**Location:** Lines 2852–2860 (label L8F92), 15 callers

**Status: NOT APPLIED.** Liveness analysis found 4 callers that read
Y after JSR L8F92 returns (lines 8773, 8840, 10541, 10585). The
restructured loop returns Y pointing one past the non-space character;
these callers expect Y to point AT it. See `tools/liveness.py` for
the automated analysis.

**Would cost:** 1 byte. **Would save:** 6 cycles per space (15 callers).

```diff
 .L8F92
         LDY     L1B
-        INC     L1B
-        LDA     (L19),Y
+.L8F94
+        LDA     (L19),Y
+        INY
         CMP     #$20
-        BEQ     L8F92
+        BEQ     L8F94
+        STY     L1B

 .L8F9C
         RTS
```

---

## Change 7: L8F9D — program-text space-skip restructure

**Location:** Lines 2862–2870 (label L8F9D), 28 callers

**Status: NOT APPLIED.** Liveness analysis found 8 callers that read
Y after JSR L8F9D returns (lines 2136, 3438, 3458, 3630, 4114, 9338,
10083/10088, 10698). Same Y-pointing issue as Change 6. See
`tools/liveness.py` for the automated analysis.

**Would cost:** 1 byte. **Would save:** 6 cycles per space (28 callers).

```diff
 .L8F9D
         LDY     L0A
-        INC     L0A
-        LDA     (L0B),Y
+.L8F9F
+        LDA     (L0B),Y
+        INY
         CMP     #$20
-        BEQ     L8F9D
+        BEQ     L8F9F
+        STY     L0A

 .L8FA7
         RTS
```

---

## Change 8: L90D0/L90D2 — statement dispatch space-skip restructure

**Location:** Lines 3110–3116 (labels L90D0, L90D2)

**Status: NOT APPLIED.** After the space-skip, the inline code at
L90EA falls through to L99D6, which executes `STY L1B` and then
`INY / LDA (L19),Y`. Both uses expect Y to point AT the non-space
character, not one past it. The restructured loop leaves Y pointing
one past, breaking variable parsing (e.g. `PRINT 1` and `T=TIME`).
Adding a compensating DEY after the loop would negate the performance
benefit of the restructuring.

**Rationale:** This is the statement dispatch loop — the hottest code
in the interpreter, executed for every BASIC statement. The same
LDY/INC-to-INY restructuring applies in principle, but the inline
callers' Y register invariant makes it unsuitable here.

**Would cost:** 1 byte. **Would save:** 6 cycles per space (every statement).

```diff
 .L90D0
         LDY     L0A
 .L90D2
-        INC     L0A
         LDA     (L0B),Y
+        INY
         CMP     #$20
-        BEQ     L90D0
+        BEQ     L90D2
+        STY     L0A

         CMP     #$CF
```

---

## Change 9: LA06F/LA070 — expression operator scan + space-skip restructure

**Location:** Lines 6207–6223 (labels LA06F, LA070, LA081)

**Status: NOT APPLIED.** The TAX/TXA refactoring changes the return
contract: the original code returns with X = the scanned character
(via TAX before PLA), allowing callers to inspect what terminated the
expression. The restructured version overwrites X with the saved
expression result (via TXA), losing the scanned character. The
space-skip restructuring also has the same Y-pointing issue as
Changes 6–8, but the X register contract change is the primary reason
this cannot be applied.

**Would cost:** 1 byte. **Would save:** 6 cycles per space + 5 cycles
unconditionally (every expression operator check).

---

## Change 10: LAD78 — factor evaluator space-skip restructure

**Location:** Lines 8822–8827 (label LAD78), 12 callers

**Status: NOT APPLIED.** After the space-skip, the inline code at
LADAC falls through to L99D8, which executes `INY / LDA (L19),Y`.
This expects Y to point AT the non-space character so that INY
advances to the next character. The restructured loop leaves Y
pointing one past, causing the read to skip a character. Adding a
compensating DEY after the loop would negate the performance benefit.

**Rationale:** The factor evaluator is entered on every numeric literal,
variable reference, function call, and sub-expression. The same
INY restructuring applies in principle, but the inline callers' Y
register invariant makes it unsuitable here.

**Would cost:** 1 byte. **Would save:** 6 cycles per space (12 callers).

```diff
 .LAD78
         LDY     L1B
-        INC     L1B
-        LDA     (L19),Y
+.LAD7A
+        LDA     (L19),Y
+        INY
         CMP     #$20
-        BEQ     LAD78
+        BEQ     LAD7A
+        STY     L1B

         CMP     #$2D
```

---

## Change 11: L9C16 — assignment parsing space-skip restructure

**Location:** Lines 5317–5322 (label L9C16), 3 callers

**Rationale:** This space-skip is in the assignment/equality parsing
path, executed for every LET, implicit LET, and `=` in expressions.
The same INY restructuring applies.

**Costs:** 1 byte. **Saves:** 6 cycles per space (3 callers).

```diff
 .L9C16
         LDY     L1B
-        INC     L1B
-        LDA     (L19),Y
+.L9C18
+        LDA     (L19),Y
+        INY
         CMP     #$20
-        BEQ     L9C16
+        BEQ     L9C18
+        STY     L1B

         CMP     #$3D
```

---

## Change 12: L9CB8 — pointer-advance merge via CLC/TYA swap

**Location:** Lines 5402–5458 (labels L9C80, L9CB8, L9CC5)

**Rationale:** L9CB8 is a 12-byte routine that advances the program
pointer (L0B/L0C) by A bytes, sets L0A to 1, and returns. It is
nearly identical to the body of L9C80, which does the same thing but
also checks the bit-7 flag at LFF. L9CB8 has two callers: `JSR L9CB8`
at line 3902, and `LDA #$03 / fall-through` from L9CB6 at line 5446.

By swapping the order of CLC and TYA at L9C80, we create a new entry
point L9C81 (the CLC) that L9CB8 can branch to. L9C80 becomes
TYA/CLC/ADC... instead of CLC/TYA/ADC... — this is safe because TYA
does not affect the carry flag.

L9CB8 is within BRA range of L9C81 (offset ~ -57), so the entire
12-byte body of L9CB8 is replaced by a single `BRA L9C81`. The RTS
at L9CC5 was originally preserved for the external reference
`BCS L9CC5` at line 5519, but that branch has been redirected to the
nearby RTS at L9C92, allowing the L9CC5 RTS to be removed entirely.

After entering at L9C81, the subroutine clears carry, adds A to L0B,
handles the carry into L0C, sets L0A=1, then falls through to the
BIT LFF / BMI L9C41 test. This is harmless for L9CB8's callers:
LFF bit 7 is only set during the TRACE path, and L9C41 is a TRACE
printer that falls through to the same RTS. Even in the TRACE case,
the only penalty is printing the line number — which is correct
behaviour, since L9CB8's callers are advancing to a new line.

**Saves:** 12 bytes, 0 cycles on hot paths. Costs +9 cycles on
L9CB8's two cold call paths (the extra BIT/BMI test).

```diff
 .L9C80
-        CLC
         TYA
+.L9C81
+        CLC
         ADC     L0B
         STA     L0B
         BCC     L9C8A
```

```diff
 .L9CB6
         LDA     #$03
 .L9CB8
-        CLC
-        ADC     L0B
-        STA     L0B
-        BCC     L9CC1
-
-        INC     L0C
-.L9CC1
-        LDY     #$01
-        STY     L0A
-.L9CC5
-        RTS
+        BRA     L9C81
```

---

## Change 13: LB522 — bare-NEXT fast path

**Location:** Lines 10299–10310 (label LB522)

**Rationale:** The NEXT handler begins by calling L99C4 to parse an
optional variable name. For bare `NEXT` (the most common form in tight
loops), L99C4 still performs a full pointer copy (L0B->L19, L0C->L1A,
L0A->L1B), a space-skip, and a multi-way character classification
before returning Z=1. This costs approximately 46 cycles.

In the tightest benchmark pattern — `FOR I%=1 TO N: NEXT:` — the byte
immediately after the NEXT token is $3A (colon) or $0D (end-of-line).
By peeking at this byte inline, we can detect bare NEXT and skip the
JSR L99C4 entirely.

The fast path loads Y from L0A and checks `(L0B),Y` for $0D and $3A.
On a match, it branches past the JSR to a shared tail that sets L1B
(needed by the loop-done exit at LB5DF), loads the FOR stack pointer,
and continues. Both `CMP #$0D` and `CMP #$3A` set carry (A >= operand),
so `BCS LB56A` correctly enters the step-addition path. (The step
code at LB56A itself checks the variable type via `CPY #$05` and
dispatches to the float path at LB5F1 if needed, so the carry flag
does not determine integer vs float.)

On a miss (variable name present, or space-padded NEXT), the code
falls through to the original JSR L99C4 / BNE LB530 sequence. This
path pays a small penalty (+16 cycles for the two peeks) which is
negligible compared to the cost of variable-name parsing.

When L99C4 returns Z=1 on the slow path (bare NEXT preceded by spaces),
it falls through to `STY L1B`. This is safe: L99C4 stores Y into L1B
at L99D6 before returning, so Y already equals L1B and the write is
a harmless no-op.

The fast path does not need to set L19/L1A (which L99C4 normally
copies from L0B/L0C), because the NEXT handler's step-addition and
loop-continue paths use L0B/L0C/L0A and the FOR stack directly, never
L19/L1A.

**Costs:** 14 bytes. **Saves:** ~46 cycles per bare-NEXT iteration
(the tightest FOR/NEXT loops). Costs +16 cycles for NEXT-with-variable.

```diff
 .LB522
+        LDY     L0A
+        LDA     (L0B),Y
+        CMP     #$0D
+        BEQ     LB_bare
+        CMP     #$3A
+        BEQ     LB_bare
         JSR     L99C4
-
         BNE     LB530
-
+.LB_bare
+        STY     L1B
         LDX     L26
         BEQ     LB563
-
         BCS     LB56A

 .LB52D
         JMP     L9C2D
```

To present this more clearly, the complete old and new blocks are:

**Old (14 bytes LB522–LB52F):**
```asm
.LB522  JSR     L99C4
        BNE     LB530
        LDX     L26
        BEQ     LB563
        BCS     LB56A
.LB52D  JMP     L9C2D
```

**New (28 bytes LB522–LB52F):**
```asm
.LB522  LDY     L0A
        LDA     (L0B),Y
        CMP     #$0D
        BEQ     LB_bare
        CMP     #$3A
        BEQ     LB_bare
        JSR     L99C4
        BNE     LB530
.LB_bare
        STY     L1B
        LDX     L26
        BEQ     LB563
        BCS     LB56A
.LB52D  JMP     L9C2D
```

---

## Change 14: LB5CF — NEXT continuation path optimisation

**Location:** Lines 10407–10414 (label LB5CF)

**Rationale:** When the NEXT handler determines that the loop should
continue, LB5CF restores the text pointer and re-enters the interpreter.
The original code calls `JSR L9C8A` (which sets L0A=1 and checks for
Escape) then `JMP L90D0` (which reloads Y from L0A). Since L9C8A's
L0A=1 setup is immediately consumed by L90D0's `LDY L0A`, we can
instead call the escape-check-only entry L9C8E, set L0A and Y inline,
and jump directly to L90D2 (bypassing the redundant `LDY L0A`).

This saves the `LDY #$01 / STY L0A` inside L9C8A (5 cycles) plus
the `LDY L0A` at L90D0 (3 cycles), at the cost of the inline
`LDY #$01 / STY L0A` (5 cycles). Net: 3 cycles saved per NEXT
iteration.

**Costs:** 4 bytes. **Saves:** 3 cycles per NEXT loop iteration.

```diff
 .LB5CF
         LDY     L0526,X
         LDA     L0527,X
         STY     L0B
         STA     L0C
-        JSR     L9C8A
+        JSR     L9C8E

-        JMP     L90D0
+        LDY     #$01
+        STY     L0A
+        JMP     L90D2
```

---

## Change 15: Remove dead LDA L31 after L82FB

**Location:** Line 703 (between the RTS at L8301 and label L8304)

**Rationale:** The instruction `LDA L31` at $8302 immediately follows
an RTS and has no label — nothing branches to it and nothing falls
into it. It is unreachable dead code, the same class as Change 5.
(Verified: no reference to $8302/$8303 exists anywhere in the source,
either as a label or an address constant.)

**Saves:** 2 bytes.

```diff
         STA     L31
         RTS

-        LDA     L31
 .L8304
         BMI     L8346
```

---

## Change 16: LBE6B load reorder + redundant CPY removal at L91EF

**Location:** Lines 12036–12040 (label LBE6B) and 3322–3326 (label L91EF)

**Rationale:** LBE6B appends a carriage return to the string buffer at
$0600 and is called from the string-store path (L91EF), the OPENIN/
OPENOUT filename path (LAB41), and by fall-through from LBE65 (the
OSCLI statement handler). It originally ended with flags reflecting
A (=$0D), so the L91EF caller needed an explicit `CPY #$00` to test
the string length in Y. Swapping the two loads (`LDA #$0D / LDY L36`
instead of `LDY L36 / LDA #$0D`) makes the routine return with Z/N
reflecting Y (the string length) at no cost, so the caller's CPY can
be deleted.

Safety: the other JSR caller (line 8364) executes `LDX #$00`
immediately after return, overwriting Z/N before use; the LBE65
fall-through path returns into `JMP L9C55`, and L9C55 begins with TXA,
which also overwrites Z/N. The carry flag is untouched by both the old
and new orderings. Exhaustively checked: LBE65 and LBE6B are the only
entry points, and no code branches into the routine's interior.

**Saves:** 2 bytes, 2 cycles per string store through L91EF (every
string variable assignment).

```diff
 .LBE6B
-        LDY     L36
         LDA     #$0D
+        LDY     L36
         STA     L0600,Y
         RTS
```

```diff
 .L91EF
         JSR     LBE6B

-        CPY     #$00
         BEQ     L9201
```

---

## Change 17: LBD77 — fix hard-coded keyword-table base (bug fix)

**Location:** Lines 11841/11843 (label LBD77)

**Rationale:** LBD77, the character/token printer used by LIST and by
the error-message printer, loaded the keyword-table base as hard-coded
immediates (`LDA #$13 / LDA #$85` = $8513). The `run.sh` sed pass that
converted address constants to labels only matched 4-hex-digit
constants, so these two immediates were missed when the disassembly
was made relocatable. Once Changes 1–5 shifted the table down 3 bytes
(and Change 15 two more), the token search began mid-table. The walk
resynchronises after the first entry, so the visible symptoms were
narrow but real: token $80 (`AND`) became unfindable — `LIST` printed
garbage for it (`Pp` on the pre-fix ROM) — and on the 3-byte-shifted
layout `ABS` printed as an empty string. Verified against the pre-fix
binary in the emulator, and fixed by making the base symbolic:

```diff
-        LDA     #$13
+        LDA     #LO(L8513)
         STA     L38
-        LDA     #$85
+        LDA     #HI(L8513)
         STA     L39
```

**Costs/saves:** 0 bytes. Restores correct LIST output and
token-bearing error messages on any layout.

---

## Change 18: Error-message dictionary compression

**Location:** All 50 relocatable BRK messages; expander + dictionary
inserted before LBE95; hook in the REPORT print loop (line ~4658).

**Rationale:** The 51 BRK error messages hold ~415 bytes of text.
Acorn already compresses them by embedding keyword tokens (printed via
LBD77's table search) and even added a detokenise-only pseudo-keyword
"Missing " (token $8D) after the tokeniser's $FE end marker — but all
128 token codes $80–$FF are in use, so that mechanism is exhausted.
Bytes $0E–$1F never occur in message text, so they become escape
codes: byte $nn expands to entry ($nn-$0D) of a new dictionary at
LDICT. Codes $01–$0D deliberately pass through as ordinary control
characters — the ROM's copyright string, which the language init
installs as the boot-time "error" and REPORT prints after a clean
start, legitimately ends with $0A,$0D. (An earlier draft used $01–$1F
and made REPORT print the copyright followed by a stray dictionary
entry.)
The expander LMSGX replaces `JSR LBD77` in REPORT's print loop only
(LIST and program detokenising are untouched) and recurses, so entries
may themselves contain escape codes or keyword tokens. A greedy
optimiser over the real message bytes chose 11 entries:

| code | expansion | | code | expansion |
|------|-----------|-|------|-----------|
| $0E | ` range` | | $14 | `variable` |
| $0F | `No ` | | $15 | `Out of` |
| $10 | `Too many ` | | $16 | `match` |
| $11 | ` space` | | $17 | `yntax` |
| $12 | `<$0F>such ` | | $18 | `ro` |
| $13 | `Bad ` | | | |

The "No TUBE" message is excluded: it is copied to $0100 by a
fixed-length loop (`LDX #$0A`) in the service handler, so its size is
load-bearing. Message text shrinks 407→252 bytes; the dictionary costs
71 and the expander 44 (including the control-character passthrough). The compression was verified three ways: a
byte-exact re-expansion check in the build script, an emulator error
battery covering every dictionary entry (Log range, No FOR, -ve root,
DIM space, No such variable, Bad DIM, Out of DATA, Type mismatch,
Syntax error, ON syntax, Too many FORs, Missing ,), and the full
52-check self-test suite.

**Saves:** 40 bytes net. Costs ~30 cycles per expanded substring on
the error-print path only (cold).

---

## Change 19: Single-digit decimal-literal fast path

**Location:** Factor evaluator dispatch (label LAD9C) and new code
LNUMF/LNUMI/LNUMS inserted before LADB6.

**Rationale:** Every numeric literal is parsed by the full
float-capable decimal parser LA2DD — even a bare `1` costs roughly
115–120 cycles (seven STZs of setup, the digit loop, the
integer-assembly exit). Constants of a single digit dominate hot
interpreted code (`I%=I%+1`, `STEP 1`, comparisons with 0, small
offsets), and BBC BASIC re-parses them on every execution because
program text is not constant-folded.

The dispatch at LAD9C routes characters $2E–$3E to the literal parser.
The fast path first confirms the character is an actual digit
('0'–'9'), then peeks the next character: if it is a digit, '.', or
'E' (exactly the continuation set accepted by LA2DD's loop at
LA303/LA34C — lowercase 'e' is not an exponent marker), it restores
the entry state (DEY, TXA) and falls into the original `JSR LA2DD`.
The peek tests the digit range first, since a digit is the most common
continuation, and the high-terminator leg falls through the '.'
comparison (which cannot match a character above ':'). Change 20
below cuts the fall-back cost further, to ~8 cycles.
Otherwise it delivers the result directly, reproducing LA2DD's integer
exit contract at LA36B precisely: L2A = digit value, L2B–L2D = 0,
A = 1 (integer type), carry set. L1B needs no adjustment — the factor
evaluator's space-skip already left it pointing at the terminator,
which is exactly where LA2DD's `STY L1B` would put it. X and Y are not
normalised: LA2DD's own integer, float, and error exits (and the
variable-fetch path LB1DE) already leave X/Y with different values per
path, so no caller can be relying on them.

**Costs:** 43 bytes (from the SKIPTO pool). **Saves:** ~72 cycles per
single-digit literal (measured). The fall-back penalty for multi-digit,
decimal-point and exponent literals was ~32 cycles as first shipped;
Change 20 reduces it to ~8. Measured on 5000-iteration loops
(centiseconds, Master 128 timing, with Change 20): `A%=A%+1` 355→335
(−5%); `A%=A%+12345` 468→470; `REPEAT S%=S%+1 UNTIL S%=5000` 670→653. Verified with 23 dedicated literal edge
cases (multi-digit, `1.5`, `.5`, `5.`, `1E2`, `2E-1`, `VAL`, `DATA`,
hex, negatives, terminators) plus the full 52-check suite.

---

## Change 20: LA2DD entry restructure — near-free literal fall-back

**Location:** LA2DD entry (label LNUMD added), LNUMF's fall-back
(LNUMS/LNUMX), LMSGX skip/print loops, and a new shared pointer-copy
subroutine LCPYW used by L97A9 and L9C0A.

**Rationale:** Change 19's fall-back re-entered LA2DD from the top,
re-running the first-character classification it had already done.
Three coordinated edits eliminate almost all of the remaining penalty:

1. **LA2DD entry restructured, checks before setup.** `EOR #$30`
   classifies digit / dot / reject in one test (digits map to their
   value directly, replacing the old CMP/CMP/SBC chain), and the state
   setup (STZs, L49=$FF) moves after the checks, followed by a 2-byte
   test that routes the leading-'.' marker to LA348. A new entry point
   `LNUMD` (at the setup) takes A = digit value and skips the checks.
   The fail path is unaffected: L82DD only writes state, so it does
   not care that the setup no longer precedes rejection. Net: VAL,
   READ and every other LA2DD caller get slightly *faster* (−2
   cycles), and the entry is 5 bytes larger.
2. **The fall-back becomes `DEY / TXA / JMP LNUMD`.** LNUMF now keeps
   the digit *value* in X (its own pre-check uses the same EOR trick,
   which also deletes the old `AND #$0F`). Jumping rather than calling
   works because every success exit of LA2DD sets carry (LA36B and
   LA3AA both end SEC/RTS) and the only CLC exit is the entry
   rejection, unreachable from LNUMD — so LA2DD's RTS returns straight
   to the factor's caller with the identical contract, skipping the
   BCC/RTS tail.
3. **Funding (−7 bytes):** the LMSGX dictionary scan/print loops are
   rotated to test the terminator with LDA's own flags (−2 bytes, and
   slightly faster; error path only), and the 6-instruction statement-
   pointer copy shared by the PROC dispatch (L97A9) and L9C0A is
   extracted as `LCPYW` (−5 bytes; +10 cycles measured per PROC call,
   ~0.7% of a minimal PROC's cost — the third copy at L9DF3 stays
   inline because the expression-evaluator entry is too hot).

Measured (5000-iteration loops): `A%=A%+12345` 475→470 (fall-back
penalty ~32→~8 cycles vs the 468 pre-Change-19 baseline);
`REPEAT S%=S%+1 UNTIL S%=5000` 659→653; PROC call +10 cycles;
`VAL` unchanged. Full 52-check suite and the literal edge-case suite
(including `.5`, `5.`, `1E2`, `VAL(".5")`) pass.

**Costs:** net −2 bytes (pool grows to 3).

---

## Free-space pool and the pinned tail (SKIPTO scheme)

The bytes freed by Changes 15–18 are absorbed by a `SKIPTO &BE95`
directive placed after the dictionary; a second `SKIPTO &BEFD` acts as
a build-time assertion. Everything from LBE95 to the end of the ROM is
pinned at its original address, because:

- the floating-point constants in page $BF are addressed by
  single-byte immediates (`LDA #LO(LBFxx)` / `ADC #LO(LBFxx)`) with the
  high byte implied to be $BF by the consuming routines;
- the LAA55 range-check indexes its compare tables via the LBF00/LBEFE
  bases;
- the LN/ATN table-index computation (the ADC #$0A chain at LA8CC,
  home of the documented LN accuracy bug) is sensitive to where table
  entries sit *within* the page — letting the pool drift would
  silently change which entries suffer the wrap-around, altering
  LN/ATN results;
- the pinned code at $BF0D ends with `BRA LBEEB`, so LBEEB must stay
  within branch range (this is why the boundary is LBE95, the first
  flow boundary before that group, rather than LBEFD).

SKIPTO makes the assembler absorb any net byte change automatically
and fail the build on overrun. **The pool currently holds 3 free
bytes** ($BE92–$BE94).

---

## Summary

| # | Location | Label | Bytes | Cycles saved |
|---|----------|-------|-------|-------------|
| 1 | 173, 220 | L802C/L806A | -2 | 4 per service call |
| 2 | 6694 | LA2CC | -2 | 7 per digit output |
| 3 | 193 | L8040+9 | -1 | -- |
| 4 | 9387 | LB047 | -1 | -- |
| 5 | 6707 | (dead code) | -1 | -- |
| 6 | 2852 | L8F92 | *(not applied)* | *(Y register conflict — 4 live callers)* |
| 7 | 2862 | L8F9D | *(not applied)* | *(Y register conflict — 8 live callers)* |
| 8 | 3110 | L90D0/L90D2 | *(not applied)* | *(Y register conflict)* |
| 9 | 6207 | LA06F/LA070 | *(not applied)* | *(X register contract change)* |
| 10 | 8822 | LAD78 | *(not applied)* | *(Y register conflict)* |
| 11 | 5317 | L9C16 | +1 | 6 per space (x3 callers) |
| 12 | 5402, 5447 | L9C80/L9CB8 | -12 | 0 (hot path) |
| 13 | 10299 | LB522 | +14 | **~46 per bare NEXT** |
| 14 | 10407 | LB5CF | +4 | **3 per NEXT iteration** |
| 15 | 703 | (dead code) | -2 | -- |
| 16 | 12036, 3325 | LBE6B/L91EF | -2 | 2 per string store |
| 17 | 11841 | LBD77 | 0 | (bug fix: LIST/AND, ABS) |
| 18 | (50 messages) | LMSGX/LDICT | -40 | ~30/substring, error path only |
| 19 | 8818 | LAD9C/LNUMF | +43 | **~72 per single-digit literal** |
| 20 | 6679, 8848 | LA2DD/LNUMD/LCPYW | -2 | fall-back ~32→~8 cycles |
| | | (SKIPTO pool before LBE95) | +3 | -- |
| | | **Total** | **0** | |

With all applicable changes applied (1–5, 11–20), the ROM uses all
16384 bytes exactly, 3 of which are free space in the SKIPTO pool. Assignment parsing benefits from
faster space-skipping. Tight FOR/NEXT loops with bare `NEXT` (followed
by end-of-line or `:`) save approximately 49 cycles per iteration.
String assignment saves 2 cycles per store. Single-digit constants in
expressions evaluate ~72 cycles faster: `A%=A%+1` loops run ~5%
faster overall.

## Rejected / future candidates from the second round

Beyond Changes 15–16, a systematic second pass (peephole scans for
65C02 idioms, redundant flag/register operations, JMP→BRA range
checks, branch-trampoline retargeting, duplicate-tail merging, and
unreferenced-label analysis over the assembled listing) found no
further clean wins. For the record:

- **JMP→BRA:** the only in-range JMP left is the ROM service-entry
  vector at $8003, which is format-locked (and saving a byte between
  the fixed header offsets is useless anyway).
- **Branch trampolines:** all ~90 conditional branches that land on a
  JMP have final targets out of BRA range from the branch site.
- **PLA/TAY→PLY (3 sites):** rejected — every site consumes the pulled
  value in A immediately afterwards (EOR/SBC/STA), so A must be loaded.
- **Sign-pack merge** (`LDA L2E/EOR L31/AND #$80/EOR L31` ×3 at lines
  7175, 10004, 11602): would save ~6 bytes but adds 12 cycles to every
  real-variable store — a bad trade for a hot path.
- **Token-match merge** (LIST path): REJECTED on closer inspection —
  the candidate block contains a `BNE L8CE3` non-local branch, so a
  JSR extraction would leave a stale return address on the stack;
  restructured variants yield at most +1 byte.
- **UNTIL loop-back micro-optimisation:** reusing the Change-14 trick
  costs +6 bytes for 3 cycles per REPEAT iteration and would need the
  L0A=1 invariant threaded past the shared LB762 entry; not worth it.
- **Single-digit decimal-literal fast path:** now implemented as
  Change 19, funded by the Change 18 compression.
- **Confirmed already-optimal (no change possible):** the integer
  variable fetch (LB1DE), integer add/subtract (L9F13/L9F70), operand
  push (LBC66), resident-integer name fast path (L99D8), the
  recursive-descent precedence tests (L9E02/L9E48/L9E6D/LA029), the
  IF-false line-skip scan (L9CFD, 16 cycles/char but no cheaper
  correct form), and the PROC-call pointer setup (L97A9).
