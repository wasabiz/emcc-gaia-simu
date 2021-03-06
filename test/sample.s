
# ----------------------------------------------------------------------
#       assembly sample
# ----------------------------------------------------------------------

# comment

label:

.global main
main:

    # primitive mnemonics
    add     r1, r2, r3, 4
    sub     r1, r2, r3, 4
    shl     r1, r2, r3, 4
    shr     r1, r2, r3, 4
    sar     r1, r2, r3, 4
    and     r1, r2, r3, 4
    or      r1, r2, r3, 4
    xor     r1, r2, r3, 4
    cmpult  r1, r2, r3, 4
    cmpule  r1, r2, r3, 4
    cmpne   r1, r2, r3, 4
    cmpeq   r1, r2, r3, 4
    cmplt   r1, r2, r3, 4
    cmple   r1, r2, r3, 4
    fcmplt  r1, r2, r3
    fcmple  r1, r2, r3
    fadd    r1, r2, r3
    fsub    r1, r2, r3
    fmul    r1, r2, r3
    ftoi    r1, r2
    itof    r1, r2
    floor   r1, r2
    ldl     r1, 2
    ldh     r1, r2, 3
    sysenter
    sysexit
    st      r1, r2, 4
    ld      r1, r2, 4
    jl      r1, 4
    jr      r1, r2
    bne     r1, r2, 4
    beq     r1, r2, 4
    fadd.neg r1, r2, r3
    fsub.abs r1, r2, r3
    fmul.abs.neg r1, r2, r3
    bne-    r1, r2, 4
    beq+    r1, r2, 4
    break   5
    penv    8
    ptrace  13

    # macros
    nop
    mov     rsp, rbp
    mov     r1, 2
    mov     r1, 234567
    mov     r1, 1.0
    mov     r1, 2.3
    mov     r1, label + label2 * 3
    mov     r1, label * 300
    mov     r1, [r2 + 4]
    mov     r1, [0x12345678]
    mov     r1, [r2 + 0x76543210]
    mov     r1, [label + 8]
    mov     r1, [label + 600000]
    mov     [r1 - 8], r2
    mov     [r1 + 4], 5
    mov     [0x12345678], r2
    mov     [r1 + 0x76543210], r2
    mov     [label + 8], r2
    mov     [label + 800000], r2
    movb    r1, [r2 + 3]
    movb    r1, [r2 + 34567]
    movb    r1, [label + 1]
    movb    r1, [label + 123456]
    movb    [r1 + 2], r3
    movb    [r1 + 234567], r8
    movb    [label + 1], r2
    movb    [label + 54321], r0
    add     r1, r2, r3
    add     r1, r2, 3
    add     r1, r2, 345
    add     r1, r2, 345678
    neg     r1, r2
    not     r1, r2
    zextb   r1, r2
    zextw   r1, r2
    sextb   r1, r2
    sextw   r1, r2
    cmpugt  r1, r2, r3
    cmpuge  r1, r2, 3
    cmpgt   r1, r2, r3
    cmpge   r1, r2, 3
    fcmpgt  r1, r2, r3
    fcmpge  r1, r2, r3
    read    r1
    write   r1
    write   r1, "\"Hello, world!\"\n"
    jr      r1
    br      label
    bz+     r1, label2
    bnz-    r1, label3
    bne     r1, r2, label
    beq     r1, 2, label
    blt+    r1, r2, label
    ble-    r1, 2, label
    bgt+    r1, r2, label
    bge-    r1, 234, label
    bflt+   r1, r2, label
    bfgt-   r1, r2, label
    push    r1
    push    23
    pop     r1
    call    r1
    call    label
    ret
    enter
    enter   16
    leave
    halt

    # directives
    .byte   1, 2, 3
    .string "literal"
    .align  4
    .int    42, 84, 126, 168
    .int    label & ~label2
    .float  -1.2e34, 5.6
    .set    label2, 0x1234
    .set    label3, label + label2 * 4
    .short  77, 777, 7777
    .space  7
    .space  2, 123

