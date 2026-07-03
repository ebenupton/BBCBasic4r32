# Plan: BASIC V-style WHILE/ENDWHILE for BASIC 4r32 (proposed Change 21)

Status: PLAN ONLY — no code yet. This documents the design, the byte
accounting, and the open decisions, so the implementation can be a
mechanical follow-up.

## 1. Objective and funding strategy

Add `WHILE <expr> ... ENDWHILE` with BASIC V semantics to the 16K
BASIC 4r32 ROM, funded by reverting the performance enhancements
(which spent bytes) while keeping every byte-saving change, the bug
fixes, and the message compression. The pinned-tail SKIPTO discipline
is unchanged: all new code goes before the `SKIPTO &BE95` pool.

## 2. What BASIC V does (source findings)

Source: RISC OS Open BASIC, `s/Stmt` (labels `WHILE`, `EWHILE`,
`ENDWH`), `hdr/Tokens`, `hdr/Definitions`, `s/Lexical`.
Repo: https://gitlab.riscosopen.org/RiscOS/Sources/Programmer/BASIC

**WHILE statement** (`WHILE`, s/Stmt:1717): pushes a pointer to the
*condition text* onto the control stack, evaluates the condition, and:
- TRUE: pushes a `TENDWH` type tag plus the block-start pointer
  (BASIC V uses one tagged control stack for FOR/REPEAT/WHILE/LOCAL;
  entry layout per hdr/Definitions: `TENDWH, block start, expr start`),
  then continues with the next statement.
- FALSE: falls into the forward scanner `EWHILE`.

**ENDWHILE statement** (`ENDWH`, s/Stmt:439): checks for Escape,
verifies statement end, requires the top control-stack entry to be a
`TENDWH` (else "Not in a WHILE loop"), then **re-evaluates the
condition itself** from the saved expression pointer:
- TRUE: resume at the saved block start, keep the stack entry.
- FALSE: pop the entry, continue after the ENDWHILE.

This is the key design elegance to copy: the WHILE statement executes
exactly once per loop entry; every iteration's test happens at
ENDWHILE from the saved pointer, so the forward scan runs **at most
once per loop** (only when the condition is false on entry) and the
loop body never re-executes the WHILE statement.

**The forward scanner** (`EWHILE`/`EWHILP`/`EWHILX`, s/Stmt:1729) —
the part we were asked to crib. It is a byte-at-a-time scan with:
- a nesting counter starting at 0: each nested WHILE token +1, each
  ENDWHILE −1; the match is found when the counter reaches −1;
- a quote toggle: `"` flips an in-string flag; token tests are
  suppressed while it is set;
- REM/DATA poisoning: on a REM or DATA token the flag is forced
  non-zero so nothing matches until end of line;
- line handling: on CR, peek the next byte — `&FF` means end of
  program (error out); otherwise skip the line-header bytes and clear
  the in-string/poison flag (so an unterminated string cannot poison
  the rest of the program);
- a token subtlety: BASIC V's WHILE is a two-byte escape token whose
  second byte collides with ACS, so the scanner checks the preceding
  byte for the `TESCSTMT` prefix ("disassociate ACS"). Our analogue of
  this class of hazard is text aliasing, handled below.

**Tokens:** BASIC V added WHILE/ENDWHILE (and CASE, ENDIF, etc.) via
escape-prefix two-byte tokens (`TESCFN`/`TESCCOM`/`TESCSTMT`). That
route is closed to us: BASIC IV uses **all 128 token codes** $80–$FF
(verified during Change 18: operators/specials $80–$8D, functions
$8E–$C5, statements $C6–$FF), and the escape-prefix trick needs a free
single-byte code.

## 3. Design for BASIC IV

### 3.1 Keyword recognition: text keywords, no tokens

`WHILE` and `ENDWHILE` remain plain text in the program. This needs no
tokeniser or LIST changes at all:
- the tokeniser will not eat them: "WHILE" diverges from "WIDTH" at
  the second character; "ENDWHILE" survives because END's conditional
  flag rejects tokenisation when followed by an alphanumeric
  (verify both empirically as an early implementation step);
- LIST shows them as typed (no LISTO indenting — documented limit).

Recognition hook: in the statement dispatch at L90EA, the character is
already in A before the variable-name parse. Insert `CMP #'W'/BEQ` and
`CMP #'E'/BEQ` filters that divert to a text comparison against
"WHILE"/"ENDWHILE" (shared string-compare routine, also used by the
scanner). Boundary rule: the character after the keyword must not be
alphanumeric, so `WHILEX=1` still assigns to the variable WHILEX.

Cost of this placement: ~4–5 cycles on every assignment statement
(two immediate compares), full compare only for statements starting
'W'/'E'. Alternative considered and rejected: hooking the "Mistake"
error path costs nothing on existing programs but misses `WHILE(X>0)`
(the name parser sees `WHILE(` as an array reference, which errors
down a different path) and adds ~250 cycles per iteration.

### 3.2 Semantics (matching BASIC V where sensible)

- `WHILE <expr>` ... `ENDWHILE`, nestable, single-line or multi-line.
- Condition false on entry: skip forward past the *matching*
  ENDWHILE (nesting-aware), continue there.
- Escape is checked once per iteration (at ENDWHILE, like UNTIL).
- Mismatched constructs behave like BASIC IV's other stacks (separate
  stacks, quirky interleavings permitted) rather than BASIC V's tagged
  single stack — consistent with FOR/REPEAT/GOSUB in this ROM.
- Errors: `No WHILE` (ENDWHILE with empty stack), `Too many WHILEs`
  (depth exceeded), `No ENDWHILE` (scan hit end of program). All three
  compress well: the Change 18 dictionary already has `No ` ($0F) and
  `Too many ` ($10).

### 3.3 WHILE stack

Two parallel byte arrays (lo/hi of a normalised text pointer), REPEAT
style, depth 10–14, plus one depth byte. Each entry is the pointer to
the *condition text* (normalised via the L9C80 convention, offset
folded so L0A=1). Unlike BASIC V we do **not** store the block-start
pointer: after ENDWHILE re-evaluates the condition TRUE, the text
pointer is already at the block start, for free.

Location: page 4 looks free between $0480 and $04FE — BASIC references
only $0400–$046B (resident integers), $0460/$0464/$046C–$047F (misc
state), and the $04FF/$05xx stacks. **Verification required**: confirm
by tracing the indexed accesses (`L046C,X` at asm lines 3366/10982)
and by a memory-watch test in jsbeeb; then place the stack at the top
of that hole (e.g. $04E0–$04FE + pointer byte).

Reset: the depth byte must be zeroed wherever L24/L25/L26 are reset —
language init, RUN/CLEAR, and the error handler's stack reset. Find
all such sites as an implementation step (known: the init block near
line 339, and the ON ERROR reset path off LB2B2).

### 3.4 WHILE handler

1. Depth check → `Too many WHILEs`.
2. Normalise and push the condition pointer.
3. Evaluate the condition (same helper chain UNTIL uses:
   JSR L9DF3 / L9C55 / L9781, then the 4-byte ORA zero test —
   share this as a small subroutine with ENDWHILE).
4. TRUE: continue (`JMP L90CA`).
5. FALSE: pop, run the forward scanner, continue after the match.

### 3.5 ENDWHILE handler

1. Depth zero → `No WHILE`.
2. Escape check (`JSR L9C8E`, as Change 14 does).
3. Save the current text position (resume point) on the CPU stack.
4. Point L0B/L0C/L0A at the stack-top condition, re-evaluate via the
   shared helper.
5. TRUE: discard the saved resume point, continue interpreting at the
   current position (= block start). Stack entry stays.
6. FALSE: pop the entry, restore the saved resume point, continue
   after the ENDWHILE.

### 3.6 Forward scanner (adapted from BASIC V's EWHILE)

Same skeleton: nesting counter, CR → end-of-program check
($0D then $FF → `No ENDWHILE`) / skip 3 header bytes / clear flags.

Differences forced by text keywords:
- Match **only at statement starts**: after a line header, after `:`,
  and after THEN ($8C) or ELSE ($8B) tokens (so
  `IF X THEN WHILE ...` participates in nesting). Track an
  at-statement-start state; skip spaces while in it.
- Boundary check after the matched word (next char not alphanumeric),
  so a variable named WHILEFLAG never miscounts. Reuse the same
  compare routine as recognition.
- String/REM/DATA guards: BASIC V carries a quote toggle and REM/DATA
  poisoning. Note that BASIC IV's own IF-false scanner (L9CFD) does
  *neither* (the well-known ELSE-inside-a-string quirk). Decision:
  implement the quote toggle + REM/DATA poisoning only if the budget
  allows (~+25 bytes); otherwise match native quirk level and document
  (`:WHILE` inside a string literal inside a skipped block miscounts).
  Statement-start matching already makes false positives much rarer
  than BASIC V's raw byte scan would suffer.
- No $8D hazard: encoded line numbers after GOTO are three bytes in
  $40–$7F, which cannot alias keyword text at a statement start.

### 3.7 Placement

All new code and the keyword strings go immediately before the
`SKIPTO &BE95` pool (cold region). The recognition hook is the only
edit in hot code.

## 4. Reversion list (funding) and byte accounting

Revert (perf features that spent bytes; keep all byte-savers, the
LBD77/copyright bug fixes, and the message compression):

| Revert | What | Frees |
|--------|------|-------|
| Change 11 | L9C16 space-skip restructure | 1 |
| Change 13 | bare-NEXT fast path | 14 |
| Change 14 | NEXT continuation (back to JSR L9C8A / JMP L90D0) | 4 |
| Change 19 | single-digit literal fast path (LNUMF block, dispatch retarget) | 43 |
| Change 20 (part) | LA2DD entry restructure (LNUMD unreferenced after 19 goes) | 5 |
| — | current SKIPTO pool | 3 |
| | **Total freed** | **70** |

Keep from Change 20: the LMSGX loop rotation and the LCPYW extraction
(both are byte savers). Note: Changes 13/14 are the most valuable perf
work (~49 cycles per NEXT); if other funding suffices, reinstate them
last — but the default per this plan is to revert all of the above.

## 5. Cost estimate and the funding gap

Conservative sizing (to be refined to exact instruction counts before
any code is written — this is the decision gate):

| Component | Bytes |
|-----------|-------|
| Keyword texts + shared compare + dispatch hook | ~55 |
| WHILE handler | ~35 |
| ENDWHILE handler | ~45 |
| Shared evaluate-and-test helper | ~12 |
| Forward scanner (quirk-parity; +25 for BASIC V-grade guards) | ~60–85 |
| Three error messages (dictionary-assisted) | ~29 |
| Stack init/reset hooks | ~10 |
| **Total** | **~245–270** |

Identified funding beyond the 70 from reverts:

| Source | Frees | Cost |
|--------|-------|------|
| Strip Tube/HiBASIC service frills (the *BASIC-style command matcher, 'H' prefix, LBF66 tube check, "No TUBE" stack-copied BRK, OSBYTE $8E re-entry; keep *HELP + workspace calls) | ~100 | ROM no longer enterable by star-command/Tube (still via *FX 142 and reset; decision needed) |
| Also drop the *HELP responder | ~30 | *HELP shows nothing for BASIC (decision needed) |
| Sign-pack merge (3 identical 8-byte sequences) | ~6 | +12 cycles per real-variable store (acceptable given perf is being traded away) |
| L9DF3 also uses LCPYW | ~9 | +12 cycles per expression evaluation (measurable; last resort) |

Best case: 70 + 100 + 30 + 6 + 9 ≈ **215**, versus ~245–270 needed.
**The plan does not close the gap on paper.** Levers, in preference
order, at the decision gate: (a) exact sizing usually differs from
conservative estimates — resolve first; (b) drop the THEN/ELSE
statement-start cases from the scanner (−10, documented limit);
(c) shorten `Too many WHILEs`/`No ENDWHILE` texts; (d) reduce depth
and inline the stack ops; (e) if still short, this becomes the first
customer of the companion-bank design from the space discussion, with
the scanner and error texts in the second bank.

## 6. Test plan

- The suite specified in `bbc_basic_test_plan.md` §6.4
  (WHILE...ENDWHILE) becomes implementable for the first time — use it
  as the acceptance set, plus:
  - false-on-entry skip (empty body; nested WHILE inside skipped body;
    ENDWHILE inside string literal / after REM / after DATA in the
    skipped region);
  - single-line `WHILE X>0:X=X-1:ENDWHILE`;
  - `IF TRUE THEN WHILE ...` participation in nesting;
  - variables named WHILEX / ENDWHILES (must not be recognised);
  - `No WHILE`, `Too many WHILEs` (depth+1), `No ENDWHILE` errors;
  - ON ERROR inside a WHILE loop resets the stack;
  - interaction: WHILE containing FOR/NEXT, REPEAT/UNTIL, PROC calls,
    GOTO out of the loop.
- Regression: full 52-check suite, the error battery, LIST round-trip,
  and re-baselined benchmarks (B1/B2/B4 revert to pre-optimisation
  values — record the new expected numbers).

## 7. Risks and open questions

1. **Budget** — see §5; hard gate before coding.
2. Tokeniser behaviour on "ENDWHILE" (END conditional flag) — verify
   first; if END *does* tokenise mid-word, recognition and scanning
   must instead match `<END token>"WHILE"`, which also works but
   complicates the compare.
3. The $0480–$04FE hole must be proven free (trace `L046C,X` reach;
   memory-watch under jsbeeb while exercising INPUT/EDIT/AUTO paths).
4. Statement-dispatch hook adds ~4–5 cycles to every assignment —
   confirm acceptable (it is the price of `WHILE(` correctness).
5. Service-frill strip changes user-visible behaviour (*commands);
   needs sign-off.
6. Text keywords are case-sensitive, non-abbreviatable, and invisible
   to LISTO indenting — document in README.

## 8. Execution order

1. Verify tokeniser treatment of WHILE/ENDWHILE text (jsbeeb).
2. Verify the page-4 hole.
3. Do the reverts; re-run suite + benchmarks; commit ("funding" commit).
4. Exact-size the components on paper against the freed budget
   (**decision gate**; pick funding levers or the two-bank fallback).
5. Implement recognition + handlers + scanner; error messages last
   (dictionary may want a new entry if `ENDWHILE`/`WHILE` text repeats).
6. Acceptance tests (§6), regression suite, README/OPTIMISATIONS.md
   updates, push.
