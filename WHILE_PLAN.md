# Plan: BASIC V-style WHILE/ENDWHILE for BASIC 4r32 (proposed Change 21)

Status: IMPLEMENTED as Change 21 (see OPTIMISATIONS.md for the
as-built record; this document is the design study). Deviations from
the plan: the L9CD6 IF-handler zero-test also shares LEVAL's tail;
the emitter hook drops the pointer high-byte carry (single-page input
buffer); `Too many REPEATs` was not retitled; a stray ENDWHILE shares
`No REPEAT`; the acceptance battery lives in tests/whiletest.bas.

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
- Errors: `Too many loops` (shared with REPEAT — see 3.3), `No WHILE`
  (ENDWHILE with empty stack; or shared `No REPEAT` in the minimal
  build), `No ENDWHILE` (scan hit end of program). All compress well:
  the Change 18 dictionary already has `No ` ($0F) and
  `Too many ` ($10).

### 3.3 Loop stack: piggyback on the REPEAT stack

WHILE shares the REPEAT stack outright: depth byte L24, pointer
arrays $0500/$0514 (read back via L04FF/L0513 with 1-based X), the
depth limit of 20, the overflow error, and — decisively — the
existing reset discipline (L24 is already cleared at language init,
RUN/CLEAR and in the error handler, so WHILE needs **no new reset
hooks and no new RAM**; the page-4 hole survey drops out of the plan
in the minimal build).

Why sharing is sound: each entry is a normalised text pointer, and
both constructs push before their bodies and pop in LIFO order.
WHILE pushes the pointer to its *condition* (which is the current
position at push time — the same thing REPEAT pushes, which is what
makes the code shareable verbatim); ENDWHILE re-evaluates from the
top entry and pops only when the loop exits. For every well-formed
program, properly nested REPEAT/WHILE constructs always pop their own
entries. What is lost is diagnostic precision on *malformed* programs:
a stray UNTIL inside a WHILE body will consume the WHILE's entry
instead of reporting `No REPEAT` (BASIC IV's separate stacks would
have caught it). Same quirk class as the interpreter's other
mismatched-construct behaviours, all verified in the emulator on the
current ROM:

- GOTO out of a FOR body leaves the frame live; a later bare NEXT
  adopts it and resumes the abandoned loop (prints "escaped" three
  times, then closes with I=4);
- `NEXT I` over an open inner `FOR J` silently discards J's frame
  (the "Can't match" error only fires when *no* frame matches);
- crossed scopes `REPEAT / FOR / UNTIL` run without complaint — UNTIL
  jumps back over the open FOR, which simply re-executes (and reuses
  its top frame rather than overflowing);
- the IF-false scanner honours an $8B byte inside a string literal as
  ELSE (poking $8B into a quoted string on an IF line yields "Mistake
  at line 10" from mid-string execution) — the no-quote-guard
  precedent cited in 3.6.

Note also the *shape* of the new failure mode: a crossed UNTIL that
pops a WHILE entry jumps to the stored condition text and dispatches
it as a statement, which in typical programs errors immediately
(e.g. `X<5` as a statement is a Mistake) — noisier and therefore
safer than the silent wrong-loop behaviour BASIC IV already exhibits
for its own stale-frame cases. Document it either way.

Optional hardening (only if budget allows): a parallel one-byte tag
array (this is where the page-4 hole would come back in) plus ~14
bytes of checks gives BASIC V-grade `No REPEAT`/`No WHILE` precision
on mismatches.

The shared overflow error message becomes literal: retitle
`Too many REPEATs` to `Too many loops` (+3 bytes over the current
dictionary-compressed form, `$10,$F5,"s"` → `$10,"loops"`), covering
both constructs honestly. Unlike BASIC V we do **not** store the
block-start pointer: after ENDWHILE re-evaluates the condition TRUE,
the text pointer is already at the block start, for free.

### 3.4 Two refactors that make the handlers almost free

- **LPUSH**: split REPEAT's body (`LBA88`: depth check → `Too many
  loops` → JSR L9C80 normalise → store L0B/L0C at $0500/$0514,X →
  INC L24) into a subroutine ending RTS; REPEAT becomes
  `JSR LPUSH / JMP L90D0` (+4 bytes to REPEAT, the whole push
  machinery reusable).
- **LEVAL**: split UNTIL's front (`JSR L9DF3 / JSR L9C55 / JSR L9781`
  plus the 4-byte ORA zero test) into a subroutine returning Z=set
  for false; UNTIL becomes `JSR LEVAL / ...` (+4 bytes to UNTIL).
  Because L9C55 performs the escape check, every WHILE/ENDWHILE
  evaluation gets Escape handling for free, like UNTIL.

Verify at implementation time: LPUSH's Y register contract (L9C80
folds Y into the pointer; REPEAT enters with Y = L0A from the
dispatch loop — the WHILE handler must present the same state).

### 3.5 WHILE and ENDWHILE handlers

WHILE (recognised via the $87 $E3 pair):
1. `JSR LPUSH` — depth check, shared error, push the condition
   pointer (= current position; this is why the ordering
   push-then-evaluate matters).
2. `JSR LEVAL`.
3. TRUE: continue (`JMP L90CA`). Entry stays for ENDWHILE.
4. FALSE: `DEC L24` (pop own entry), run the forward scanner,
   continue after the match.

ENDWHILE ($87 $DC):
1. L24 zero → `No WHILE` (or share UNTIL's `No REPEAT` branch in the
   minimal build — decide at the gate).
2. Save the current text position (resume point) on the CPU stack.
3. Load the top entry into L0B/L0C, set L0A=1 (entries are stored
   normalised), `JSR LEVAL` — escape check included.
4. TRUE: discard the saved resume point, continue at the current
   position (= block start, free). Entry stays.
5. FALSE: `DEC L24`, restore the resume point, continue after the
   ENDWHILE.

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

With the REPEAT piggyback (3.3/3.4), option (d):

| Component | Bytes |
|-----------|-------|
| Table entries + emitter hook + LIST hook + dispatch hook | ~79 |
| LPUSH + LEVAL refactors (added to REPEAT/UNTIL) | ~8 |
| WHILE handler (two JSRs + branches + pop) | ~16 |
| ENDWHILE handler (dominated by resume-point save/restore) | ~50 |
| Forward scanner (guard-free byte-pair scan) | ~40 |
| Errors: `Too many loops` retitle +3, `No ENDWHILE` ~11, `No WHILE` ~8 (or 0 if shared) | ~14–22 |
| Stack, init and reset hooks | 0 |
| **Total** | **~210–215** |

(The pre-piggyback standalone design costed ~250 for (d) and
~245–290 for the text fallback (e); the piggyback saves ~40 bytes
and deletes the new-RAM requirement and its verification risk.)

Identified funding beyond the 70 from reverts:

| Source | Frees | Cost |
|--------|-------|------|
| Strip the service call-4 frills (the *BASIC-style command matcher, 'H' prefix, LBF66 tube check, "No TUBE" stack-copied BRK, OSBYTE $8E re-entry). MUST keep the $02/$27 OSBYTE 187 registration (~12 bytes) so the Master MOS's built-in *BASIC still finds us, and the unclaimed-call pass-on path (protocol requirement). | ~100 | Spec-compliant. On a Master nothing is lost; Tube language transfer still works via the header relocation data. Only a 65C02-modified BBC B would lose *BASIC-by-name (use *FX 142). |
| Also drop the *HELP responder (service call 9) | ~30 | Spec-compliant but breaches Acorn's "should respond to *HELP" etiquette — the only documented convention violated by either strip. Restore first from any byte surplus. *ROMS still lists the title. |
| Sign-pack merge (3 identical 8-byte sequences) | ~6 | +12 cycles per real-variable store (acceptable given perf is being traded away) |
| L9DF3 also uses LCPYW | ~9 | +12 cycles per expression evaluation (measurable; last resort) |

Best case: 70 + 100 + 30 + 6 + 9 ≈ **215**, versus ~210–215 needed:
**with the REPEAT piggyback the budget now roughly closes on paper**
— tightly, and only if the service-frill strip (with its behaviour
change) is accepted. Levers at the decision gate if exact sizing runs
over: (a) share `No REPEAT` for stray ENDWHILE (−8); (b) keep
`Too many REPEATs` unretitled (−3); (c) trim the ENDWHILE
resume-point save by using spare zero-page instead of the CPU stack
if a truly dead pair exists; (d) if still short, this becomes the
first customer of the companion-bank design, with the scanner and
error texts in the second bank. Conversely, if sizing comes in under,
spend the surplus on the tag-array hardening (3.3), then on
reinstating Changes 13/14.

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
3. Shared-stack semantics: stray UNTIL/ENDWHILE in malformed programs
   pop each other's entries (see 3.3) — acceptable quirk, document;
   the optional tag array restores precision and is the only thing
   that still needs the page-4 hole verified.
   Also verify LPUSH's Y/L9C80 entry contract from the WHILE hook.
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
2. Do the reverts; re-run suite + benchmarks; commit ("funding" commit).
   Refactor LPUSH/LEVAL in the same commit (behaviour-neutral for
   REPEAT/UNTIL; re-run suite to prove it).
4. Exact-size the components on paper against the freed budget
   (**decision gate**; pick funding levers or the two-bank fallback).
5. Implement recognition + handlers + scanner; error messages last
   (dictionary may want a new entry if `ENDWHILE`/`WHILE` text repeats).
6. Acceptance tests (§6), regression suite, README/OPTIMISATIONS.md
   updates, push.

## 9. Future: multi-line IF...THEN...ELSE...ENDIF (speculation, verified against BASIC V source)

> **Status (July 2026): implemented in reduced form as Change 24** —
> an ELSE-less nested block IF...THEN/ENDIF (ENDIF = $87 $E1), fitted
> into the while variant by the map-free RENUMBER (Change 23) and the
> cold-path extractions, with the forward scanner UNIFIED with the
> WHILE scanner (mode byte in L2D) rather than duplicated. ELSE —
> roughly half the cost estimated below — remains future work, and
> the syntax is forward-compatible with adding it. See
> OPTIMISATIONS.md Change 24.

BASIC V's block IF (`s/Stmt`, labels ELSEBLK/ELSE2/ENDIF) is
**completely stateless** — no control-stack entry exists for it; it is
pure scanning, which makes it structurally *cheaper* than WHILE was.
Two implementation tricks worth copying:

- **Line-hop scanning**: the ELSE/ENDIF search walks line HEADERS
  using the length byte (`LDRB R0,[R2,#3]; ADD R2,R2,R0`) rather than
  scanning every byte — faster than our WHILE scanner, and string/REM
  content is never even looked at.
- **Nesting via trailing THEN**: a nested block IF is detected by
  checking whether a line *ends* with the THEN token — no parsing of
  line contents at all. Block form itself is triggered by THEN
  immediately before the line's CR.

Sketch for BASIC IV: trigger in the IF handler (THEN then CR, ~10
bytes — note IV does not strip trailing spaces, so skip them);
IF-false scan hopping lines via the header length byte, counting
lines that end in $8C, matching line-start ENDIF (a third OFF-pair,
$87 $E7, extending LWTOK/LWLIST/keyword table) or line-start ELSE at
depth 1 (~70 bytes); runtime line-start ELSE = dispatch hook on $8B
(currently an error) that scans to the matching ENDIF (~15 + shared);
ENDIF itself a no-op statement (~8). Unlike BASIC V no second ELSE
token is needed: only statement-START ELSE reaches the dispatch hook,
and classic single-line IF consumes mid-line ELSE internally.
Estimated total ~150–160 bytes plus messages.

Budget: does NOT fit the while variant (1 + 11 stash bytes free).
Plausible homes: (a) the fast variant still carries the ~142-byte
service frills — a "fast + block-IF" variant could strip them exactly
as Change 21 did and fund this; (b) a variant with block-IF instead
of WHILE; (c) the companion-bank design. Interactions to check at
implementation time: WHILE-scan crossing block IFs (fine — token
pairs are position-independent) and block-IF scan crossing WHILE
pairs (fine — different match set); GOTO into/out of blocks behaves
per the usual BASIC IV non-enforcement.
