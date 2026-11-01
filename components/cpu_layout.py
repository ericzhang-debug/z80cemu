"""ctypes layout for the bundled redcode Z80 DLL."""
import ctypes as C

READ = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint16)
WRITE = C.CFUNCTYPE(None, C.c_void_p, C.c_uint16, C.c_uint8)

class CPU(C.Structure):
    _fields_ = [('cycles', C.c_size_t), ('cycle_limit', C.c_size_t), ('context', C.c_void_p)] + [(n, C.c_void_p) for n in ('fetch_opcode','fetch','read','write','in_','out','halt','nop','nmia','inta','int_fetch','ld_i_a','ld_r_a','reti','retn','hook','illegal')] + [('data', C.c_uint32), ('ix_iy', C.c_uint16 * 2)] + [(n, C.c_uint16) for n in ('pc','sp','xy','memptr','af','af_','bc','bc_','de','de_','hl','hl_')] + [(n, C.c_uint8) for n in ('r','i','r7','im','request','resume','iff1','iff2','q','options','int_line','halt_line')]
