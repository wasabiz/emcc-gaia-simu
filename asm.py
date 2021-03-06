#!/usr/bin/env python2.7

import sys
import os.path
import re
import struct
import argparse


srcs = {}
filename = ''
pos = 0

def fatal(msg):
    prog = os.path.basename(sys.argv[0])
    if sys.stderr.isatty():
        print >> sys.stderr, '\x1b[1m{}: \x1b[31mfatal error:\x1b[39m'.format(prog), msg
        sys.stderr.write('\x1b[0m')
    else:
        print >> sys.stderr, '{}: fatal error:'.format(prog), msg
    sys.exit(1)

def error(msg):
    if sys.stderr.isatty():
        print >> sys.stderr, '\x1b[1m{}:{}: \x1b[31merror:\x1b[39m'.format(filename, pos), msg
        sys.stderr.write('\x1b[0m')
    else:
        print >> sys.stderr, '{}:{}: error:'.format(filename, pos), msg
    print >> sys.stderr, '  ' + srcs[filename][pos]
    sys.exit(1)

def warning(msg, show_line=False):
    if sys.stderr.isatty():
        print >> sys.stderr, '\x1b[1m{}:{}: \x1b[35mwarning:\x1b[39m'.format(filename, pos), msg
        sys.stderr.write('\x1b[0m')
    else:
        print >> sys.stderr, '{}:{}: warning:'.format(filename, pos), msg
    if show_line:
        print >> sys.stderr, '  ' + srcs[filename][pos]


# ----------------------------------------------------------------------
#       utility functions (mainly parsing)
# ----------------------------------------------------------------------

regs = {'rsp': 30, 'rbp': 31, 'rk0': 26, 'rk1': 27}
for i in range(32):
    regs['r' + str(i)] = i

def regnum(reg):
    if reg not in regs:
        error('expected register: ' + reg)
    return regs[reg]

def parse_int(s):
    try:
        return True, int(s, 0)
    except ValueError:
        return False, 0

def parse_float(s):
    try:
        return True, float(s)
    except ValueError:
        return False, 0.0

def check_int_range(i, b):
    x = 1 << (b - 1)
    return -x <= i < x

def float_to_bit(f):
    try:
        s = struct.pack('f', f)
        return struct.unpack('I', s)[0]
    except OverflowError:
        error('floating point value is too large')

def parse_memaccess(operand):
    m = re.match(r'\[\s*(r\w+)\s*([+-])\s*(\w+)\s*\]$', operand)
    if m:
        base = m.group(1)
        success, imm = parse_int(m.group(2) + m.group(3))
        if base in regs and success:
            return True, base, imm
    m = re.match(r'\[\s*(r\w+)\s*\]$', operand)
    if m and m.group(1) in regs:
        return True, m.group(1), 0
    m = re.match(r'\[\s*([+-]?\s*\w+)\s*\]$', operand)
    if m:
        success, imm = parse_int(m.group(1))
        if success:
            return True, 'r0', imm
    return False, 'r0', 0

def check_operands_n(operands, n, m=-1):
    l = len(operands)
    if l < n:
        error('expected {} operands, but {} given'.format(n, l))
    if l > max(n, m):
        error('expected {} operands, but {} given'.format(max(n, m), l))

def split_comma(s):
    lit = esc = False
    for i, c in enumerate(s):
        if esc:
            esc = False
            continue
        if c == '\"':
            lit ^= True
        if c == '\\' and lit:
            esc = True
        if c == ',' and not lit:
            return [s[0:i]] + split_comma(s[i+1:])
        if c == '#' and not lit:
            return [s[0:i]]
    return [s]

def parse(line):
    mnemonic, rest = line.split(None, 1) if ' ' in line else (line, '')
    if '#' in mnemonic:
        return mnemonic[0 : mnemonic.find('#')], []
    if len(rest) == 0 or rest[0] == '#':
        return mnemonic, []
    operands = split_comma(rest)
    return mnemonic, map(str.strip, operands)


# ----------------------------------------------------------------------
#       mnemonic definitions
# ----------------------------------------------------------------------

alu3_table = {
    # 'fcmpne':   28,
    # 'fcmpeq':   29,
    'fcmplt':   30,
    'fcmple':   31,
}

alu4_table = {
    'add':       0,
    'sub':       1,
    'shl':       2,
    'shr':       3,
    'sar':       4,
    'and':       5,
    'or':        6,
    'xor':       7,
    'adda':      8,
    'cmpult':   22,
    'cmpule':   23,
    'cmpne':    24,
    'cmpeq':    25,
    'cmplt':    26,
    'cmple':    27,
}

fpu2_table = {
    'finv':      4,
    'fsqrt':     5,
    'ftoi':      6,
    'itof':      7,
    'floor':     8,
}

fpu3_table = {
    'fadd':      0,
    'fsub':      1,
    'fmul':      2,
    # 'fdiv':      3,
}

misc0_table = {
    'sysenter': 12,
    'sysexit':  13,
}

misc2_table = {
    'ldl':       2,
    'jl':        4,
}

misc3_table = {
    'ldh':       3,
    'ld':        6,
    'ldb':       7,
    'st':        8,
    'stb':       9,
    'bne':      14,
    'beq':      15,
}

debug_table = {
    'break':     1,
    'penv':      2,
    'ptrace':    3,
}

sign_table = {
    '':          0,
    'neg':       1,
    'abs':       2,
    'abs.neg':   3,
}

def code_i(op, rx, ra, rb, imm, tag):
    x = regnum(rx)
    a = regnum(ra)
    b = regnum(rb)
    success, i = parse_int(imm)
    if not success:
        error('expected integer literal: ' + imm)
    if not check_int_range(i, 8):
        error('immediate value too large: ' + imm)
    c0 = ((i & 7) << 5) + tag
    c1 = ((b & 7) << 5) + ((i >> 3) & 31)
    c2 = ((x & 1) << 7) + (a << 2) + (b >> 3)
    c3 = (op << 4) + (x >> 1)
    return chr(c0) + chr(c1) + chr(c2) + chr(c3)

def code_f(rx, ra, rb, sign, tag):
    x = regnum(rx)
    a = regnum(ra)
    b = regnum(rb)
    c0 = (sign << 5) + tag
    c1 = ((b & 7) << 5)
    c2 = ((x & 1) << 7) + (a << 2) + (b >> 3)
    c3 = (1 << 4) + (x >> 1)
    return chr(c0) + chr(c1) + chr(c2) + chr(c3)

def code_m(op, rx, ra, pred, disp, disp_mode):
    x = regnum(rx)
    a = regnum(ra)
    success, d = parse_int(disp)
    if not success:
        error('expected displacement: ' + disp)
    if disp_mode == 0:
        if not -0x8000 <= d <= 0xffff:
            error('immediate value too large: ' + disp)
    elif disp_mode == 1:
        if not check_int_range(d, 16):
            error('displacement too large: ' + disp)
    else:
        if d & 3 != 0:
            error('displacement must be a multiple of 4')
        if not check_int_range(d, 18):
            error('displacement too large: ' + disp)
        d >>= 2
    c0 = d & 255
    c1 = (d >> 8) & 255
    c2 = ((x & 1) << 7) + (a << 2) + pred
    c3 = (op << 4) + (x >> 1)
    return chr(c0) + chr(c1) + chr(c2) + chr(c3)

def on_alu3(operands, tag):
    check_operands_n(operands, 3)
    return code_i(0, operands[0], operands[1], operands[2], '0', tag)

def on_alu4(operands, tag):
    check_operands_n(operands, 4)
    return code_i(0, operands[0], operands[1], operands[2], operands[3], tag)

def on_fpu2(operands, sign, tag):
    check_operands_n(operands, 2)
    return code_f(operands[0], operands[1], 'r0', sign, tag)

def on_fpu3(operands, sign, tag):
    check_operands_n(operands, 3)
    return code_f(operands[0], operands[1], operands[2], sign, tag)

def on_misc0(operands, op, pred, disp_mode):
    check_operands_n(operands, 0)
    return code_m(op, 'r0', 'r0', pred, '0', disp_mode)

def on_misc2(operands, op, pred, disp_mode):
    check_operands_n(operands, 2)
    return code_m(op, operands[0], 'r0', pred, operands[1], disp_mode)

def on_misc3(operands, op, pred, disp_mode):
    check_operands_n(operands, 3)
    return code_m(op, operands[0], operands[1], pred, operands[2], disp_mode)

def on_jr(operands):
    check_operands_n(operands, 2)
    return code_m(5, operands[0], operands[1], 3, '0', 0)

def on_debug(operands, tag):
    check_operands_n(operands, 1)
    return code_m(10, 'r{}'.format(tag), 'r0', 0, operands[0], 0)

def on_dot_int(operand):
    success, imm = parse_int(operand)
    if not success:
        error('expected integer literal: ' + operand)
    if not -0x80000000 <= imm <= 0xffffffff:
        error('immediate value too large: ' + operand)
    return ''.join(chr(imm >> x & 255) for x in [0, 8, 16, 24])

def on_dot_byte(operand):
    success, imm = parse_int(operand)
    if not success:
        error('expected integer literal: ' + operand)
    if not -128 <= imm <= 255:
        error('immediate value too large: ' + operand)
    return chr(imm & 255)

def on_dot_short(operand):
    success, imm = parse_int(operand)
    if not success:
        error('expected integer literal: ' + operand)
    if not -0x8000 <= imm <= 0xffff:
        error('immediate value too large: ' + operand)
    return chr(imm & 255) + chr(imm >> 8 & 255)

def on_dot_space(operands):
    check_operands_n(operands, 2)
    success, imm = parse_int(operands[1])
    if not success:
        error('expected integer literal: ' + operands[1])
    if not -128 <= imm <= 255:
        error('immediate value too large: ' + operand)
    size = int(operands[0], 0)
    return ''.ljust(size, chr(imm & 255))

def code(mnemonic, operands):
    if mnemonic in alu3_table:
        return on_alu3(operands, alu3_table[mnemonic])
    if mnemonic in alu4_table:
        return on_alu4(operands, alu4_table[mnemonic])
    fpu_mnemonic, fpu_suffix = mnemonic, ''
    if '.' in mnemonic:
        fpu_mnemonic, fpu_suffix = mnemonic.split('.', 1)
    if fpu_mnemonic in fpu2_table:
        return on_fpu2(operands, sign_table[fpu_suffix], fpu2_table[fpu_mnemonic])
    if fpu_mnemonic in fpu3_table:
        return on_fpu3(operands, sign_table[fpu_suffix], fpu3_table[fpu_mnemonic])
    pred = 3 if mnemonic in ['jl', 'bne+', 'beq+'] else 0
    disp_mode = 0 if mnemonic in ['ldl', 'ldh'] else \
                1 if mnemonic in ['ldb', 'stb'] else 2
    if mnemonic in ['bne-', 'bne+']:
        mnemonic = 'bne'
    if mnemonic in ['beq-', 'beq+']:
        mnemonic = 'beq'
    if mnemonic in misc0_table:
        return on_misc0(operands, misc0_table[mnemonic], pred, disp_mode)
    if mnemonic in misc2_table:
        return on_misc2(operands, misc2_table[mnemonic], pred, disp_mode)
    if mnemonic in misc3_table:
        return on_misc3(operands, misc3_table[mnemonic], pred, disp_mode)
    if mnemonic == 'jr':
        return on_jr(operands)
    if mnemonic in debug_table:
        return on_debug(operands, debug_table[mnemonic])
    if mnemonic == '.int':
        return ''.join(on_dot_int(operand) for operand in operands)
    if mnemonic == '.byte':
        return ''.join(on_dot_byte(operand) for operand in operands)
    if mnemonic == '.short':
        return ''.join(on_dot_short(operand) for operand in operands)
    if mnemonic == '.space':
        return on_dot_space(operands)
    error('unknown mnemonic \'{}\''.format(mnemonic))


# ----------------------------------------------------------------------
#       macro definitions
# ----------------------------------------------------------------------

def eval_string(arg):
    try:
        s = eval(arg)
        if not isinstance(s, str):
            error('expected string literal: ' + arg)
        return s
    except Exception:
        error('invalid string literal: ' + arg)

def expand_nop(operands):
    check_operands_n(operands, 0)
    return [('add', ['r0', 'r0', 'r0', '0'])]

def mov_imm(dest, imm):
    if check_int_range(imm, 16):
        return [('ldl', [dest, str(imm)])]
    if not -0x80000000 <= imm <= 0xffffffff:
        error('immediate value too large: ' + hex(imm))
    if imm & 0xffff == 0:
        return [('ldh', [dest, 'r0', hex((imm >> 16) & 0xffff)])]
    return [('ldl', [dest, hex(imm & 0xffff)]),
            ('ldh', [dest, dest, hex((imm >> 16) & 0xffff)])]

def expand_mov(operands):
    check_operands_n(operands, 2)
    if operands[0] in regs and operands[1] in regs:
        return [('add', [operands[0], operands[1], 'r0', '0'])]
    if operands[1][0] == '[' and operands[1][-1] == ']':
        success, base, disp = parse_memaccess(operands[1])
        if not success:
            return [('ld2', [operands[0], operands[1][1:-1].strip()])]
        if check_int_range(disp, 18):
            return [('ld', [operands[0], base, str(disp)])]
        return [('ldh', ['r29', 'r0', hex(disp >> 16 & 0xffff)])] + \
              ([('add', ['r29', base, 'r29', '0'])] if base != 'r0' else []) + \
               [('ld', [operands[0], 'r29', hex(disp & 0xffff)])]
    if operands[0][0] == '[' and operands[0][-1] == ']':
        success, base, disp = parse_memaccess(operands[0])
        if not success:
            return [('st2', [operands[1], operands[0][1:-1].strip()])]
        if check_int_range(disp, 18):
            d, p = (operands[1], []) if operands[1] in regs else ('r29', expand_mov(['r29', operands[1]]))
            return p + [('st', [d, base, str(disp)])]
        return [('ldh', ['r29', 'r0', hex(disp >> 16 & 0xffff)])] + \
              ([('add', ['r29', base, 'r29', '0'])] if base != 'r0' else []) + \
               [('st', [operands[1], 'r29', hex(disp & 0xffff)])]
    success, imm = parse_int(operands[1])
    if success:
        return mov_imm(operands[0], imm)
    success, imm = parse_float(operands[1])
    if success:
        return mov_imm(operands[0], float_to_bit(imm))
    if operands[0] in regs:
        return [('mov', operands)]
    error('invalid syntax')

# and, sub, shl, shr, sar, and, or, xor, cmpne, cmpeq, cmplt, cmple
def expand_alu(op, operands):
    check_operands_n(operands, 3, 4)
    if (len(operands) == 4):
        return [(op, operands)]
    if operands[2] in regs:
        return [(op, operands + ['0'])]
    success, imm = parse_int(operands[2])
    if success:
        if check_int_range(imm, 8):
            return [(op, [operands[0], operands[1], 'r0', operands[2]])]
        return mov_imm('r29', imm) + [(op, [operands[0], operands[1], 'r29', '0'])]
    error('expected register or immediate value: ' + operands[2])

def expand_movb(operands):
    if operands[1][0] == '[' and operands[1][-1] == ']':
        success, base, disp = parse_memaccess(operands[1])
        if not success:
            return [('ldb2', [operands[0], operands[1][1:-1].strip()])]
        if check_int_range(disp, 16):
            return [('ldb', [operands[0], base, str(disp)])]
        return [('ldh', ['r29', 'r0', hex((disp + 0x8000) >> 16 & 0xffff)])] + \
              ([('add', ['r29', base, 'r29', '0'])] if base != 'r0' else []) + \
               [('ldb', [operands[0], 'r29', hex(((disp + 0x8000) & 0xffff) - 0x8000)])]
    if operands[0][0] == '[' and operands[0][-1] == ']':
        success, base, disp = parse_memaccess(operands[0])
        if not success:
            return [('stb2', [operands[1], operands[0][1:-1].strip()])]
        if check_int_range(disp, 16):
            d, p = (operands[1], []) if operands[1] in regs else ('r29', expand_mov('r29', operands[1]))
            return p + [('stb', [d, base, str(disp)])]
        return [('ldh', ['r29', 'r0', hex((disp + 0x8000) >> 16 & 0xffff)])] + \
              ([('add', ['r29', base, 'r29', '0'])] if base != 'r0' else []) + \
               [('stb', [operands[1], 'r29', hex(((disp + 0x8000) & 0xffff) - 0x8000)])]
    error('movb only supports move between register and memory')

def expand_neg(operands):
    check_operands_n(operands, 2)
    return [('sub', [operands[0], 'r0', operands[1], '0'])]

def expand_not(operands):
    check_operands_n(operands, 2)
    return [('xor', [operands[0], operands[1], 'r0', '-1'])]

def expand_sextb(operands):
    check_operands_n(operands, 2)
    return [('shl', ['r29', operands[1], 'r0', '24']),
            ('sar', [operands[0], 'r29', 'r0', '24'])]

def expand_sextw(operands):
    check_operands_n(operands, 2)
    return [('shl', ['r29', operands[1], 'r0', '16']),
            ('sar', [operands[0], 'r29', 'r0', '16'])]

def expand_zextb(operands):
    check_operands_n(operands, 2)
    return [('shl', ['r29', operands[1], 'r0', '24']),
            ('shr', [operands[0], 'r29', 'r0', '24'])]

def expand_zextw(operands):
    check_operands_n(operands, 2)
    return [('ldh', [operands[0], operands[1], '0'])]

# cmpgt, cmpge, cmpugt, cmpuge
def expand_cmpgt(mnemonic, operands):
    check_operands_n(operands, 3)
    m = mnemonic.replace('g', 'l')
    if operands[2] in regs:
        return [(m, [operands[0], operands[2], operands[1], '0'])]
    success, imm = parse_int(operands[2])
    if success:
        return mov_imm('r29', imm) + [(m, [operands[0], 'r29', operands[1], '0'])]
    error('expected register or immediate value: ' + operands[2])

def expand_fcmpgt(operands):
    check_operands_n(operands, 3)
    return [('fcmplt', [operands[0], operands[2], operands[1]])]

def expand_fcmpge(operands):
    check_operands_n(operands, 3)
    return [('fcmple', [operands[0], operands[2], operands[1]])]

def expand_read(operands):
    check_operands_n(operands, 1)
    return [('ldh', ['r29', 'r0', '0x8000']),
            ('ld', [operands[0], 'r29', '0x1000']),
            ('cmplt', ['r29', operands[0], 'r0', '0']),
            ('bne', ['r29', 'r0', '-16'])]

def expand_write(operands):
    check_operands_n(operands, 1, 2)
    if len(operands) == 1:
        return [('ldh', ['r29', 'r0', '0x8000']),
                ('ld', ['r29', 'r29', '0x1004']),
                ('beq', ['r29', 'r0', '-12']),
                ('ldh', ['r29', 'r0', '0x8000']),
                ('st', [operands[0], 'r29', '0x1000'])]
    s = eval_string(operands[1])
    l = [mov_imm(operands[0], ord(c)) + [('st', [operands[0], 'r29', '0x1000'])] for c in s]
    return [('ldh', ['r29', 'r0', '0x8000'])] + sum(l, [])

def expand_jr(operands):
    check_operands_n(operands, 1, 2)
    if len(operands) == 1:
        return [('jr', ['r29', operands[0]])]
    return [('jr', operands)]

def expand_br(operands):
    check_operands_n(operands, 1)
    return [('jl', ['r29', operands[0]])]

def expand_bz(operands, pred):
    check_operands_n(operands, 2)
    return [('beq' + pred, [operands[0], 'r0', operands[1]])]

def expand_bnz(operands, pred):
    check_operands_n(operands, 2)
    return [('bne' + pred, [operands[0], 'r0', operands[1]])]

# bne, beq
def expand_bne(op, operands, pred):
    check_operands_n(operands, 3)
    success, imm = parse_int(operands[1])
    if success:
        return mov_imm('r29', imm) + [(op + pred, [operands[0], 'r29', operands[2]])]
    return [(op + pred, operands)]

# blt, ble, bgt, bge
def expand_blt(op, operands, pred):
    check_operands_n(operands, 3)
    b, c = ('beq', 'cmple') if op == 'bgt' else \
           ('beq', 'cmplt') if op == 'bge' else \
           ('bne', 'cmp' + op[1:])
    return expand_alu(c, ['r29', operands[0], operands[1]]) + [(b + pred, ['r29', 'r0', operands[2]])]

# bflt, bfle, bfgt, bfge
def expand_bfne(op, operands, pred):
    check_operands_n(operands, 3)
    b, c = ('beq', 'fcmple') if op == 'bfgt' else \
           ('beq', 'fcmplt') if op == 'bfge' else \
           ('bne', 'fcmp' + op[2:])
    return [(c, ['r29', operands[0], operands[1]]),
            (b + pred, ['r29', 'r0', operands[2]])]

def expand_push(operands):
    check_operands_n(operands, 1)
    pre = [('sub', ['rsp', 'rsp', 'r0', '4'])]
    success, imm = parse_int(operands[0])
    if success:
        return mov_imm('r29', imm) + pre + [('st', ['r29', 'rsp', '0'])]
    return pre + [('st', [operands[0], 'rsp', '0'])]

def expand_pop(operands):
    check_operands_n(operands, 1)
    return [('ld', [operands[0], 'rsp', '0']),
            ('add', ['rsp', 'rsp', 'r0', '4'])]

def expand_call(operands):
    check_operands_n(operands, 1)
    if operands[0] in regs:
        return [('st', ['rbp', 'rsp', '-4']),
                ('sub', ['rsp', 'rsp', 'r0', '4']),
                ('add', ['rbp', 'rsp', 'r0', '0']),
                ('jr', ['r28', operands[0]]),
                ('add', ['rsp', 'rbp', 'r0', '4']),
                ('ld', ['rbp', 'rsp', '-4'])]
    return [('call', operands)]

def expand_ret(operands):
    check_operands_n(operands, 0)
    return [('jr', ['r29', 'r28'])]

def expand_enter(operands):
    check_operands_n(operands, 0, 1)
    success, imm = parse_int(operands[0] if operands else '0')
    if success:
        if imm & 3 != 0:
            error('immediate value must be a multiple of 4')
        return expand_alu('sub', ['rsp', 'rsp', str(imm + 4)]) + [('st', ['r28', 'rsp', '0'])]
    error('expected integer literal: ' + operands[0])

def expand_leave(operands):
    check_operands_n(operands, 0)
    return [('ld', ['r28', 'rsp', '0'])]

def expand_halt(operands):
    check_operands_n(operands, 0)
    return [('beq+', ['r31', 'r31', '-4'])]

def expand_dot_float(operands):
    def go(operand):
        success, floimm = parse_float(operand)
        if not success:
            error('expected floating point literal: ' + operand)
        return hex(float_to_bit(floimm))
    return [('.int', map(go, operands))]

def expand_dot_space(operands):
    check_operands_n(operands, 1, 2)
    if len(operands) == 2:
        return [('.space', operands)]
    return [('.space', [operands[0], '0'])]

def expand_dot_string(operands):
    check_operands_n(operands, 1)
    s = eval_string(operands[0])
    return [('.byte', [str(ord(c)) for c in s] + ['0'])]

macro_table = {
    'nop':      expand_nop,
    'mov':      expand_mov,
    'movb':     expand_movb,
    'neg':      expand_neg,
    'not':      expand_not,
    'sextb':    expand_sextb,
    'sextw':    expand_sextw,
    'zextb':    expand_zextb,
    'zextw':    expand_zextw,
    'fcmpgt':   expand_fcmpgt,
    'fcmpge':   expand_fcmpge,
    'read':     expand_read,
    'write':    expand_write,
    'jr':       expand_jr,
    'br':       expand_br,
    'push':     expand_push,
    'pop':      expand_pop,
    'call':     expand_call,
    'ret':      expand_ret,
    'enter':    expand_enter,
    'leave':    expand_leave,
    'halt':     expand_halt,
    '.float':   expand_dot_float,
    '.space':   expand_dot_space,
    '.string':  expand_dot_string,
}

def expand_macro(line):
    mnemonic, operands = parse(line)
    if not mnemonic:
        return []
    if mnemonic in macro_table:
        return macro_table[mnemonic](operands)
    if mnemonic in ['add', 'sub', 'shl', 'shr', 'sar', 'and', 'or', 'xor', 'adda',
                    'cmpne', 'cmpeq', 'cmplt', 'cmple', 'cmpult', 'cmpule']:
        return expand_alu(mnemonic, operands)
    if mnemonic in ['cmpgt', 'cmpge', 'cmpugt', 'cmpuge']:
        return expand_cmpgt(mnemonic, operands)
    m = re.match(r'(\w+)([+-]?)$', mnemonic)
    if m:
        br_mnemonic, pred = m.groups()
        if br_mnemonic == 'bz':
            return expand_bz(operands, pred)
        if br_mnemonic == 'bnz':
            return expand_bnz(operands, pred)
        if br_mnemonic in ['bne', 'beq']:
            return expand_bne(br_mnemonic, operands, pred)
        if br_mnemonic in ['blt', 'ble', 'bgt', 'bge']:
            return expand_blt(br_mnemonic, operands, pred)
        if br_mnemonic in ['bflt', 'bfle', 'bfgt', 'bfge']:
            return expand_bfne(br_mnemonic, operands, pred)
    return [(mnemonic, operands)]


# ----------------------------------------------------------------------
#       label resolution
# ----------------------------------------------------------------------

labels = {}
rev_labels = {}
library = []
entry_point = 0x2000
start_label = 'main'

ofs_table = {
    'mov':       8,
    'ld2':       8,
    'ldb2':      8,
    'st2':       8,
    'stb2':      8,
    'call':     32,
    'call6':    24,
    'call7':    28,
}

def add_label(label, i):
    if label in regs:
        error('\'{}\' is register name'.format(label))
    if parse_int(label)[0]:
        error('\'{}\' can be parsed as integer'.format(label))
    if re.search(r'[^\w.$!?]', label):
        c = re.search(r'[^\w.$!?]', label).group()
        error('label name cannot contain \'{}\' character'.format(c))
    labels.setdefault(label, {}).setdefault(filename, [-1, False, False])
    if labels[label][filename][0] >= 0:
        error('duplicate declaration of label \'{}\''.format(label))
    labels[label][filename][0] = i
    rev_labels.setdefault(i, []).append(label)

def add_global(label):
    labels.setdefault(label, {}).setdefault(filename, [-1, False, False])
    labels[label][filename][1] = True

def label_addr(label):
    dic = labels.get(label, {})
    if filename in dic:
        decl = [filename]
    else:
        decl = filter(lambda x: dic[x][1], dic)
    if len(decl) == 0:
        if label == start_label:
            fatal('global label \'{}\' is required'.format(label))
        else:
            error('label \'{}\' is not declared'.format(label))
    if len(decl) > 1 and not set(decl) <= set(library):
        decl = list(set(decl) - set(library))
    if len(decl) > 1:
        msg = 'label \'{}\' is declared in multiple files ({})'.format(label, ', '.join(sorted(decl)))
        if label == start_label:
            fatal(msg)
        else:
            error(msg)
    dic[decl[0]][2] = True
    return dic[decl[0]][0]

def eval_expr(expr):
    r = re.compile(r'[\w.$!?]+')
    m = r.search(expr)
    while m:
        success, imm = parse_int(m.group())
        if not success:
            addr = str(label_addr(m.group()))
            expr = expr[:m.start()] + addr + expr[m.end():]
        m = r.search(expr, m.end() if success else m.start() + len(addr))
    try:
        res = eval(expr, {})
        if not isinstance(res, int):
            error('expression type must be int')
        return res
    except Exception:
        error('eval error: ' + expr)

def calc_ofs(mnemonic, operands, addr=0):
    if mnemonic[-1] == ':' or mnemonic in ['.global', '.set']:
        return 0
    if mnemonic == '.align':
        align = int(operands[0], 0)
        return ((addr + align - 1) & ~(align - 1)) - addr
    if mnemonic == '.byte':
        return len(operands)
    if mnemonic == '.int':
        return 4 * len(operands)
    if mnemonic == '.short':
        return 2 * len(operands)
    if mnemonic == '.space':
        return int(operands[0], 0)
    return ofs_table.get(mnemonic, 4)

def init_label_first(lines):
    global labels, rev_labels, filename, pos
    labels = {}
    rev_labels = {}
    addr = entry_point
    for mnemonic, operands, filename, pos in lines:
        if mnemonic[-1] == ':':
            if len(operands) > 0:
                error('label declaration must be followed by new line')
            add_label(mnemonic[:-1], addr)
        elif mnemonic == '.align':
            check_operands_n(operands, 1)
            success, imm = parse_int(operands[0])
            if not success:
                error('expected integer literal: ' + operands[0])
            if imm < 4 or (imm & (imm - 1)) > 0:
                error('alignment must be a power of 2 which is not less than 4')
            addr += ((addr + imm - 1) & ~(imm - 1)) - addr
        elif mnemonic == '.byte':
            addr += len(operands)
        elif mnemonic == '.global':
            check_operands_n(operands, 1)
            add_global(operands[0])
        elif mnemonic == '.int':
            addr += 4 * len(operands)
        elif mnemonic == '.set':
            check_operands_n(operands, 2)
            add_label(operands[0], eval_expr(operands[1]))
        elif mnemonic == '.short':
            addr += 2 * len(operands)
        elif mnemonic == '.space':
            check_operands_n(operands, 2)
            success, imm = parse_int(operands[0])
            if not success:
                error('expected integer literal: ' + operands[0])
            addr += imm
        else:
            if addr & 3:
                error('instruction must be aligned on 4-byte boundaries')
            addr += ofs_table.get(mnemonic, 4)

def init_label(lines):
    global labels, rev_labels, filename, pos
    labels = {}
    rev_labels = {}
    addr = entry_point
    for mnemonic, operands, filename, pos in lines:
        if mnemonic[-1] == ':':
            add_label(mnemonic[:-1], addr)
        elif mnemonic == '.global':
            add_global(operands[0])
        elif mnemonic == '.set':
            add_label(operands[0], eval_expr(operands[1]))
        else:
            addr += calc_ofs(mnemonic, operands, addr)

def optimize(lines):
    global filename, pos
    eff = 0
    addr = entry_point
    for i, (mnemonic, operands, filename, pos) in enumerate(lines):
        if mnemonic == 'mov':
            addr += 8
            if check_int_range(eval_expr(operands[1]), 16):
                eff += 4
                lines[i] = ('mov1', operands, filename, pos)
        elif mnemonic in ['ld2', 'st2']:
            addr += 8
            if check_int_range(eval_expr(operands[1]), 18):
                eff += 4
                lines[i] = (mnemonic[:2] + '1', operands, filename, pos)
        elif mnemonic in ['ldb2', 'stb2']:
            addr += 8
            if check_int_range(eval_expr(operands[1]), 16):
                eff += 4
                lines[i] = (mnemonic[:3] + '1', operands, filename, pos)
        elif mnemonic in ['call', 'call7']:
            val = label_addr(operands[0])
            if check_int_range(val - addr - 16 + (eff if val > addr else -eff), 18):
                eff += ofs_table[mnemonic] - 24
                lines[i] = ('call6', operands, filename, pos)
            elif mnemonic == 'call' and check_int_range(val, 16):
                eff += 4
                lines[i] = ('call7', operands, filename, pos)
            addr += ofs_table[mnemonic]
        else:
            addr += calc_ofs(mnemonic, operands, addr)
    return eff > 0

def resolve_label(lines):
    global filename, pos
    ret = []
    addr = entry_point
    for mnemonic, operands, filename, pos in lines:
        if mnemonic[-1] == ':' or mnemonic in ['.global', '.set']:
            continue
        if mnemonic == 'mov1':
            addr += 4
            ret.append(('ldl', [operands[0], hex(eval_expr(operands[1]))], filename, pos))
            continue
        if mnemonic == 'mov':
            addr += 8
            val = eval_expr(operands[1])
            if not -0x80000000 <= val <= 0xffffffff:
                if not filename:
                    fatal('address of start label is too large: ' + hex(val))
                else:
                    error('expression value too large: ' + hex(val))
            ret.append(('ldl', [operands[0], hex(val & 0xffff)], filename, pos))
            ret.append(('ldh', [operands[0], operands[0], hex(val >> 16 & 0xffff)], filename, pos))
            continue
        if mnemonic in ['ld1', 'ldb1', 'st1', 'stb1']:
            addr += 4
            ret.append((mnemonic[:-1], [operands[0], 'r0', hex(eval_expr(operands[1]))], filename, pos))
            continue
        if mnemonic in ['ld2', 'ldb2', 'st2', 'stb2']:
            addr += 8
            val = eval_expr(operands[1])
            if not -0x80000000 <= val <= 0xffffffff:
                error('expression value too large: ' + hex(val))
            hi, lo = (val + 0x8000) >> 16 & 0xffff, ((val + 0x8000) & 0xffff) - 0x8000
            ret.append(('ldh', ['r29', 'r0', hex(hi)], filename, pos))
            ret.append((mnemonic[:-1], [operands[0], 'r29', hex(lo)], filename, pos))
            continue
        if mnemonic in ['call', 'call6', 'call7']:
            addr += ofs_table[mnemonic]
            val = label_addr(operands[0])
            if not -0x80000000 <= val <= 0xffffffff:
                error('expression value too large: ' + hex(val))
            pre = [('st', ['rbp', 'rsp', '-4']),
                   ('sub', ['rsp', 'rsp', 'r0', '4']),
                   ('add', ['rbp', 'rsp', 'r0', '0'])]
            if mnemonic == 'call6':
                mid = [('jl', ['r28', hex(val - addr + 8)])]
            else:
                if mnemonic == 'call7':
                    mid = [('ldl', ['r29', hex(val)])]
                else:
                    mid = [('ldl', ['r29', hex(val & 0xffff)]),
                           ('ldh', ['r29', 'r29', hex(val >> 16 & 0xffff)])]
                mid.append(('jr', ['r28', 'r29']))
            post = [('add', ['rsp', 'rbp', 'r0', '4']), ('ld', ['rbp', 'rsp', '-4'])]
            ret.extend(map(lambda (x, y): (x, y, filename, pos), pre + mid + post))
            continue
        if mnemonic == '.align':
            align = int(operands[0], 0)
            padding = ((addr + align - 1) & ~(align - 1)) - addr
            if padding:
                addr += padding
                ret.append(('.space', [str(padding), '0'],filename, pos))
            continue
        if mnemonic in ['jl', 'bne', 'bne-', 'bne+', 'beq', 'beq-', 'beq+']:
            check_operands_n(operands, 2, 3)
            if not parse_int(operands[-1])[0]:
                operands[-1] = hex(label_addr(operands[-1]) - addr - 4)
        if mnemonic == '.int':
            def go(operand):
                val = eval_expr(operand)
                if not -0x80000000 <= val <= 0xffffffff:
                    error('expression value too large: ' + hex(val))
                return str(val) if check_int_range(val, 8) else hex(val)
            operands = map(go, operands)
        addr += calc_ofs(mnemonic, operands)
        ret.append((mnemonic, operands, filename, pos))
    if addr - entry_point > 0x400000:
        fatal('program size exceeds 4MB limit ({:,} bytes)'.format(addr - entry_point))
    return ret

def check_global(label):
    if labels[label][filename][0] < 0:
        error('label \'{}\' is not declared'.format(label))

def warn_unused_label(label):
    if not labels[label][filename][2] and not (filename in library and labels[label][filename][1]):
        warning('unused label \'{}\''.format(label))

def show_label(i):
    if i in rev_labels:
        return format(', '.join(rev_labels[i]))
    return ''


# ----------------------------------------------------------------------
#       main process
# ----------------------------------------------------------------------

# parse command line arguments
argparser = argparse.ArgumentParser(usage='%(prog)s [options] file...')
argparser.add_argument('inputs', nargs='*', help='input files', metavar='file...')
argparser.add_argument('-a', help='output as rs232c send test format', action='store_true')
argparser.add_argument('-c', help='do not append file header', action='store_true')
argparser.add_argument('-e', help='set entry point address', metavar='<integer>')
argparser.add_argument('-f', help='append label to end of program', metavar='<label>')
argparser.add_argument('-k', help='output as array of std_logic_vector format', action='store_true')
argparser.add_argument('-l', help='set library file to <file>', metavar='<file>', action='append')
argparser.add_argument('-o', help='set output file to <file>', metavar='<file>', default='a.out')
argparser.add_argument('-O', help='set optimization level', metavar='<integer>', default=2, type=int)
argparser.add_argument('-r', help='do not insert main label jump instruction', action='store_true')
argparser.add_argument('-s', help='output preprocessed assembly', action='store_true')
argparser.add_argument('-start', help='same as -t (deprecated)', metavar='<label>', dest='t')
argparser.add_argument('-t', help='start execution from <label>', metavar='<label>')
argparser.add_argument('-v', help='output more detailed assembly than -s', action='store_true')
argparser.add_argument('-Wno-unused-label', help='disable unused label warning', action='store_true')
argparser.add_argument('-Wr29', help='enable use of r29 warning', action='store_true')
args = argparser.parse_args()
if args.inputs == []:
    argparser.print_help(sys.stderr)
    sys.exit(1)
if args.e:
    success, entry_point = parse_int(args.e)
    if not success:
        argparser.print_usage(sys.stderr)
        fatal('argument -e: expected integer: ' + args.e)
    if entry_point & 3 != 0:
        argparser.print_usage(sys.stderr)
        fatal('argument -e: entry address must be a multiple of 4')
    if entry_point < 0:
        argparser.print_usage(sys.stderr)
        fatal('argument -e: entry address must be zero or positive')
if args.l:
    library = map(os.path.relpath, args.l)
    args.inputs = library + args.inputs
if args.t:
    start_label = args.t

# 0. preprocess
lines0 = []
for filename in args.inputs:
    filename = os.path.relpath(filename)
    if not os.path.isfile(filename):
        fatal('file does not exist: ' + filename)
    with open(filename, 'r') as f:
        srcs[filename] = {}
        for pos, line in enumerate(f):
            line = line.strip()
            if line:
                srcs[filename][pos + 1] = line
                lines0.append((line, filename, pos + 1))
if lines0:
    lines0.append(('.align 4', lines0[-1][1], lines0[-1][2]))
if args.f:
    lines0.append(('.global ' + args.f, '_end', 0))
    lines0.append((args.f + ':', '_end', 0))

# 1. macro expansion
lines1 = []
if not args.r:
    lines1 = [('mov', ['r29', start_label], '', 0), ('jr', ['r29', 'r29'], '', 0)]
for line, filename, pos in lines0:
    lines = expand_macro(line)
    lines1.extend(map(lambda (x, y): (x, y, filename, pos), lines))
if args.Wr29:
    f = p = ''
    for mnemonic, operands, filename, pos in lines1:
        if 'r29' in operands and not (f == filename and p == pos):
            f, p = filename, pos
            warning('r29 is used', True)

# 2. label resolution (by 2-pass algorithm)
init_label_first(lines1)
while args.O > 0 and optimize(lines1):
    args.O -= 1
    init_label(lines1)
lines2 = resolve_label(lines1)
for mnemonic, operands, filename, pos in lines1:
    if mnemonic == '.global':
        check_global(operands[0])
    if mnemonic[-1] == ':' and not args.Wno_unused_label:
        warn_unused_label(mnemonic[:-1])

# 3. assemble
if args.s or args.v:
    with open(args.o + '.s', 'w') as f:
        addr = entry_point
        prev_pos = -1
        prev_file = ''
        for mnemonic, operands, filename, pos in lines2:
            if prev_file != filename:
                print >> f, '\n# file: ' + filename
                prev_file = filename
            s = '{:#08x}  {:7} {}'.format(addr, mnemonic, ', '.join(operands))
            l = show_label(addr)
            if args.v:
                b = code(mnemonic, operands).ljust(4, '\0')[0:4]
                comment = '# [{:08x}]  '.format(struct.unpack('<I', b)[0])
                if l:
                    comment += '(' + l + ')  '
                if prev_pos != pos and filename:
                    comment += srcs[filename][pos]
                    prev_pos = pos
            else:
                comment = '# ' + l if l else ''
            print >> f, '{:39} {}'.format(s, comment).rstrip()
            addr += calc_ofs(mnemonic, operands)

def write(f, byterepr):
    if args.k:
        f.write("{} => x\"{:08x}\",\n".format(i, struct.unpack('<I', byterepr)[0]))
    elif args.a:
        fmt = """
        wait for BR; RS_RX <= '0';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '{}';
        wait for BR; RS_RX <= '1';

        wait for (2 * BR);

"""
        for b in byterepr:
            a = ord(b)
            ps = ['1' if a & (1 << j) else '0' for j in range(8)]
            f.write(fmt.format(*ps))
    else:
        f.write(byterepr)

with open(args.o, 'w') as f:
    size = 0
    if not (args.c or args.k):
        write(f, 'size')
    for i, (mnemonic, operands, filename, pos) in enumerate(lines2):
        byterepr = code(mnemonic, operands)
        write(f, byterepr)
        size += len(byterepr)
    if args.k:
        f.write("others => (others => '0')\n")
    elif not args.c:
        f.seek(0)
        byterepr = ''.join(chr(size >> x & 255) for x in [0, 8, 16, 24])
        write(f, byterepr)

