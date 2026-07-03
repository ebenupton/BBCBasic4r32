# BBC BASIC II Self-Checking Test Suite — Comprehensive Specification

## 1. Preamble

### 1.1 Scope and Target

This document specifies a self-checking test suite for **BBC BASIC II** as shipped on the BBC Microcomputer Model B (post-1982). The normative reference is the *BBC Microcomputer System User Guide* (the "User Guide"), supplemented by the *BBC 1981 BASIC Language Interpreter Outline Specification* and the *Advanced User Guide* for floating-point internals.

The suite is intended to be run on:
- Real BBC Micro hardware (Model B, B+, Master in BASIC II mode)
- Emulators (BeebEm, b-em, JSBeeb, etc.)
- Any compatible BBC BASIC interpreter that claims BASIC II compatibility

### 1.2 Self-Checking Architecture

Every test must be self-checking: it computes an expected result, compares it against the actual result, and reports PASS or FAIL with no human judgement required.

```
10 REM === Test: ABS of negative float ===
20 result = ABS(-4.6)
30 expected = 4.6
40 IF result = expected THEN PRINT "PASS: ABS(-4.6)" ELSE PRINT "FAIL: ABS(-4.6) got ";result
```

#### Test Harness Design

The harness should be a set of BBC BASIC programs (one per major section, or batched into files of manageable size given the ~28K program memory limit on a Model B). Each program should:

1. Initialise a pass counter `P%` and fail counter `F%` (using static integer variables so they survive CHAIN if needed).
2. Define a `PROCcheck(test$, got, expected)` for numeric comparisons, a `PROCcheck_str(test$, got$, expected$)` for string comparisons, and a `PROCcheck_int(test$, got%, expected%)` for integer comparisons.
3. For floating-point comparisons, use an epsilon-based comparison: `IF ABS(got - expected) < 1E-8 THEN ...` (the exact epsilon depending on the precision class of the test).
4. Print a summary line at the end: `PRINT P%;" passed, ";F%;" failed"`.
5. Optionally CHAIN the next test file in sequence.

#### Floating-Point Comparison Tolerance

BBC BASIC II uses 5-byte (40-bit) reals: 8-bit exponent + 32-bit mantissa, giving approximately 9.6 significant decimal digits. The test suite should define three tolerance levels:

- **Exact**: for results that must be bit-identical (integer results stored in reals, string lengths, etc.)
- **Tight** (ε = 1E-9): for basic arithmetic and simple functions where full precision is expected.
- **Loose** (ε = 1E-6): for transcendental functions at extreme arguments, where precision loss is documented.

### 1.3 Naming Convention

Each test should be identified by a hierarchical name: `SECTION.SUBSECTION.CASE`, e.g. `ARITH.ADD.INT_OVERFLOW`, `STR.MID.EMPTY`, `FLOW.FOR.NESTED_10`. These names appear in PASS/FAIL output.

---

## 2. Numeric Representation and Arithmetic

### 2.1 Integer Variables (%)

BBC BASIC II stores integer variables as signed 32-bit two's complement.

#### 2.1.1 Range and Boundaries

| Test ID | Description | Expression | Expected |
|---------|-------------|------------|----------|
| INT.RANGE.MAX | Maximum positive | `A%=2147483647: PRINT A%` | 2147483647 |
| INT.RANGE.MIN | Minimum negative | `A%=-2147483648: PRINT A%` | -2147483648 |
| INT.RANGE.ZERO | Zero | `A%=0: PRINT A%` | 0 |
| INT.RANGE.NEG1 | Minus one | `A%=-1: PRINT A%` | -1 |
| INT.RANGE.WRAP_POS | Overflow wrapping: 2147483647 + 1 | Verify wraps to -2147483648 |
| INT.RANGE.WRAP_NEG | Underflow wrapping: -2147483648 - 1 | Verify wraps to 2147483647 |

#### 2.1.2 Integer Arithmetic

| Test ID | Description | Notes |
|---------|-------------|-------|
| INT.ADD.BASIC | A%=100: B%=200: C%=A%+B% | 300 |
| INT.ADD.NEG | A%=-100: B%=50: C%=A%+B% | -50 |
| INT.ADD.OVERFLOW | A%=2000000000: B%=2000000000: C%=A%+B% | Wraps (verify value) |
| INT.SUB.BASIC | 300-100 | 200 |
| INT.SUB.UNDERFLOW | -2000000000 - 2000000000 | Wraps |
| INT.MUL.BASIC | 100*200 | 20000 |
| INT.MUL.LARGE | 50000*50000 | Verify (may overflow 32 bits → wraps) |
| INT.DIV.EXACT | 100 DIV 10 | 10 |
| INT.DIV.TRUNC | 7 DIV 2 | 3 |
| INT.DIV.NEG | -7 DIV 2 | Verify BBC BASIC's truncation direction |
| INT.DIV.BY_ZERO | Verify "Division by zero" error (ERR=18) |
| INT.MOD.BASIC | 7 MOD 3 | 1 |
| INT.MOD.NEG | -7 MOD 3 | Verify sign convention |
| INT.MOD.ZERO | 7 MOD 0 | Verify "Division by zero" error |

Note: The User Guide describes MOD as "binary unsigned remainder of an integer division". Tests must verify this unsigned behaviour carefully with negative operands.

#### 2.1.3 Hex Notation

| Test ID | Description | Expected |
|---------|-------------|----------|
| INT.HEX.BASIC | A%=&FF | 255 |
| INT.HEX.LARGE | A%=&7FFFFFFF | 2147483647 |
| INT.HEX.FULL32 | A%=&FFFFFFFF | -1 |
| INT.HEX.ZERO | A%=&0 | 0 |
| INT.HEX.MIXED | A%=&DeAdBeEf | Verify case-insensitive parsing |
| INT.HEX.PRINT | PRINT ~255 | FF |

#### 2.1.4 Static Variables (A%–Z%)

| Test ID | Description |
|---------|-------------|
| INT.STATIC.SURVIVE_RUN | Set A%=42, RUN a trivial program, verify A%=42 |
| INT.STATIC.SURVIVE_CLEAR | Set B%=99, execute CLEAR, verify B%=99 |
| INT.STATIC.ALL26 | Assign distinct values to A%–Z%, verify all 26 |

### 2.2 Real (Floating-Point) Variables

5-byte representation: 1 byte exponent (excess-128), 4 bytes mantissa with implied MSB.

#### 2.2.1 Representation and Range

| Test ID | Description | Expected |
|---------|-------------|----------|
| REAL.RANGE.MAX | Largest representable ~1.7E38 | Verify no overflow |
| REAL.RANGE.MIN | Smallest positive ~2.9E-39 | Verify no underflow to zero |
| REAL.RANGE.NEG_MAX | ~-1.7E38 | |
| REAL.RANGE.ZERO | A=0: verify A=0 | |
| REAL.RANGE.OVERFLOW | Computation exceeding range | "Too big" error (ERR=20) |
| REAL.RANGE.NEGZERO | Verify behaviour of -0 if representable |

#### 2.2.2 Precision Tests

| Test ID | Description | Notes |
|---------|-------------|-------|
| REAL.PREC.9SIG | 1/3 * 3 | Should be very close to 1 (within tight ε) |
| REAL.PREC.ASSOC | (0.1 + 0.2) - 0.3 | Verify near-zero (not necessarily exact) |
| REAL.PREC.IDENTITY | X=123456789: verify X prints with 9 sig figs | |
| REAL.PREC.SMALL_DIFF | 1000000.01 - 1000000.00 | Verify ≈0.01 (tests mantissa alignment) |
| REAL.PREC.LARGE_ADD | 1E30 + 1 | Should equal 1E30 (1 lost to rounding) |
| REAL.PREC.SUBNORM | Very small values near underflow | |

#### 2.2.3 Real Arithmetic

For each operation, test: positive×positive, positive×negative, negative×negative, zero cases, and precision-edge cases.

| Test ID | Operation | Key cases |
|---------|-----------|-----------|
| REAL.ADD.* | Addition | 0+0, 1+0, -1+1, 0.1+0.2, 1E38+1E38 (overflow) |
| REAL.SUB.* | Subtraction | Cancellation, sign flip, near-equal large numbers |
| REAL.MUL.* | Multiplication | 1*X, 0*X, -1*X, large*large (overflow), small*small |
| REAL.DIV.* | Division | X/1, X/X, 1/3, 1/0 (error), 0/0 (error), tiny/huge |
| REAL.POW.* | Exponentiation (^) | 2^10, 2^0, 2^-1, 0^0, (-1)^2, (-2)^3, 0^(-1) error, fractional powers |

#### 2.2.4 Mixed Integer/Real Arithmetic

| Test ID | Description |
|---------|-------------|
| MIXED.ADD | A%=5: B=2.5: C=A%+B | 7.5 |
| MIXED.ASSIGN_REAL_TO_INT | A%=3.7 | Verify truncation to 3 |
| MIXED.ASSIGN_INT_TO_REAL | A=5% ... wait, A=B% where B%=42 | 42.0 |
| MIXED.EXPR | (A%+1)/2 where A%=5 | 3 (integer division) vs 3.0 |
| MIXED.DIV_BEHAVIOUR | Verify: integer/integer gives integer; integer/real gives real |

### 2.3 Operator Precedence

The User Guide defines precedence (highest to lowest):
1. Unary minus, NOT, functions, procedures, (), indirection
2. ^
3. *, /, MOD, DIV
4. +, -
5. =, <, >, <=, >=, <>
6. AND
7. OR, EOR

| Test ID | Expression | Expected | Precedence tested |
|---------|------------|----------|-------------------|
| PREC.MUL_ADD | 2+3*4 | 14 | * before + |
| PREC.POW_MUL | 2*3^2 | 18 | ^ before * |
| PREC.UNARY | -3^2 | 9 ((-3)^2) or -9? | Unary minus vs ^ |
| PREC.AND_OR | 1 OR 2 AND 4 | Verify AND before OR |
| PREC.CMP_AND | 3>2 AND 5>4 | TRUE (-1) | > before AND |
| PREC.PARENS | (2+3)*4 | 20 | Parentheses override |
| PREC.NESTED | ((2+3)*4)^2 | 400 | Nested parens |
| PREC.DIV_MOD | 10 DIV 3 * 3 + 10 MOD 3 | 10 | DIV/MOD same level as * |
| PREC.NOT | NOT 0 | -1 (TRUE) | Unary NOT |
| PREC.NOT_AND | NOT 0 AND &FF | 255 or -1 AND 255 = 255 | NOT before AND |
| PREC.CHAIN | 2^3^2 | Verify right-to-left or left-to-right associativity |
| PREC.ALL | Complex expression testing all 7 levels simultaneously |

### 2.4 Comparison Operators

Test each of `=`, `<>`, `<`, `>`, `<=`, `>=` with:
- Integer vs integer (same, less, greater)
- Real vs real
- Integer vs real (mixed comparison)
- Negative numbers
- Zero
- Equal values (boundary case for < vs <=)
- String vs string (all six operators on strings)

The comparison operators return 0 (FALSE) or -1 (TRUE) as integers.

| Test ID | Expression | Expected |
|---------|------------|----------|
| CMP.EQ.INT_TRUE | 5=5 | -1 |
| CMP.EQ.INT_FALSE | 5=6 | 0 |
| CMP.EQ.REAL | 0.1+0.2 = 0.3 | 0 or -1 (platform-dependent; document actual) |
| CMP.NE.BASIC | 5<>6 | -1 |
| CMP.LT.NEG | -5 < -3 | -1 |
| CMP.GE.BOUNDARY | 5>=5 | -1 |
| CMP.STR.EQ | "ABC"="ABC" | -1 |
| CMP.STR.LT | "ABC"<"ABD" | -1 |
| CMP.STR.CASE | "abc"<"ABC" or "abc">"ABC" | Verify ASCII ordering |
| CMP.STR.LEN | "AB"<"ABC" | -1 (shorter string < longer with same prefix) |
| CMP.STR.EMPTY | ""="" | -1 |
| CMP.STR.EMPTY_LT | ""<"A" | -1 |

### 2.5 Bitwise Operators

AND, OR, EOR (XOR) operate on 32-bit integers.

| Test ID | Expression | Expected |
|---------|------------|----------|
| BIT.AND.BASIC | &FF00 AND &0FF0 | &0F00 (3840) |
| BIT.AND.ZERO | &FFFF AND 0 | 0 |
| BIT.AND.SELF | &DEAD AND &DEAD | &DEAD |
| BIT.OR.BASIC | &FF00 OR &00FF | &FFFF (65535) |
| BIT.OR.ZERO | 0 OR 0 | 0 |
| BIT.EOR.BASIC | &FF00 EOR &0FF0 | &F0F0 |
| BIT.EOR.SELF | &DEAD EOR &DEAD | 0 |
| BIT.EOR.INVERT | &FFFFFFFF EOR &FFFFFFFF | 0 |
| BIT.NOT.ZERO | NOT 0 | -1 (&FFFFFFFF) |
| BIT.NOT.TRUE | NOT -1 | 0 |
| BIT.NOT.FF | NOT &FF | &FFFFFF00 |
| BIT.COMBO | (A% AND &F0) OR (B% AND &0F) | Nibble merge test |

---

## 3. Mathematical Functions

### 3.1 Trigonometric Functions

All work in radians. Test at: 0, π/6, π/4, π/3, π/2, π, 3π/2, 2π, negative angles, very large angles (accuracy loss boundary), and values near domain boundaries.

#### 3.1.1 SIN

| Test ID | Argument | Expected | Tolerance |
|---------|----------|----------|-----------|
| TRIG.SIN.ZERO | SIN(0) | 0 | Exact |
| TRIG.SIN.PI6 | SIN(PI/6) | 0.5 | Tight |
| TRIG.SIN.PI4 | SIN(PI/4) | 0.707106781 | Tight |
| TRIG.SIN.PI2 | SIN(PI/2) | 1 | Tight |
| TRIG.SIN.PI | SIN(PI) | 0 | Tight |
| TRIG.SIN.NEG | SIN(-PI/2) | -1 | Tight |
| TRIG.SIN.LARGE | SIN(1E8) | Verify no error, result in [-1,1] | Loose |
| TRIG.SIN.HUGE | SIN(1E18) | "Accuracy lost" error (ERR=23)? Or very imprecise? |
| TRIG.SIN.IDENTITY | SIN(X)^2 + COS(X)^2 for several X | 1.0 within tight ε |

#### 3.1.2 COS

Mirror of SIN tests with phase shift. Also:

| Test ID | Argument | Expected |
|---------|----------|----------|
| TRIG.COS.ZERO | COS(0) | 1 |
| TRIG.COS.PI2 | COS(PI/2) | 0 (within tight ε) |
| TRIG.COS.PI | COS(PI) | -1 |

#### 3.1.3 TAN

| Test ID | Argument | Expected |
|---------|----------|----------|
| TRIG.TAN.ZERO | TAN(0) | 0 |
| TRIG.TAN.PI4 | TAN(PI/4) | 1 (tight ε) |
| TRIG.TAN.NEAR_PI2 | TAN(1.5707) | Very large positive |
| TRIG.TAN.PI | TAN(PI) | 0 (tight ε) |
| TRIG.TAN.IDENTITY | TAN(X) = SIN(X)/COS(X) for several X |

#### 3.1.4 Inverse Trigonometric Functions

**ASN** (arc sine): domain [-1, 1], range [-π/2, π/2]

| Test ID | Argument | Expected |
|---------|----------|----------|
| TRIG.ASN.ZERO | ASN(0) | 0 |
| TRIG.ASN.HALF | ASN(0.5) | π/6 |
| TRIG.ASN.ONE | ASN(1) | π/2 |
| TRIG.ASN.NEG | ASN(-1) | -π/2 |
| TRIG.ASN.OUT_OF_RANGE | ASN(2) | Error (verify which error) |
| TRIG.ASN.ROUNDTRIP | SIN(ASN(0.3)) | 0.3 |

**ACS** (arc cosine): domain [-1, 1], range [0, π]

| Test ID | Argument | Expected |
|---------|----------|----------|
| TRIG.ACS.ZERO | ACS(0) | π/2 |
| TRIG.ACS.ONE | ACS(1) | 0 |
| TRIG.ACS.NEG | ACS(-1) | π |
| TRIG.ACS.HALF | ACS(0.5) | π/3 |
| TRIG.ACS.OUT_OF_RANGE | ACS(1.1) | Error |
| TRIG.ACS.ROUNDTRIP | COS(ACS(0.3)) | 0.3 |

**ATN** (arc tangent): domain all reals, range (-π/2, π/2)

| Test ID | Argument | Expected |
|---------|----------|----------|
| TRIG.ATN.ZERO | ATN(0) | 0 |
| TRIG.ATN.ONE | ATN(1) | π/4 |
| TRIG.ATN.LARGE | ATN(1E10) | ≈π/2 |
| TRIG.ATN.NEG | ATN(-1) | -π/4 |
| TRIG.ATN.ROUNDTRIP | TAN(ATN(2.5)) | 2.5 |

### 3.2 Logarithmic and Exponential Functions

#### 3.2.1 LN (Natural Logarithm)

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.LN.ONE | LN(1) | 0 |
| MATH.LN.E | LN(EXP(1)) | 1 |
| MATH.LN.10 | LN(10) | 2.30258509 |
| MATH.LN.SMALL | LN(1E-10) | ≈-23.026 |
| MATH.LN.LARGE | LN(1E38) | ≈87.498 |
| MATH.LN.ZERO | LN(0) | "Log range" error (ERR=22) |
| MATH.LN.NEG | LN(-1) | "Log range" error (ERR=22) |
| MATH.LN.ROUNDTRIP | EXP(LN(42)) | 42 |

#### 3.2.2 LOG (Log base 10)

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.LOG.ONE | LOG(1) | 0 |
| MATH.LOG.TEN | LOG(10) | 1 |
| MATH.LOG.HUNDRED | LOG(100) | 2 |
| MATH.LOG.SMALL | LOG(0.001) | -3 |
| MATH.LOG.ZERO | LOG(0) | "Log range" error |
| MATH.LOG.RELATION | LOG(X) = LN(X)/LN(10) for several X |

#### 3.2.3 EXP

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.EXP.ZERO | EXP(0) | 1 |
| MATH.EXP.ONE | EXP(1) | 2.71828183 |
| MATH.EXP.NEG | EXP(-1) | 0.367879441 |
| MATH.EXP.OVERFLOW | EXP(89) | "Exp range" error (ERR=24) |
| MATH.EXP.LARGE_NEG | EXP(-100) | 0 or very small (verify underflow) |
| MATH.EXP.IDENTITY | EXP(LN(X)) = X for several X values |

### 3.3 Other Numeric Functions

#### 3.3.1 ABS

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.ABS.POS | ABS(4) | 4 |
| MATH.ABS.NEG | ABS(-4.6) | 4.6 |
| MATH.ABS.ZERO | ABS(0) | 0 |
| MATH.ABS.INT | ABS(A%) where A%=-42 | 42 |
| MATH.ABS.MININT | ABS(-2147483648) | Verify (may overflow if stored as int) |

#### 3.3.2 SGN

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.SGN.POS | SGN(42) | 1 |
| MATH.SGN.NEG | SGN(-3.7) | -1 |
| MATH.SGN.ZERO | SGN(0) | 0 |

#### 3.3.3 SQR

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.SQR.FOUR | SQR(4) | 2 |
| MATH.SQR.TWO | SQR(2) | 1.41421356 |
| MATH.SQR.ZERO | SQR(0) | 0 |
| MATH.SQR.ONE | SQR(1) | 1 |
| MATH.SQR.LARGE | SQR(1E30) | 1E15 |
| MATH.SQR.SMALL | SQR(1E-20) | 1E-10 |
| MATH.SQR.NEG | SQR(-1) | "-ve root" error (ERR=21) |
| MATH.SQR.ROUNDTRIP | SQR(X)*SQR(X) = X for several X |

#### 3.3.4 INT

| Test ID | Argument | Expected |
|---------|----------|----------|
| MATH.INT.POS | INT(3.7) | 3 |
| MATH.INT.NEG | INT(-3.7) | -4 (floor, not truncation!) |
| MATH.INT.ALREADY | INT(5) | 5 |
| MATH.INT.ZERO | INT(0) | 0 |
| MATH.INT.NEG_EXACT | INT(-3.0) | -3 |
| MATH.INT.JUST_BELOW | INT(2.999999999) | 2 |

The User Guide is clear: INT truncates toward negative infinity (floor function), NOT toward zero.

#### 3.3.5 DEG and RAD

| Test ID | Expression | Expected |
|---------|------------|----------|
| MATH.DEG.PI | DEG(PI) | 180 |
| MATH.DEG.PI2 | DEG(PI/2) | 90 |
| MATH.RAD.180 | RAD(180) | PI |
| MATH.RAD.90 | RAD(90) | PI/2 |
| MATH.DEG_RAD.ROUNDTRIP | DEG(RAD(X)) = X for several X |
| MATH.RAD_DEG.ROUNDTRIP | RAD(DEG(X)) = X for several X |

#### 3.3.6 PI

| Test ID | Expression | Expected |
|---------|------------|----------|
| MATH.PI.VALUE | PI | 3.14159265 (9 sig figs) |
| MATH.PI.PRECISION | PI - 3.14159265 | Very small residual (< 1E-8) |
| MATH.PI.READONLY | Verify PI cannot be assigned to |

### 3.4 RND (Random Number Generator)

| Test ID | Description |
|---------|-------------|
| RND.BARE | X%=RND: verify 32-bit integer |
| RND.UNIT | X=RND(1): verify 0 < X < 1 |
| RND.RANGE | X=RND(6): verify integer 1 ≤ X ≤ 6, over many iterations |
| RND.RANGE_1 | X=RND(1) in integer context: same as RND(1)? |
| RND.REPEAT | RND(0) returns same value as last RND call |
| RND.SEED_NEG | RND(-N) seeds the generator; verify deterministic sequence after seed |
| RND.DETERMINISM | Seed with same value twice, verify identical sequence of 100 values |
| RND.DISTRIBUTION | Generate 6000 values of RND(6), verify each face appears ~1000 times (±15%) |
| RND.ZERO | RND(0) behaviour |

---

## 4. String Operations

### 4.1 String Variables and Assignment

| Test ID | Description |
|---------|-------------|
| STR.ASSIGN.BASIC | A$="HELLO": verify A$="HELLO" |
| STR.ASSIGN.EMPTY | A$="": verify LEN(A$)=0 |
| STR.ASSIGN.MAX | A$=STRING$(255,"X"): verify LEN(A$)=255 |
| STR.ASSIGN.OVERFLOW | Attempt to create string >255 chars: "String too long" error (ERR=19) |
| STR.ASSIGN.SPECIAL | String containing quotes: A$=CHR$(34) |
| STR.ASSIGN.QUOTE | A$="""": verify this is a single quote char |

### 4.2 String Concatenation

| Test ID | Description |
|---------|-------------|
| STR.CAT.BASIC | "ABC"+"DEF" = "ABCDEF" |
| STR.CAT.EMPTY | "ABC"+"" = "ABC" |
| STR.CAT.BOTH_EMPTY | ""+"" = "" |
| STR.CAT.OVERFLOW | STRING$(200,"X")+STRING$(200,"Y") → "String too long" |
| STR.CAT.BOUNDARY | STRING$(127,"X")+STRING$(128,"Y"): verify LEN=255 |

### 4.3 String Functions

#### 4.3.1 LEN

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.LEN.BASIC | LEN("HELLO") | 5 |
| STR.LEN.EMPTY | LEN("") | 0 |
| STR.LEN.MAX | LEN(STRING$(255,"X")) | 255 |
| STR.LEN.SPACES | LEN("   ") | 3 |
| STR.LEN.CHR0 | LEN(CHR$(0)) | 1 |

#### 4.3.2 LEFT$

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.LEFT.BASIC | LEFT$("HELLO",3) | "HEL" |
| STR.LEFT.ZERO | LEFT$("HELLO",0) | "" |
| STR.LEFT.ALL | LEFT$("HELLO",5) | "HELLO" |
| STR.LEFT.EXCESS | LEFT$("HELLO",10) | "HELLO" (no error, returns whole string) |
| STR.LEFT.EMPTY | LEFT$("",3) | "" |

#### 4.3.3 RIGHT$

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.RIGHT.BASIC | RIGHT$("HELLO",3) | "LLO" |
| STR.RIGHT.ZERO | RIGHT$("HELLO",0) | "" |
| STR.RIGHT.ALL | RIGHT$("HELLO",5) | "HELLO" |
| STR.RIGHT.EXCESS | RIGHT$("HELLO",10) | "HELLO" |
| STR.RIGHT.EMPTY | RIGHT$("",3) | "" |

#### 4.3.4 MID$

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.MID.BASIC | MID$("HELLO",2,3) | "ELL" |
| STR.MID.FROM_START | MID$("HELLO",1,3) | "HEL" |
| STR.MID.TO_END | MID$("HELLO",3,10) | "LLO" (excess count OK) |
| STR.MID.ONE_CHAR | MID$("HELLO",3,1) | "L" |
| STR.MID.ZERO_LEN | MID$("HELLO",3,0) | "" |
| STR.MID.PAST_END | MID$("HELLO",10,3) | "" |
| STR.MID.EMPTY | MID$("",1,1) | "" |
| STR.MID.POS_ZERO | MID$("HELLO",0,3) | Verify error or behaviour |

#### 4.3.5 CHR$ and ASC

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.CHR.BASIC | CHR$(65) | "A" |
| STR.CHR.ZERO | CHR$(0) | String of length 1 containing NUL |
| STR.CHR.MAX | CHR$(255) | Character 255 |
| STR.CHR.SPACE | CHR$(32) | " " |
| STR.ASC.BASIC | ASC("A") | 65 |
| STR.ASC.LOWER | ASC("a") | 97 |
| STR.ASC.MULTI | ASC("HELLO") | 72 (first char only) |
| STR.ASC.SPACE | ASC(" ") | 32 |
| STR.ASC.EMPTY | ASC("") | -1 (BBC BASIC II returns -1 for null string) |
| STR.CHR_ASC.ROUNDTRIP | CHR$(ASC(A$)) = LEFT$(A$,1) for non-empty A$ |
| STR.ASC_CHR.ROUNDTRIP | ASC(CHR$(N)) = N for 0..255 |

#### 4.3.6 STR$ and VAL

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.STR.POS | STR$(42) | "42" |
| STR.STR.NEG | STR$(-3.5) | "-3.5" |
| STR.STR.ZERO | STR$(0) | "0" |
| STR.STR.REAL | STR$(PI) | "3.14159265" (verify format) |
| STR.STR.LARGE | STR$(1E20) | Verify scientific notation |
| STR.VAL.INT | VAL("42") | 42 |
| STR.VAL.REAL | VAL("3.14") | 3.14 |
| STR.VAL.NEG | VAL("-5") | -5 |
| STR.VAL.LEADING_SP | VAL(" 42") | 42 (leading spaces OK) |
| STR.VAL.GARBAGE | VAL("HELLO") | 0 |
| STR.VAL.PARTIAL | VAL("42ABC") | 42 (parses up to non-numeric) |
| STR.VAL.EMPTY | VAL("") | 0 |
| STR.VAL.HEX | Verify: does VAL handle "&FF"? (implementation-dependent) |
| STR.ROUNDTRIP | VAL(STR$(X)) = X for several X |

#### 4.3.7 INSTR

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.INSTR.FOUND | INSTR("HELLO WORLD","WORLD") | 7 |
| STR.INSTR.NOT_FOUND | INSTR("HELLO","WORLD") | 0 |
| STR.INSTR.START | INSTR("HELLO","HE") | 1 |
| STR.INSTR.END | INSTR("HELLO","LO") | 4 |
| STR.INSTR.SINGLE | INSTR("HELLO","L") | 3 (first occurrence) |
| STR.INSTR.EMPTY_NEEDLE | INSTR("HELLO","") | 1 or 0? (verify) |
| STR.INSTR.EMPTY_HAY | INSTR("","X") | 0 |
| STR.INSTR.OFFSET | INSTR("ABCABC","AB",2) | 4 (search from position 2) |
| STR.INSTR.OFFSET_MISS | INSTR("ABCABC","AB",5) | 0 |
| STR.INSTR.CASE | INSTR("Hello","hello") | 0 (case-sensitive) |
| STR.INSTR.SELF | INSTR(A$,A$) | 1 |

#### 4.3.8 STRING$

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.STRING.BASIC | STRING$(3,"AB") | "ABABAB" |
| STR.STRING.ONE | STRING$(1,"XY") | "XY" |
| STR.STRING.ZERO | STRING$(0,"AB") | "" |
| STR.STRING.CHAR | STRING$(5,"*") | "*****" |
| STR.STRING.MAX | STRING$(255,"X") | 255 X's... actually verify if this overflows: 255*1=255 OK |
| STR.STRING.OVERFLOW | STRING$(200,"AB") | 400 chars → "String too long" |

### 4.4 EVAL

| Test ID | Expression | Expected |
|---------|------------|----------|
| STR.EVAL.ARITH | EVAL("2+3") | 5 |
| STR.EVAL.VAR | A=10: EVAL("A*2") | 20 |
| STR.EVAL.STRING | EVAL("""HELLO""") | "HELLO" (returns string) |
| STR.EVAL.FUNC | EVAL("SIN(1)") | SIN(1) |
| STR.EVAL.NESTED | A$="2+3": EVAL(A$) | 5 |
| STR.EVAL.ERROR | EVAL("1/0") | "Division by zero" |

---

## 5. Variables and Arrays

### 5.1 Variable Naming

| Test ID | Description |
|---------|-------------|
| VAR.NAME.SINGLE | A=1: verify |
| VAR.NAME.LONG | LongVariableName=42: verify |
| VAR.NAME.CASE | A=1: a=2: verify A<>a (case-sensitive) |
| VAR.NAME.EMBEDDED_KW | FORTUNE=1: verify (contains FOR, but embedded keywords allowed) |
| VAR.NAME.UNDERSCORE | my_var=5: verify |
| VAR.NAME.DIGITS | A1=1: A2=2: verify distinct |
| VAR.NAME.TYPES | A=1.5: A%=2: A$="X": verify all three are independent |
| VAR.NAME.NOSUCH | Attempt to PRINT undeclared variable → "No such variable" error (ERR=26) |

### 5.2 Arrays

#### 5.2.1 DIM and Access

| Test ID | Description |
|---------|-------------|
| ARR.DIM.1D | DIM A(10): verify 11 elements (0-10) |
| ARR.DIM.2D | DIM B(3,4): verify 4×5=20 elements |
| ARR.DIM.3D | DIM C(2,2,2): verify 27 elements |
| ARR.DIM.ZERO | DIM D(0): verify 1 element |
| ARR.DIM.STRING | DIM E$(5): verify string array |
| ARR.DIM.INT | DIM F%(5): verify integer array |
| ARR.DIM.INIT | After DIM, verify all elements are 0 (numeric) or "" (string) |
| ARR.DIM.REDIM | Attempt to DIM an already-DIMmed array → error |

#### 5.2.2 Array Access

| Test ID | Description |
|---------|-------------|
| ARR.ACCESS.BASIC | DIM A(5): A(3)=42: verify A(3)=42 |
| ARR.ACCESS.2D | DIM B(3,3): B(1,2)=99: verify |
| ARR.ACCESS.ZERO_IDX | A(0)=1: verify |
| ARR.ACCESS.MAX_IDX | DIM A(100): A(100)=1: verify |
| ARR.ACCESS.NEG_IDX | A(-1) → "Subscript" error (ERR=15) |
| ARR.ACCESS.OVER_IDX | A(101) where DIM A(100) → "Subscript" error |

### 5.3 Pseudo-Variables

| Test ID | Description |
|---------|-------------|
| PVAR.PAGE | Verify PAGE returns sensible address (multiple of 256) |
| PVAR.TOP | Verify TOP > PAGE (program exists) |
| PVAR.HIMEM | Verify HIMEM > TOP |
| PVAR.LOMEM | Verify LOMEM >= TOP |
| PVAR.TIME.READ | T=TIME: verify is numeric |
| PVAR.TIME.WRITE | TIME=0: FOR I=1 TO 1000: NEXT: T=TIME: verify T>0 |
| PVAR.TIME.MONOTONE | T1=TIME: T2=TIME: verify T2>=T1 |

### 5.4 Indirection Operators

| Test ID | Description |
|---------|-------------|
| INDIR.QUERY.WRITE | ?&70=42: verify ?&70=42 (8-bit byte) |
| INDIR.QUERY.RANGE | ?addr=256: verify ?addr=0 (wraps to byte) |
| INDIR.BANG.WRITE | !&70=&12345678: verify !&70=&12345678 (32-bit word) |
| INDIR.BANG.BYTES | After !&70=&12345678, verify ?&70=&78, ?&71=&56 etc. (little-endian) |
| INDIR.DOLLAR.WRITE | $&70="HELLO"+CHR$(13): verify $&70="HELLO" (CR-terminated) |
| INDIR.DOLLAR.READ | Verify $addr reads until CR |

---

## 6. Control Flow

### 6.1 IF...THEN...ELSE

| Test ID | Description |
|---------|-------------|
| FLOW.IF.TRUE | IF 1 THEN A=1 ELSE A=2: verify A=1 |
| FLOW.IF.FALSE | IF 0 THEN A=1 ELSE A=2: verify A=2 |
| FLOW.IF.NO_ELSE | IF 0 THEN A=1: verify A not set (or retains old value) |
| FLOW.IF.GOTO | IF 1 THEN GOTO target: verify jumps |
| FLOW.IF.LINE_NUM | IF 1 THEN 100 (line number after THEN) |
| FLOW.IF.MULTI_STMT | IF 1 THEN A=1:B=2:C=3 — all three execute |
| FLOW.IF.NESTED | IF 1 THEN IF 0 THEN A=1 ELSE A=2: verify A=2 (ELSE binds to nearest IF) |
| FLOW.IF.EXPR | IF A%>5 AND A%<10 THEN ... |
| FLOW.IF.STRING | IF A$="YES" THEN ... |

### 6.2 FOR...NEXT

| Test ID | Description |
|---------|-------------|
| FLOW.FOR.BASIC | FOR I=1 TO 5: count: NEXT: verify count=5 |
| FLOW.FOR.STEP | FOR I=0 TO 10 STEP 2: verify values 0,2,4,6,8,10 |
| FLOW.FOR.NEG_STEP | FOR I=10 TO 1 STEP -1: verify 10 iterations |
| FLOW.FOR.REAL_STEP | FOR I=0 TO 1 STEP 0.1: count iterations (≈11 but verify edge case) |
| FLOW.FOR.ZERO_BODY | FOR I=5 TO 1 (no STEP -1): verify executes once (always executes at least once) |
| FLOW.FOR.NESTED | FOR I=1 TO 3: FOR J=1 TO 3: count: NEXT J: NEXT I: verify 9 |
| FLOW.FOR.DEEP_NEST | 10 nested FOR loops: verify correct execution |
| FLOW.FOR.INT_VAR | FOR I%=1 TO 1000: verify faster than real |
| FLOW.FOR.EXIT_VALUE | FOR I=1 TO 5: NEXT: verify I=6 (one past end) |
| FLOW.FOR.STEP_ZERO | FOR I=1 TO 5 STEP 0: verify error (ERR=35 in later BASICs, may differ in BASIC II) |
| FLOW.FOR.VAR_BOUNDS | S=1: E=5: FOR I=S TO E: verify works with variable bounds |
| FLOW.FOR.BODY_MODIFY | FOR I=1 TO 5: I=10: NEXT: verify terminates (modifying control variable) |
| FLOW.FOR.REUSE_VAR | FOR I=1 TO 3: FOR I=1 TO 2: NEXT: NEXT: verify behaviour |

### 6.3 REPEAT...UNTIL

| Test ID | Description |
|---------|-------------|
| FLOW.RPT.BASIC | REPEAT: A=A+1: UNTIL A=5: verify A=5 |
| FLOW.RPT.ONCE | REPEAT: UNTIL TRUE: verify executes body once |
| FLOW.RPT.NESTED | Nested REPEAT...UNTIL: verify correct pairing |
| FLOW.RPT.CONDITION | REPEAT ... UNTIL A$="QUIT" (string condition) |
| FLOW.RPT.COMPLEX | REPEAT ... UNTIL A>5 AND B<10 |

### 6.4 WHILE...ENDWHILE

Note: the User Guide spec says this may not be in initial release. Verify whether BASIC II includes it (it was not included in the shipped 6502 BASIC II ROM — test for "Mistake" error to confirm absence, or test functionality if present).

| Test ID | Description |
|---------|-------------|
| FLOW.WHILE.PRESENT | Attempt WHILE TRUE: ENDWHILE: check if syntax error |
| FLOW.WHILE.BASIC | WHILE A<5: A=A+1: ENDWHILE: verify A=5 (if implemented) |
| FLOW.WHILE.ZERO_ITER | WHILE FALSE: should not execute body |

### 6.5 GOTO and GOSUB/RETURN

| Test ID | Description |
|---------|-------------|
| FLOW.GOTO.BASIC | GOTO target line: verify jump |
| FLOW.GOTO.FORWARD | Jump forward |
| FLOW.GOTO.BACKWARD | Jump backward |
| FLOW.GOTO.NOSUCH | GOTO non-existent line → "No such line" error (ERR=41) |
| FLOW.GOSUB.BASIC | GOSUB routine: RETURN: verify returns to correct point |
| FLOW.GOSUB.NESTED | GOSUB from within GOSUB: verify both return correctly |
| FLOW.GOSUB.DEEP | 10+ nested GOSUBs: verify stack handles depth |
| FLOW.GOSUB.NO_RETURN | GOSUB without RETURN → "No GOSUB" error when RETURN encountered elsewhere? |

### 6.6 ON...GOTO / ON...GOSUB

| Test ID | Description |
|---------|-------------|
| FLOW.ON.GOTO_1 | ON 1 GOTO 100,200,300: verify goes to 100 |
| FLOW.ON.GOTO_2 | ON 2 GOTO 100,200,300: verify goes to 200 |
| FLOW.ON.GOTO_3 | ON 3 GOTO 100,200,300: verify goes to 300 |
| FLOW.ON.GOTO_RANGE | ON 0 GOTO 100,200: verify ELSE branch or error (ERR=40) |
| FLOW.ON.GOTO_EXCESS | ON 4 GOTO 100,200,300: verify ELSE branch or error |
| FLOW.ON.GOTO_ELSE | ON X GOTO 100,200 ELSE 999: verify ELSE works |
| FLOW.ON.GOSUB | ON N GOSUB 100,200: verify subroutine call and return |

### 6.7 PROC/FN (Structured Programming)

#### 6.7.1 Procedures

| Test ID | Description |
|---------|-------------|
| PROC.BASIC | DEF PROCtest: PRINT "OK": ENDPROC — call PROCtest |
| PROC.PARAM | DEF PROCadd(A,B): PRINT A+B: ENDPROC |
| PROC.MULTI_PARAM | DEF PROCfoo(A,B,C$): verify all params passed |
| PROC.LOCAL | DEF PROCfoo: LOCAL X: X=99: ENDPROC — verify X restored after call |
| PROC.RECURSIVE | DEF PROCfact(N): IF N>1 THEN PROCfact(N-1) ... recursive call |
| PROC.NESTED_CALL | PROCa calls PROCb: verify correct return |
| PROC.NO_DEF | Call undefined PROC → "No such FN/PROC" error (ERR=29) |

#### 6.7.2 Functions

| Test ID | Description |
|---------|-------------|
| FN.BASIC | DEF FNdouble(X) = X*2: verify FNdouble(5)=10 |
| FN.STRING | DEF FN$reverse(A$): ... : ="reversed": verify returns string |
| FN.MULTI_LINE | DEF FNfoo(X): LOCAL Y: Y=X*2: =Y+1 |
| FN.RECURSIVE | DEF FNfact(N): IF N<=1 THEN =1 ELSE =N*FNfact(N-1) |
| FN.NESTED | FNa calls FNb: verify |
| FN.LOCAL | Verify LOCAL variables are truly local and restored |
| FN.EXPR | Use FN in expression: A = FNdouble(3) + FNdouble(4) | 14 |
| FN.SIDE_EFFECT | Function modifying global variable: verify |
| FN.NO_DEF | Call undefined FN → error |

### 6.8 DATA/READ/RESTORE

| Test ID | Description |
|---------|-------------|
| DATA.READ.INT | DATA 1,2,3: READ A,B,C: verify 1,2,3 |
| DATA.READ.REAL | DATA 3.14,2.72: READ A,B |
| DATA.READ.STRING | DATA "HELLO","WORLD": READ A$,B$ |
| DATA.READ.MIXED | DATA 42,"FRED",3.14: READ A,B$,C |
| DATA.READ.MULTI_LINE | DATA across multiple lines: verify sequential reading |
| DATA.READ.OVERFLOW | READ past end of DATA → "Out of DATA" error (ERR=42) |
| DATA.RESTORE.BASIC | RESTORE: verify reads from start again |
| DATA.RESTORE.LINE | RESTORE 100: verify reads from line 100 |
| DATA.READ.UNQUOTED | DATA HELLO: READ A$: verify A$="HELLO" (unquoted string) |
| DATA.READ.COMMA | DATA "A,B": READ A$: verify A$="A,B" (quoted comma) |
| DATA.READ.SPACES | DATA " HELLO": verify leading space handling |

---

## 7. PRINT Formatting

### 7.1 Basic PRINT

| Test ID | Description | Expected output |
|---------|-------------|-----------------|
| PRINT.STRING | PRINT "HELLO" | HELLO |
| PRINT.NUM.INT | PRINT 42 | 42 (with leading space for sign) |
| PRINT.NUM.NEG | PRINT -42 | -42 |
| PRINT.NUM.REAL | PRINT 3.14 | 3.14 |
| PRINT.NUM.ZERO | PRINT 0 | 0 |
| PRINT.NUM.SMALL | PRINT 0.001 | 0.001 |
| PRINT.NUM.SCI | PRINT 1E20 | Verify scientific notation format |

### 7.2 Print Separators

| Test ID | Description | Behaviour |
|---------|-------------|-----------|
| PRINT.SEP.SEMI | PRINT "A";"B" | AB (no space) |
| PRINT.SEP.COMMA | PRINT "A","B" | A followed by tab to next zone, then B |
| PRINT.SEP.APOST | PRINT "A"'"B" | A on first line, B on second |
| PRINT.SEP.TRAILING_SEMI | PRINT "A";: PRINT "B" | AB on same line |
| PRINT.SEP.NO_TRAILING | PRINT "A": PRINT "B" | A and B on separate lines |
| PRINT.SEP.ZONE_WIDTH | Verify print zones are 10 characters wide |

### 7.3 TAB and SPC

| Test ID | Description |
|---------|-------------|
| PRINT.TAB.BASIC | PRINT TAB(10);"X": verify X at column 10 |
| PRINT.TAB.XY | PRINT TAB(5,10);"X": verify cursor at (5,10) |
| PRINT.TAB.ZERO | PRINT TAB(0);"X": verify at column 0 |
| PRINT.SPC.BASIC | PRINT SPC(5);"X": verify 5 spaces before X |
| PRINT.SPC.ZERO | PRINT SPC(0);"X": verify no extra spaces |

### 7.4 Print Formatting (~ for hex)

| Test ID | Description | Expected |
|---------|-------------|----------|
| PRINT.HEX.BASIC | PRINT ~255 | FF |
| PRINT.HEX.LARGE | PRINT ~65535 | FFFF |
| PRINT.HEX.ZERO | PRINT ~0 | 0 |
| PRINT.HEX.NEG | PRINT ~-1 | FFFFFFFF |

### 7.5 WIDTH

| Test ID | Description |
|---------|-------------|
| PRINT.WIDTH.SET | WIDTH 40: verify line wraps at 40 |
| PRINT.WIDTH.ZERO | WIDTH 0: verify no wrapping |

### 7.6 COUNT and POS/VPOS

| Test ID | Description |
|---------|-------------|
| PRINT.COUNT.BASIC | PRINT "HELLO";: verify COUNT=5 |
| PRINT.COUNT.NEWLINE | PRINT "HI": verify COUNT=0 after newline |
| PRINT.POS.BASIC | Verify POS returns current horizontal cursor position |
| PRINT.VPOS.BASIC | Verify VPOS returns current vertical cursor position |

---

## 8. Error Handling

### 8.1 ON ERROR

| Test ID | Description |
|---------|-------------|
| ERR.ONERR.BASIC | ON ERROR GOTO handler: trigger error: verify handler called |
| ERR.ONERR.ERR | After error, verify ERR returns correct error number |
| ERR.ONERR.ERL | After error, verify ERL returns correct line number |
| ERR.ONERR.REPORT | After error, REPORT prints correct message |
| ERR.ONERR.OFF | ON ERROR OFF (or ON ERROR END): verify errors are no longer trapped |
| ERR.ONERR.CHAIN | Verify ON ERROR persists through various operations |
| ERR.ONERR.NESTED | Multiple ON ERROR handlers: verify latest one takes effect |

### 8.2 Specific Error Generation

Each of these tests should deliberately trigger a specific error and verify both the error number (ERR) and that the error is trappable via ON ERROR.

| Test ID | Trigger | ERR | Error Message |
|---------|---------|-----|---------------|
| ERR.GEN.DIV_ZERO | X=1/0 | 18 | "Division by zero" |
| ERR.GEN.STR_LONG | A$=STRING$(255,"X")+"Y" | 19 | "String too long" |
| ERR.GEN.TOO_BIG | X=1E38*10 | 20 | "Too big" |
| ERR.GEN.NEG_ROOT | X=SQR(-1) | 21 | "-ve root" |
| ERR.GEN.LOG_RANGE | X=LN(0) | 22 | "Log range" |
| ERR.GEN.ACC_LOST | X=SIN(1E18) | 23 | "Accuracy lost" (verify threshold) |
| ERR.GEN.EXP_RANGE | X=EXP(89) | 24 | "Exp range" |
| ERR.GEN.NO_SUCH_VAR | PRINT undefined_var | 26 | "No such variable" |
| ERR.GEN.TYPE_MISMATCH | A$=42 | 6 | "Type mismatch" |
| ERR.GEN.SUBSCRIPT | DIM A(5): X=A(10) | 15 | "Subscript" |
| ERR.GEN.NO_SUCH_LINE | GOTO 99999 | 41 | "No such line" |
| ERR.GEN.OUT_OF_DATA | READ X (no DATA) | 42 | "Out of DATA" |
| ERR.GEN.MISSING_QUOTE | Programmatically construct bad string? | 9 | Missing " |
| ERR.GEN.BAD_DIM | DIM A(-1) | 10 | "Bad DIM" |
| ERR.GEN.DIM_SPACE | DIM A(1000000) | 11 | "DIM space" |
| ERR.GEN.NO_FOR | NEXT without FOR | 32 | "No FOR" |
| ERR.GEN.NO_REPEAT | UNTIL without REPEAT | 43 | "No REPEAT" |
| ERR.GEN.NO_GOSUB | RETURN without GOSUB | 38 | "No GOSUB" |
| ERR.GEN.NO_FN | ENDPROC outside PROC | 7 | "No FN" |
| ERR.GEN.MISTAKE | Syntax error: PRNT "X" | 4 | "Mistake" |

---

## 9. INPUT and READ

### 9.1 INPUT (Simulated Where Possible)

Since INPUT is interactive, testing it directly in a self-checking suite is difficult. However:

| Test ID | Description |
|---------|-------------|
| INPUT.REDIRECT | If running on an emulator that supports input redirection, test INPUT A, INPUT A$, INPUT LINE A$ |
| INPUT.PROMPT_SEMI | INPUT "Name";A$ — verify semicolon suppresses "?" |
| INPUT.PROMPT_COMMA | INPUT "Name",A$ — verify comma produces "?" |
| INPUT.MULTIPLE | INPUT A,B,C — multiple values |
| INPUT.LINE | INPUT LINE A$ — verify commas and quotes preserved |

### 9.2 PRINT# and INPUT# (File I/O)

| Test ID | Description |
|---------|-------------|
| FILE.WRITE_READ.INT | OPENOUT, PRINT# integer, CLOSE#, OPENIN, INPUT#, verify |
| FILE.WRITE_READ.REAL | PRINT# real, INPUT#, verify |
| FILE.WRITE_READ.STRING | PRINT# string, INPUT#, verify |
| FILE.WRITE_READ.MULTI | PRINT# multiple values, INPUT# all, verify |
| FILE.BPUT_BGET | BPUT# byte, BGET# byte, verify |
| FILE.PTR | Set PTR# to 0 after writing, read back |
| FILE.EXT | Verify EXT# returns correct file length |
| FILE.CLOSE_ZERO | CLOSE#0 closes all files |

---

## 10. Graphics and Sound (Testable Subset)

While graphics are inherently visual, some aspects can be self-checked:

### 10.1 MODE

| Test ID | Description |
|---------|-------------|
| GFX.MODE.SET | MODE 7: verify no error |
| GFX.MODE.ALL | Cycle through MODE 0-7: verify no error on each |

### 10.2 COLOUR/GCOL

| Test ID | Description |
|---------|-------------|
| GFX.COLOUR.SET | COLOUR 1: verify no error |
| GFX.COLOUR.RANGE | COLOUR 0 through COLOUR 15: all valid |

### 10.3 POINT (Pixel Query)

| Test ID | Description |
|---------|-------------|
| GFX.POINT.READ | In a graphics mode, PLOT a point, then POINT(x,y) to read it back |
| GFX.POINT.BACKGROUND | Read undrawn pixel: verify returns background colour |
| GFX.POINT.OFFSCREEN | POINT(-1,-1): verify returns -1 |

### 10.4 PLOT

| Test ID | Description |
|---------|-------------|
| GFX.PLOT.MOVE | PLOT 4,100,100: verify no error (absolute move) |
| GFX.PLOT.DRAW | PLOT 5,200,200: verify no error (absolute draw) |
| GFX.PLOT.POINT | PLOT 69,100,100: verify POINT(100,100) = foreground colour |

### 10.5 VDU

| Test ID | Description |
|---------|-------------|
| GFX.VDU.BEEP | VDU 7: verify no error (bell) |
| GFX.VDU.CLS | VDU 12: verify clears screen (same as CLS) |
| GFX.VDU.SEQUENCE | VDU 31,10,10: move cursor to (10,10), verify POS=10, VPOS=10 |

### 10.6 SOUND and ENVELOPE

| Test ID | Description |
|---------|-------------|
| SND.SOUND.BASIC | SOUND 1,-15,100,10: verify no error |
| SND.ENVELOPE.BASIC | ENVELOPE 1,1,0,0,0,0,0,0,126,0,0,-126,126,126: verify no error |

---

## 11. Assembler (Inline 6502)

### 11.1 Basic Assembly

| Test ID | Description |
|---------|-------------|
| ASM.BASIC | Assemble `LDA #42: RTS` at P%, CALL it, verify A%=42 |
| ASM.TWO_PASS | FOR I%=0 TO 2 STEP 2: P%=code: [OPT I%: ...]: NEXT: verify two-pass assembly |
| ASM.FORWARD_REF | Verify forward reference resolved in pass 2 |
| ASM.ALL_ADDR_MODES | Test: immediate, zero-page, absolute, indexed, indirect indexed |
| ASM.BRANCH | BEQ, BNE with computed labels |
| ASM.USR | X=USR(addr): verify returns A + 256*X + 65536*Y |

### 11.2 Specific Instructions (Spot Check)

| Test ID | Description |
|---------|-------------|
| ASM.LDA_IMM | LDA #&FF: verify A%=255 after USR |
| ASM.ADC | CLC: LDA #10: ADC #20: verify result 30 |
| ASM.SBC | SEC: LDA #30: SBC #10: verify result 20 |
| ASM.AND | LDA #&F0: AND #&0F: verify 0 |
| ASM.ORA | LDA #&F0: ORA #&0F: verify &FF |
| ASM.EOR | LDA #&FF: EOR #&F0: verify &0F |
| ASM.SHIFTS | ASL, LSR, ROL, ROR: verify bit manipulation |
| ASM.LOOP | LDX #10: DEX: BNE loop: verify loop executes 10 times |

---

## 12. Operating System Interface

### 12.1 OSCLI

| Test ID | Description |
|---------|-------------|
| OS.OSCLI.BASIC | OSCLI "FX 0": verify no error |
| OS.STAR.BASIC | *FX 0: verify no error |

### 12.2 CALL

| Test ID | Description |
|---------|-------------|
| OS.CALL.BASIC | Assemble a simple routine, CALL it |
| OS.CALL.PARAMS | CALL addr, A, B$: verify parameter block |

### 12.3 USR

| Test ID | Description |
|---------|-------------|
| OS.USR.BASIC | Assemble LDA #1: LDX #2: LDY #3: RTS, verify USR returns &030201 |
| OS.USR.OSBYTE | USR(&FFF4) style OS calls (where testable) |

---

## 13. Program Management Commands (Smoke Tests)

These are harder to self-check but should at least verify no crash:

| Test ID | Description |
|---------|-------------|
| CMD.NEW | NEW: verify program erased |
| CMD.OLD | NEW: OLD: verify program recovered |
| CMD.LIST | LIST: verify no error |
| CMD.RENUMBER | RENUMBER: verify line numbers changed, GOTOs updated |
| CMD.AUTO | AUTO: verify auto line numbering starts (escape to exit) |
| CMD.DELETE | DELETE 10,20: verify lines removed |
| CMD.CLEAR | CLEAR: verify dynamic variables cleared, static preserved |
| CMD.RUN | RUN: verify program executes from start |
| CMD.CHAIN | CHAIN "testfile": verify load-and-run (needs test fixture file) |
| CMD.SAVE_LOAD | SAVE/LOAD round-trip: verify program survives |

---

## 14. Edge Cases, Pathological Inputs, and Regression Tests

### 14.1 Parser Edge Cases

| Test ID | Description |
|---------|-------------|
| EDGE.MULTI_STMT | A=1:B=2:C=3:D=4: verify all assignments |
| EDGE.EMPTY_LINE | Line with only a line number: 100 — verify no error |
| EDGE.MAX_LINE | Line 32767: verify accepted |
| EDGE.LONG_LINE | 239-byte line (max): verify accepted |
| EDGE.KEYWORDS_IN_VARS | Variables whose names contain keywords: FORGET, FORNEXT, LETTER |
| EDGE.COLON_IN_STRING | A$="A:B": verify colon inside string is not treated as separator |
| EDGE.REM | 10 REM This line is a comment: verify skipped |
| EDGE.REM_KEYWORDS | 10 REM GOTO 100: verify GOTO is not executed |

### 14.2 Numeric Edge Cases

| Test ID | Description |
|---------|-------------|
| EDGE.INT_REAL_BOUNDARY | Values near 2^31 stored as real vs integer |
| EDGE.VERY_SMALL_REAL | 1E-38, 1E-39: verify representation |
| EDGE.NEG_ZERO | -0: verify behaviour in comparisons |
| EDGE.NAN_EQUIV | Division edge cases that might produce unusual values |
| EDGE.PRINT_FORMAT | Verify numbers print with correct number of sig figs in all ranges |
| EDGE.INT_DIVISION | 1/3 vs 1 DIV 3 vs 1.0/3.0: verify different results |

### 14.3 String Edge Cases

| Test ID | Description |
|---------|-------------|
| EDGE.STR_ALL_CHARS | Build and verify string containing all 256 byte values |
| EDGE.STR_NUL | String containing CHR$(0): verify LEN, MID$ etc. handle it |
| EDGE.STR_CR | String containing CHR$(13): verify behaviour |
| EDGE.STR_QUOTE | String containing CHR$(34): verify PRINT, MID$ etc. |
| EDGE.STR_MAX_CAT | Concatenate to exactly 255 characters: verify |

### 14.4 Stack/Memory Pressure

| Test ID | Description |
|---------|-------------|
| EDGE.DEEP_GOSUB | Nested GOSUB to max depth: verify error message |
| EDGE.DEEP_FOR | Many nested FOR loops: verify limit |
| EDGE.DEEP_REPEAT | Many nested REPEAT loops |
| EDGE.DEEP_FN | Deeply recursive FN: verify stack overflow is trapped |
| EDGE.MANY_VARS | Create hundreds of variables: verify memory management |
| EDGE.LARGE_ARRAY | DIM A(10000): verify or get "DIM space" |

### 14.5 ESCAPE Handling

| Test ID | Description |
|---------|-------------|
| EDGE.ESCAPE.ERR | After ESCAPE, verify ERR=17 |
| EDGE.ESCAPE.TRAP | ON ERROR GOTO handler: verify ESCAPE is trappable |

---

## 15. Cross-Cutting Concerns

### 15.1 TRUE and FALSE

| Test ID | Description |
|---------|-------------|
| BOOL.TRUE | Verify TRUE = -1 |
| BOOL.FALSE | Verify FALSE = 0 |
| BOOL.IF_TRUE | IF TRUE THEN A=1: verify |
| BOOL.IF_FALSE | IF FALSE THEN A=1: verify skipped |
| BOOL.NONZERO | IF 42 THEN A=1: verify (any nonzero is true) |

### 15.2 Multiple Statement Lines

| Test ID | Description |
|---------|-------------|
| MULTI.BASIC | A=1:B=2:C=3: verify all |
| MULTI.IF_SCOPE | IF TRUE THEN A=1:B=2 — verify both execute |
| MULTI.IF_ELSE | IF FALSE THEN A=1:B=2 ELSE C=3: verify only C set |

### 15.3 LET (Optional Keyword)

| Test ID | Description |
|---------|-------------|
| LET.EXPLICIT | LET A=42: verify A=42 |
| LET.IMPLICIT | A=42: verify A=42 |
| LET.EQUIV | Verify LET A=X and A=X produce identical results |

---

## 16. Test Execution Plan

### 16.1 File Organisation

Given BBC Micro memory constraints (~28K usable in MODE 7), the test suite should be split into multiple files:

| File | Sections Covered | Estimated Size |
|------|-----------------|----------------|
| T.ARITH1 | §2.1–2.2 (Integer and real arithmetic) | ~4K |
| T.ARITH2 | §2.3–2.5 (Precedence, comparison, bitwise) | ~3K |
| T.MATH1 | §3.1 (Trigonometry) | ~4K |
| T.MATH2 | §3.2–3.4 (Log, exp, other functions, RND) | ~3K |
| T.STRING1 | §4.1–4.3 (String ops through MID$) | ~4K |
| T.STRING2 | §4.3.5–4.4 (CHR$/ASC through EVAL) | ~3K |
| T.VARS | §5 (Variables, arrays, pseudo-vars, indirection) | ~4K |
| T.FLOW1 | §6.1–6.4 (IF, FOR, REPEAT, WHILE) | ~4K |
| T.FLOW2 | §6.5–6.8 (GOTO, ON, PROC/FN, DATA) | ~4K |
| T.PRINT | §7 (PRINT formatting) | ~3K |
| T.ERROR | §8 (Error handling) | ~3K |
| T.FILE | §9 (File I/O) | ~2K |
| T.GFX | §10 (Graphics and sound smoke tests) | ~2K |
| T.ASM | §11 (Inline assembler) | ~3K |
| T.OSIF | §12 (OS interface) | ~2K |
| T.EDGE | §14 (Edge cases) | ~4K |
| T.CROSS | §13, §15 (Commands, cross-cutting) | ~2K |
| T.RUNNER | Master file: CHAINs each test file in sequence | ~0.5K |

### 16.2 Harness Code (Shared via Static Variables)

The harness uses A%–Z% for state that survives CHAIN:

- `P%` — total passes (repurposing the assembler pointer when not assembling)
- `F%` — total failures  
- `T%` — test file index (for sequencing)

Actually, P% is special (assembler). Use other statics:
- `N%` — total passes
- `F%` — total failures
- `T%` — test index

Each test file begins with:
```
10 REM T.ARITH1 - Integer and real arithmetic
20 DEF PROCpass(T$):N%=N%+1:PRINT "PASS: ";T$:ENDPROC
30 DEF PROCfail(T$,G$,E$):F%=F%+1:PRINT "FAIL: ";T$;" got ";G$;" expected ";E$:ENDPROC
40 DEF PROCchk(T$,G,E):IF ABS(G-E)<1E-9 THEN PROCpass(T$) ELSE PROCfail(T$,STR$(G),STR$(E))
50 DEF PROCchk_str(T$,G$,E$):IF G$=E$ THEN PROCpass(T$) ELSE PROCfail(T$,G$,E$)
60 DEF PROCchk_int(T$,G%,E%):IF G%=E% THEN PROCpass(T$) ELSE PROCfail(T$,STR$(G%),STR$(E%))
70 DEF PROCchk_exact(T$,G,E):IF G=E THEN PROCpass(T$) ELSE PROCfail(T$,STR$(G),STR$(E))
80 DEF PROCchk_err(T$,E%):IF ERR=E% THEN PROCpass(T$) ELSE PROCfail(T$,STR$(ERR),STR$(E%))
```

And ends with:
```
9990 PRINT "---"
9991 PRINT "File passes: ";N_local;" File fails: ";F_local
9992 PRINT "Cumulative: ";N%;" passed, ";F%;" failed"
9993 T%=T%+1: CHAIN "T."+MID$("ARITH1ARITH2MATH1 ...",T%*6-5,6)
```

(The exact CHAIN mechanism may use an array of filenames in a DATA statement read by the runner.)

### 16.3 Estimated Test Count

| Section | Approx. Tests |
|---------|---------------|
| §2 Arithmetic | 80 |
| §3 Math functions | 90 |
| §4 Strings | 80 |
| §5 Variables/arrays | 40 |
| §6 Control flow | 80 |
| §7 PRINT | 30 |
| §8 Errors | 30 |
| §9 File I/O | 15 |
| §10 Graphics | 15 |
| §11 Assembler | 20 |
| §12 OS interface | 10 |
| §14 Edge cases | 40 |
| §15 Cross-cutting | 15 |
| **Total** | **~545** |

### 16.4 Platform-Specific Considerations

- **MODE 7** should be used for testing to maximise available memory (~25K for program).
- **Cassette filing system**: SAVE/LOAD tests need CFS; disk tests need DFS.
- **ADVAL**: Only testable with actual analogue hardware connected.
- **INKEY**: Only testable interactively or with emulator keyboard injection.
- **SOUND/ENVELOPE**: Verify no error; cannot automatically verify audio output.
- **ESCAPE**: Can be simulated in some emulators via scripted keypress.

### 16.5 What This Suite Does NOT Test

- Screen layout and character rendering (visual inspection required)
- Teletext graphics (MODE 7 control codes)
- Cassette/disk filing system timing and reliability
- RS-232 serial communication
- Analogue input (ADVAL with physical hardware)
- User-defined character graphics
- Printer output
- Second processor operation
- Networking (Econet)
- Exact timing of SOUND and ENVELOPE playback

---

## Appendix A: BBC BASIC II Keyword Coverage Matrix

Every keyword in BBC BASIC II should be exercised by at least one test. This matrix tracks coverage.

| Keyword | Section | Test IDs | Notes |
|---------|---------|----------|-------|
| ABS | §3.3.1 | MATH.ABS.* | |
| ACS | §3.1.4 | TRIG.ACS.* | |
| ADVAL | — | — | Requires hardware |
| AND | §2.5 | BIT.AND.* | Bitwise and logical |
| ASC | §4.3.5 | STR.ASC.* | |
| ASN | §3.1.4 | TRIG.ASN.* | |
| ATN | §3.1.4 | TRIG.ATN.* | |
| AUTO | §13 | CMD.AUTO | Smoke test |
| BGET# | §9.2 | FILE.BPUT_BGET | |
| BPUT# | §9.2 | FILE.BPUT_BGET | |
| CALL | §12.2 | OS.CALL.* | |
| CHAIN | §13 | CMD.CHAIN | |
| CHR$ | §4.3.5 | STR.CHR.* | |
| CLEAR | §13 | CMD.CLEAR, INT.STATIC.SURVIVE_CLEAR | |
| CLOSE# | §9.2 | FILE.CLOSE_ZERO | |
| CLG | §10 | — | Graphics clear |
| CLS | §10 | — | Text clear |
| COLOUR | §10.2 | GFX.COLOUR.* | |
| COS | §3.1.2 | TRIG.COS.* | |
| COUNT | §7.6 | PRINT.COUNT.* | |
| DATA | §6.8 | DATA.* | |
| DEF | §6.7 | PROC.*, FN.* | |
| DEG | §3.3.5 | MATH.DEG.* | |
| DELETE | §13 | CMD.DELETE | |
| DIM | §5.2 | ARR.DIM.* | |
| DIV | §2.1.2 | INT.DIV.* | |
| DRAW | §10.4 | — | |
| ELSE | §6.1 | FLOW.IF.* | |
| END | §6 | — | |
| ENDPROC | §6.7.1 | PROC.* | |
| EOR | §2.5 | BIT.EOR.* | |
| ERL | §8.1 | ERR.ONERR.ERL | |
| ERR | §8.1 | ERR.ONERR.ERR | |
| EVAL | §4.4 | STR.EVAL.* | |
| EXP | §3.2.3 | MATH.EXP.* | |
| EXT# | §9.2 | FILE.EXT | |
| FALSE | §15.1 | BOOL.FALSE | |
| FN | §6.7.2 | FN.* | |
| FOR | §6.2 | FLOW.FOR.* | |
| GCOL | §10.2 | — | |
| GET | — | — | Interactive |
| GOSUB | §6.5 | FLOW.GOSUB.* | |
| GOTO | §6.5 | FLOW.GOTO.* | |
| HIMEM | §5.3 | PVAR.HIMEM | |
| IF | §6.1 | FLOW.IF.* | |
| INKEY | — | — | Interactive |
| INPUT | §9.1 | INPUT.* | Limited testing |
| INPUT# | §9.2 | FILE.WRITE_READ.* | |
| INPUT LINE | §9.1 | INPUT.LINE | |
| INSTR | §4.3.7 | STR.INSTR.* | |
| INT | §3.3.4 | MATH.INT.* | |
| LEFT$ | §4.3.2 | STR.LEFT.* | |
| LEN | §4.3.1 | STR.LEN.* | |
| LET | §15.3 | LET.* | |
| LIST | §13 | CMD.LIST | |
| LN | §3.2.1 | MATH.LN.* | |
| LOAD | §13 | CMD.SAVE_LOAD | |
| LOCAL | §6.7 | PROC.LOCAL, FN.LOCAL | |
| LOG | §3.2.2 | MATH.LOG.* | |
| LOMEM | §5.3 | PVAR.LOMEM | |
| LVAR | §13 | — | Lists variables |
| MID$ | §4.3.4 | STR.MID.* | |
| MOD | §2.1.2 | INT.MOD.* | |
| MODE | §10.1 | GFX.MODE.* | |
| MOVE | §10.4 | — | |
| NEW | §13 | CMD.NEW | |
| NEXT | §6.2 | FLOW.FOR.* | |
| NOT | §2.5 | BIT.NOT.* | |
| OLD | §13 | CMD.OLD | |
| ON | §6.6 | FLOW.ON.* | |
| ON ERROR | §8.1 | ERR.ONERR.* | |
| OPENIN | §9.2 | FILE.* | |
| OPENOUT | §9.2 | FILE.* | |
| OPENUP | §9.2 | — | BASIC II addition |
| OR | §2.5 | BIT.OR.* | |
| ORIGIN | §10 | — | Graphics origin |
| OSCLI | §12.1 | OS.OSCLI.* | |
| PAGE | §5.3 | PVAR.PAGE | |
| PI | §3.3.6 | MATH.PI.* | |
| PLOT | §10.4 | GFX.PLOT.* | |
| POINT | §10.3 | GFX.POINT.* | |
| POS | §7.6 | PRINT.POS.* | |
| PRINT | §7 | PRINT.* | |
| PRINT# | §9.2 | FILE.WRITE_READ.* | |
| PROC | §6.7.1 | PROC.* | |
| PTR# | §9.2 | FILE.PTR | |
| RAD | §3.3.5 | MATH.RAD.* | |
| READ | §6.8 | DATA.READ.* | |
| REM | §14.1 | EDGE.REM.* | |
| RENUMBER | §13 | CMD.RENUMBER | |
| REPEAT | §6.3 | FLOW.RPT.* | |
| REPORT | §8.1 | ERR.ONERR.REPORT | |
| RESTORE | §6.8 | DATA.RESTORE.* | |
| RETURN | §6.5 | FLOW.GOSUB.* | |
| RIGHT$ | §4.3.3 | STR.RIGHT.* | |
| RND | §3.4 | RND.* | |
| RUN | §13 | CMD.RUN | |
| SAVE | §13 | CMD.SAVE_LOAD | |
| SGN | §3.3.2 | MATH.SGN.* | |
| SIN | §3.1.1 | TRIG.SIN.* | |
| SOUND | §10.6 | SND.SOUND.* | |
| SPC | §7.3 | PRINT.SPC.* | |
| SQR | §3.3.3 | MATH.SQR.* | |
| STEP | §6.2 | FLOW.FOR.STEP | |
| STOP | §8 | — | |
| STR$ | §4.3.6 | STR.STR.* | |
| STRING$ | §4.3.8 | STR.STRING.* | |
| TAB | §7.3 | PRINT.TAB.* | |
| TAN | §3.1.3 | TRIG.TAN.* | |
| THEN | §6.1 | FLOW.IF.* | |
| TIME | §5.3 | PVAR.TIME.* | |
| TO | §6.2 | FLOW.FOR.* | |
| TOP | §5.3 | PVAR.TOP | |
| TRACE | §13 | — | Debugging |
| TRUE | §15.1 | BOOL.TRUE | |
| UNTIL | §6.3 | FLOW.RPT.* | |
| USR | §12.3 | OS.USR.* | |
| VAL | §4.3.6 | STR.VAL.* | |
| VDU | §10.5 | GFX.VDU.* | |
| VPOS | §7.6 | PRINT.VPOS.* | |
| WIDTH | §7.5 | PRINT.WIDTH.* | |

---

## Appendix B: Floating-Point Format Reference

BBC BASIC II uses a 5-byte (40-bit) floating-point format:

| Byte | Content |
|------|---------|
| 0 | Exponent (excess-128, 0 means the number is zero) |
| 1 | Mantissa MSB (bit 7 = sign; bit 7 would be 1 for normalised, but is repurposed as sign) |
| 2 | Mantissa byte 2 |
| 3 | Mantissa byte 3 |
| 4 | Mantissa LSB |

- Sign bit: bit 7 of byte 1 (0 = positive, 1 = negative)
- The mantissa has an implicit leading 1 (hidden bit), so effective mantissa precision is 32 bits
- Range: approximately ±1.7×10³⁸
- Precision: approximately 9.6 decimal digits

Tests should verify this representation by writing known values via indirection and reading them back, and vice versa.

---

## Appendix C: Error Code Quick Reference (6502 BASIC II)

| ERR | Message |
|-----|---------|
| 0 | No room |
| 1 | Out of range |
| 2 | Byte |
| 3 | Index |
| 4 | Mistake |
| 5 | Missing , |
| 6 | Type mismatch |
| 7 | No FN |
| 8 | $ range |
| 9 | Missing " |
| 10 | Bad DIM |
| 11 | DIM space |
| 12 | Not LOCAL |
| 13 | No PROC |
| 14 | Array |
| 15 | Subscript |
| 16 | Syntax error |
| 17 | Escape |
| 18 | Division by zero |
| 19 | String too long |
| 20 | Too big |
| 21 | -ve root |
| 22 | Log range |
| 23 | Accuracy lost |
| 24 | Exp range |
| 25 | (not used in BASIC II) |
| 26 | No such variable |
| 27 | Missing ) |
| 28 | Bad HEX |
| 29 | No such FN/PROC |
| 30 | Bad call |
| 31 | Arguments |
| 32 | No FOR |
| 33 | Can't match FOR |
| 34 | FOR variable |
| 35 | Too many FORs |
| 36 | Missing TO |
| 37 | Too many GOSUBs |
| 38 | No GOSUB |
| 39 | ON syntax |
| 40 | ON range |
| 41 | No such line |
| 42 | Out of DATA |
| 43 | No REPEAT |
| 44 | Too many REPEATs |
| 45 | Missing # |
