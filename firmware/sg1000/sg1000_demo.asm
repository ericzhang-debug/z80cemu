; Z80SimPlatform SG-1000 compatible diagnostic ROM, 2026.
; Shows a simple title on a TMS9918A in 40-column text mode.
ORG 0x0000
    DI
    LD SP, 0xDFFF
    ; R0 text mode, R1 display enabled, R2 name table, R4 pattern table.
    LD A, 0x00
    OUT (0xBF), A
    LD A, 0x80
    OUT (0xBF), A
    LD A, 0x50
    OUT (0xBF), A
    LD A, 0x81
    OUT (0xBF), A
    LD A, 0x00
    OUT (0xBF), A
    LD A, 0x82
    OUT (0xBF), A
    LD A, 0x01
    OUT (0xBF), A
    LD A, 0x84
    OUT (0xBF), A
    LD A, 0xF4
    OUT (0xBF), A
    LD A, 0x87
    OUT (0xBF), A
    ; Write 6 character patterns at VRAM 0800h, including blank character 0.
    XOR A
    OUT (0xBF), A
    LD A, 0x48
    OUT (0xBF), A
    LD HL, Font
    LD B, 48
FontLoop:
    LD A, (HL)
    OUT (0xBE), A
    INC HL
    DJNZ FontLoop
    ; Name table row 10, column 16.
    LD A, 0xA0
    OUT (0xBF), A
    LD A, 0x41
    OUT (0xBF), A
    LD HL, Title
    LD B, 7
TitleLoop:
    LD A, (HL)
    OUT (0xBE), A
    INC HL
    DJNZ TitleLoop
Forever:
    HALT
    JR Forever
Title:
    DB 1, 2, 3, 4, 5, 5, 5
Font:
    DB 0,0,0,0,0,0,0,0
    DB 0x78,0x80,0x80,0x70,0x08,0x08,0xF0,0
    DB 0x70,0x88,0x80,0xB8,0x88,0x88,0x78,0
    DB 0,0,0,0xF8,0,0,0,0
    DB 0x20,0x60,0x20,0x20,0x20,0x20,0x70,0
    DB 0x70,0x88,0x98,0xA8,0xC8,0x88,0x70,0
