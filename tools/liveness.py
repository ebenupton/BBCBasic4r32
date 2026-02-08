#!/usr/bin/env python3
"""
Register liveness analysis for 6502 assembly.

Given an assembly file and a target label, this script:
1. Finds all JSR/JMP/BRA/Bxx references to the target
2. For JSR callers, finds the return point (instruction after JSR)
3. Traces forward from that return point, tracking which registers
   (A, X, Y) and flags (N, Z, C, V) are READ before being WRITTEN
4. Reports any caller where Y is live (read before written) after the JSR

Also traces WITHIN the target routine to check if Y is read between
the space-skip exit and the point where Y is reloaded.
"""

import re
import sys

# Instructions that READ Y
Y_READERS = {
    'STY', 'TYA', 'CPY', 'PHY',
    # Indexed addressing modes that use Y
    'LDA', 'STA', 'CMP', 'ADC', 'SBC', 'AND', 'ORA', 'EOR',
}

# Instructions that unconditionally WRITE Y (kill Y's old value)
Y_WRITERS = {'LDY', 'PLY', 'TAY', 'INY', 'DEY', 'TXY'}

# Instructions that MIGHT use Y depending on addressing mode
# (zp),Y and abs,Y modes read Y
Y_ADDR_PATTERNS = re.compile(r'\(.*\),Y|,Y\b', re.IGNORECASE)

# Branch instructions
BRANCHES = {'BEQ', 'BNE', 'BCC', 'BCS', 'BMI', 'BPL', 'BVS', 'BVC', 'BRA'}
UNCONDITIONAL = {'JMP', 'BRA', 'RTS', 'RTI', 'BRK'}

def parse_instruction(line):
    """Parse an assembly line into (label, mnemonic, operand) or None."""
    # Strip comments
    line = line.split(';')[0].strip()
    if not line:
        return None

    label = None
    if line.startswith('.'):
        # Label definition
        parts = line.split(None, 1)
        label = parts[0][1:]  # remove leading dot
        if len(parts) < 2:
            return ('label', label, None, None)
        line = parts[1].strip()

    # Skip directives
    if not line or line.startswith('EQUB') or line.startswith('EQUS') or line.startswith('EQUW'):
        return ('directive', label, None, None) if label else None
    if line.startswith('SAVE') or line.startswith('CPU') or line.startswith('ORG'):
        return ('directive', label, None, None) if label else None

    parts = line.split(None, 1)
    mnemonic = parts[0].upper()
    operand = parts[1].strip() if len(parts) > 1 else ''

    return ('instr', label, mnemonic, operand)

def reads_y(mnemonic, operand):
    """Check if this instruction reads the Y register."""
    if mnemonic in ('STY', 'TYA', 'CPY', 'PHY'):
        return True
    # Check for Y-indexed addressing modes
    if Y_ADDR_PATTERNS.search(operand):
        return True
    return False

def writes_y(mnemonic, operand):
    """Check if this instruction unconditionally writes Y."""
    if mnemonic in ('LDY', 'PLY', 'TAY'):
        return True
    # INY and DEY read AND write Y
    if mnemonic in ('INY', 'DEY'):
        return True  # They write Y, but also read it first
    return False

def kills_y(mnemonic, operand):
    """Check if this instruction overwrites Y without reading old value."""
    if mnemonic in ('LDY', 'PLY', 'TAY'):
        return True
    return False

def is_branch(mnemonic):
    return mnemonic in BRANCHES

def is_unconditional_transfer(mnemonic):
    return mnemonic in UNCONDITIONAL or mnemonic == 'JMP'

def is_jsr(mnemonic):
    return mnemonic == 'JSR'

def get_branch_target(operand):
    """Extract branch/jump target label."""
    operand = operand.strip()
    if operand.startswith('('):
        return None  # Indirect jump, can't resolve
    return operand

def load_asm(filename):
    """Load assembly file and return list of (line_num, label, mnemonic, operand)."""
    instructions = []
    with open(filename) as f:
        for i, line in enumerate(f, 1):
            parsed = parse_instruction(line)
            if parsed:
                kind, label, mnemonic, operand = parsed
                if kind == 'label':
                    instructions.append((i, label, None, None))
                elif kind == 'instr':
                    instructions.append((i, label, mnemonic, operand))
                elif kind == 'directive' and label:
                    instructions.append((i, label, None, None))
    return instructions

def build_label_index(instructions):
    """Map label names to instruction indices."""
    idx = {}
    for i, (line_num, label, mnemonic, operand) in enumerate(instructions):
        if label:
            idx[label] = i
    return idx

def trace_y_liveness(instructions, label_idx, start_idx, max_depth=50, context_label=""):
    """
    Trace forward from start_idx, checking if Y is read before being killed.
    Returns (is_live, trace_description).
    Uses BFS to handle branches.
    """
    visited = set()
    queue = [(start_idx, [])]
    results = []

    while queue:
        idx, path = queue.pop(0)

        if idx in visited or idx >= len(instructions):
            continue
        if len(path) > max_depth:
            results.append(f"  DEPTH LIMIT reached at path: {' -> '.join(path)}")
            continue
        visited.add(idx)

        line_num, label, mnemonic, operand = instructions[idx]

        if mnemonic is None:
            # Label-only line, continue to next
            queue.append((idx + 1, path))
            continue

        step = f"L{line_num}:{mnemonic} {operand}"
        new_path = path + [step]

        # Check if this instruction reads Y
        if reads_y(mnemonic, operand):
            if not kills_y(mnemonic, operand):
                # Y is read before being killed — it's LIVE
                results.append(f"  Y IS LIVE: {mnemonic} {operand} at line {line_num}")
                results.append(f"    Path: {' -> '.join(new_path)}")
                continue
            else:
                # INY/DEY: reads then writes — Y is live
                results.append(f"  Y IS LIVE (read+write): {mnemonic} {operand} at line {line_num}")
                results.append(f"    Path: {' -> '.join(new_path)}")
                continue

        # Check if this instruction kills Y (writes without reading)
        if kills_y(mnemonic, operand):
            # Y is dead — this path is safe
            results.append(f"  Y killed by {mnemonic} {operand} at line {line_num} (safe)")
            continue

        # Handle control flow
        if mnemonic == 'RTS' or mnemonic == 'RTI':
            results.append(f"  RTS at line {line_num} without Y use (safe)")
            continue

        if mnemonic == 'BRK':
            results.append(f"  BRK (error) at line {line_num} (safe - no return)")
            continue

        if mnemonic == 'JSR':
            # JSR: assume subroutine may clobber Y (conservative)
            # Actually, we should check if the subroutine preserves Y
            # For now, assume JSR clobbers A/X/Y (conservative = safe assumption)
            # But actually, if JSR preserves Y, then Y is still live after
            # The conservative assumption for liveness is: JSR does NOT kill Y
            # (because the subroutine might preserve it)
            # BUT: for our purposes, we want to know if Y from the space-skip
            # reaches the caller. If a JSR happens first, the subroutine will
            # set up its own Y. So we can't assume Y survives.
            #
            # Actually the truly conservative approach: don't assume JSR kills Y.
            # Continue tracing after the JSR.
            results.append(f"  JSR {operand} at line {line_num} (Y may or may not survive)")
            queue.append((idx + 1, new_path))
            continue

        if mnemonic == 'JMP':
            target = get_branch_target(operand)
            if target and target in label_idx:
                queue.append((label_idx[target], new_path))
            else:
                results.append(f"  JMP to unresolved target {operand} at line {line_num}")
            continue

        if is_branch(mnemonic):
            target = get_branch_target(operand)
            if mnemonic == 'BRA':
                # Unconditional branch
                if target and target in label_idx:
                    queue.append((label_idx[target], new_path))
                continue
            else:
                # Conditional: trace both paths
                queue.append((idx + 1, new_path))  # fall-through
                if target and target in label_idx:
                    queue.append((label_idx[target], new_path))  # taken
                continue

        # Regular instruction, continue to next
        queue.append((idx + 1, new_path))

    return results

def find_callers(instructions, target_label):
    """Find all JSR/JMP/BRA/Bxx instructions referencing the target."""
    callers = []
    for i, (line_num, label, mnemonic, operand) in enumerate(instructions):
        if mnemonic and operand and target_label in operand:
            if mnemonic == 'JSR':
                callers.append(('JSR', i, line_num))
            elif mnemonic in BRANCHES or mnemonic == 'JMP':
                callers.append((mnemonic, i, line_num))
    return callers

def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <asm_file> <label> [<label2> ...]")
        sys.exit(1)

    filename = sys.argv[1]
    targets = sys.argv[2:]

    print(f"Loading {filename}...")
    instructions = load_asm(filename)
    label_idx = build_label_index(instructions)
    print(f"Loaded {len(instructions)} instructions, {len(label_idx)} labels")

    for target in targets:
        print(f"\n{'='*60}")
        print(f"Analyzing Y liveness for callers of {target}")
        print(f"{'='*60}")

        if target not in label_idx:
            print(f"  ERROR: Label {target} not found!")
            continue

        callers = find_callers(instructions, target)
        print(f"Found {len(callers)} references to {target}")

        for call_type, idx, line_num in callers:
            # Skip self-references (BEQ within the loop)
            instr = instructions[idx]
            if call_type == 'BEQ' and instr[2] == 'BEQ':
                # Internal loop branch, skip
                continue

            print(f"\n--- {call_type} {target} at line {line_num} ---")

            if call_type == 'JSR':
                # Trace from the instruction AFTER the JSR
                # But we need to know what Y is when the JSR returns
                # The question is: does the caller use Y after JSR returns?
                print(f"Tracing Y liveness AFTER JSR return (from line {line_num + 1}):")
                results = trace_y_liveness(instructions, label_idx, idx + 1,
                                          context_label=f"after JSR {target}")
                for r in results:
                    print(r)
            else:
                print(f"  Branch reference ({call_type}), not a JSR caller")

    # Also trace Y liveness WITHIN the routine
    for target in targets:
        if target not in label_idx:
            continue
        print(f"\n{'='*60}")
        print(f"Tracing Y liveness WITHIN {target} (from the label itself)")
        print(f"{'='*60}")

        start = label_idx[target]
        results = trace_y_liveness(instructions, label_idx, start)
        for r in results:
            print(r)

if __name__ == '__main__':
    main()
