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

This memo describes 14 changes to the ROM, targeting the 65C02. They
fall into four categories:

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

Net effect: the ROM uses all 16384 bytes exactly. Assignment parsing
benefits from faster space-skipping. Tight FOR/NEXT loops with bare
`NEXT` (followed by `:` or end-of-line) save approximately 49 cycles
per iteration.

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
| | | **Total** | **0** | |

With all applicable changes applied (1–5, 11–14), the ROM uses all
16384 bytes exactly. Assignment parsing benefits from faster
space-skipping. Tight FOR/NEXT loops with bare `NEXT` (followed by
end-of-line or `:`) save approximately 49 cycles per iteration.
