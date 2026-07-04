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

### 3.1 Keyword representation — the token question, thought through

All 128 single-byte codes are assigned, but that is not the end of the
analysis. Codes are *context-multiplexed*: statement dispatch,
expression dispatch and argument-position lookaheads each consume
overlapping ranges, and several codes are illegal in whole contexts.
Options examined:

**(a) Reuse a function code for statement-position WHILE.** Every
function token $8E–$C5 is an error at statement start, so the
statement loop could give one a second meaning. Fatal flaw: LIST.
LBD77 detokenises by first-match on the token byte, with no context,
so one code cannot print as two different keywords. Rejected.

**(b) Retire a keyword.** No BASIC IV keyword is redundant (OPENIN
and OPENUP have distinct semantics; the $CF–$D3 statement forms of
PTR/PAGE/TIME/LOMEM/HIMEM are all live assignment handlers; the
$C6–$CE commands are legal in programs). Rejected.

**(c) $8D as a two-byte escape prefix.** The line-number marker is
always followed by three bytes in $40–$7F, so `$8D <token>` is
unambiguous. But everything that walks $8D triples blindly would need
patching — RENUMBER's whole-program scan chief among them — plus LIST
and the tokeniser. Workable but the most invasive option. Rejected in
favour of (d).

**(d) RECOMMENDED: `OFF` ($87) as a two-byte escape-statement prefix
— our analogue of BASIC V's TESCSTMT.** Verified in the ROM: $87 is
consumed at exactly three argument-position lookaheads (after TRACE /
ON ERROR / ON), has no statement dispatch of its own (statement-start
OFF is an error today), and is never legally followed by a byte
≥ $80. Therefore the pairs

    WHILE    = $87 $E3   (OFF FOR)
    ENDWHILE = $87 $DC   (OFF DATA)

can never occur in an existing program, and — unlike text keywords —
cannot occur inside strings, REM, DATA or $8D triples either, because
the tokeniser never emits $87 there. Four integration points:

1. *Tokeniser*: table entries `"WHILE",$E3` (before WIDTH, which must
   stay last as the $FE scan terminator) and `"ENDWHILE",$DC` (before
   END, following the ENDPROC-before-END precedent verified in the
   table). A small emitter hook prefixes the $87 byte when one of
   these two entries matched — triggered by a spare flag bit if the
   flag-bit audit finds one, else by comparing the entry pointer
   (~14–16 bytes either way). Abbreviations (`WH.`, `ENDW.`) work for
   free via the normal matcher.
2. *LIST*: a hook in the LIST character loop: on $87 with a following
   $E3/$DC, print the keyword text from our table entries and consume
   both bytes (~26 bytes). LBD77 itself needs no change — and the
   entry token bytes $E3/$DC were chosen so their first-match owners
   (FOR, DATA — both alphabetically ahead of W/E sections... DATA
   ahead of ENDWHILE, FOR ahead of WHILE) keep winning LBD77
   searches, so FOR/DATA/UNTIL/OFF all still LIST correctly.
3. *Statement dispatch*: in the L90EA path (non-token statements),
   `CMP #$87` diverts to a second-byte check (~20 bytes). Zero cost
   for token statements; ~4 cycles for assignments.
4. *Runtime*: recognition per iteration is a 2-byte compare — no
   string comparison, no boundary rules, `WHILE(X>0)` just works.

**(e) Fallback: text keywords** (the previous revision of this plan,
retained in git history): no tokeniser/LIST surgery, but a slower and
quirkier scanner (statement-start tracking, word-boundary checks,
WHILEX/WHILE( edge cases) and a per-iteration string compare. Use
only if the tokeniser hooks in (d) prove unexpectedly hairy.

Known costs of (d) to document: SAVEd programs using WHILE are
gibberish under stock BASIC (true of any new token scheme); external
detokenisers print `OFF FOR`/`OFF DATA` until taught the pair.

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
($0D then $FF → `No ENDWHILE`) / skip 3 header bytes.

With option 3.1(d) the scanner becomes almost exactly BASIC V's,
minus its guards: it hunts the byte pair `$87 $E3` (+1) / `$87 $DC`
(−1, match at −1). Because the tokeniser is the only producer of $87
outside argument position, and strings/REM/DATA/$8D-triples contain
only what the user typed (never a bare tokenised $87 pair — a `TRACE
OFF` inside the body scans as $87 followed by a non-pair byte and is
skipped harmlessly), **no quote toggle, no REM/DATA poisoning, no
statement-start tracking and no word-boundary checks are needed**.
Estimated ~40 bytes. One caveat to verify: top-bit bytes can be
embedded in string/REM text by creative editing; if we choose to
defend against a literal $87,$E3 inside a string, the BASIC V quote
toggle costs ~+12 bytes (BASIC IV's own IF/ELSE scanner does not
bother — the known ELSE-in-a-string quirk — so quirk-parity is
defensible).

(Under fallback 3.1(e), the scanner needs statement-start tracking
after line headers / `:` / THEN / ELSE, word-boundary checks, and
optional guards: ~60–85 bytes — this was the previous revision.)

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

| Component | (d) tokens | (e) text |
|-----------|-----------|----------|
| Table entries / keyword texts | 17 | 15 |
| Tokeniser emitter hook | ~16 | — |
| LIST detokenise hook | ~26 | — |
| Recognition/dispatch hook | ~20 | ~40 |
| WHILE handler | ~35 | ~35 |
| ENDWHILE handler | ~45 | ~45 |
| Shared evaluate-and-test helper | ~12 | ~12 |
| Forward scanner | ~40 (+12 opt. quote guard) | ~60–85 |
| Three error messages (dictionary-assisted) | ~29 | ~29 |
| Stack init/reset hooks | ~10 | ~10 |
| **Total** | **~250** | **~245–290** |

The two options cost about the same; (d) buys correct LIST output,
working abbreviations, `WHILE(` support, a far simpler and safer
scanner, and per-iteration recognition measured in single-digit
cycles instead of a string compare. Byte-wise the budget conclusion
is unchanged by the choice.

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
2. Tokeniser internals for option (d): audit the keyword-entry flag
   bits (which of bits 3/4/5/7 the matcher at L8F41–L8F6D really
   tests) to pick the emitter-hook trigger; verify entry placement
   rules empirically (ENDWHILE before END, WHILE before the WIDTH/$FE
   terminator); confirm the emit path has a single choke point for
   the $87 prefix. If any of this turns hostile, fall back to (e).
3. The $0480–$04FE hole must be proven free (trace `L046C,X` reach;
   memory-watch under jsbeeb while exercising INPUT/EDIT/AUTO paths).
4. Statement-dispatch hook adds ~4–5 cycles to every assignment —
   confirm acceptable (it is the price of `WHILE(` correctness).
5. Service-frill strip changes user-visible behaviour (*commands);
   needs sign-off.
6. Option (d): SAVEd WHILE programs are not portable to stock BASIC
   ROMs, and external detokenisers show `OFF FOR`/`OFF DATA`;
   LISTO indenting is not extended to WHILE bodies. Document all
   three in the README.

## 8. Execution order

1. Flag-bit audit + tokeniser choke-point check (decides (d) vs (e));
   verify table placement rules with throwaway entries in jsbeeb.
2. Verify the page-4 hole.
3. Do the reverts; re-run suite + benchmarks; commit ("funding" commit).
4. Exact-size the components on paper against the freed budget
   (**decision gate**; pick funding levers or the two-bank fallback).
5. Implement recognition + handlers + scanner; error messages last
   (dictionary may want a new entry if `ENDWHILE`/`WHILE` text repeats).
6. Acceptance tests (§6), regression suite, README/OPTIMISATIONS.md
   updates, push.
