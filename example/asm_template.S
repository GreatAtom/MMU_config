/**
 * @brief MIPS CRAM.
 * @version 2.0 08/07/2019
 */

#include "mips.h"

    .set        noreorder
    .set        mips32

    .text

### Fill TLB for test
.macro tlb_entry_init tlb_index page_size_mask virt_addr entryLo0 entryLo1
    li k0, \tlb_index           # Set TLB Index
    mtc0 k0, C0_INX             # Write CP0 Index Register
    li k0, \page_size_mask      # Set Page Size
    mtc0 k0, C0_PGMASK          # Write CP0 PageMask Register
    li k0, \virt_addr           # Set Virtual Page Number
    mtc0 k0, C0_TLBHI           # Write CP0 EntryHi
    li k0, \entryLo0            # Set Physical Page Number, Cacheble, Dirty, Valid, Global
    mtc0 k0, C0_TLBLO0          # Write CP0 EntryLo0
    li k0, \entryLo1            # Set Physical Page Number, Cacheble, Dirty, Valid, Global
    mtc0 k0, C0_TLBLO1          # Write CP0 EntryLo1
    tlbwi                       # Write entry in TLB
.endm
#####################

    .org	0x0000
_reset_vector: .global _reset_vector
    j _start
    nop

#------------------------------------------------
# Exception or Interrupt
#
    .org	0x0180
_exc_int_vector: .global _exc_int_vector
    #Flat jump to programm address by address 180 -> 180
	li k0, GENERAL_EXCEPTION
	j k0
	nop


#------------------------------------------------
# TLB refill vector at 0xbfc00200
#
    .org	0x0200
_int_vector: .global _int_vector
    #Flat jump to programm address by address 200 -> 200
    ### Fill TLB for test
    li k0, ${tlb_page_size}     # Set Page Size (${tlb_page_size_bytes}B)
    mtc0 k0, C0_PGMASK          # Write CP0 PageMask Register
    mfc0 k0, C0_BADVADDR        # Load BADVADDR (virt addr)
    li k1, ${virt_addr_mask}    # Load mask (${tlb_page_size_bytes}B) for (virt addr)
    and k0, k0, k1              # And mask to virt addr
    mtc0 k0, C0_TLBHI           # Write CP0 EntryHi
    srl k0, k0, 0x6             # Count Physical Page Number
    ori k0, 0x00000007          # Set Cacheble, Dirty, Valid, Global
    mtc0 k0, C0_TLBLO0          # Write CP0 EntryLo0 (Physical Page Number)
    addu k0, k0, 0x40000        # add 16MB(>>) to EntryLo0 for EntryLo1 (Physical Page Number)
    mtc0 k0, C0_TLBLO1          # Write CP0 EntryLo1
    tlbwr                       # Write entry in TLB
    eret


#------------------------------------------------
# Exception vector at 0xbfc00380
#
    .org	0x0380
_exception_vector: .global _exception_vector
    li k0, EXCEPTION_OTHER
    jr k0
    nop


#------------------------------------------------
# Interrupt vector at 0xbfc00400
#
    .org	0x0400
_interrupt_vector: .global _interrupt_vector
    li k0, EXCEPTION_INTERRUPT
    jr k0
    nop

_start: .global _start


## Reset CSR
    li t0, CSR_ADDR              # Set CSR address
    lw t1, 0(t0)                 # Load CSR
    ehb                          # Clear hazard barrier
    and t1, t1, CSR_FM_DIS       # Set TLB mode
    or t1, t1, CSR_TR_CRAM       # Set TR_CRAM to CRAM mode
    or t1, t1, CSR_FLUSH         # Flush cache
    sw t1, 0(t0)                 # Write back CSR
    li k0, ${wired}                     # Set WIRED
    mtc0 k0, C0_WIRED            # Set WIRED
    ehb                          # Clear hazard barrier

### Fill TLB for test
    ###########    tlb_index  page_mask  virt_addr  entryLo0   entryLo1
    ${macros_call}

# Set IV to 1 ( move interrupt vector to 0x200 )
    li k0, 0x00800000
    mtc0 k0, C0_CAUSE
    nop
    nop
    nop
    nop
    nop
    nop
    li k0, MAIN_PROG_ADDR
    nop
    nop
    nop
    nop
    nop
    nop
    jr k0
    nop
    nop

_exit:
    # Jump to main program on 0xc0000000
//local_loop:
//    nop
//    nop
//    nop
//    nop
//    j local_loop
    nop
    nop
    nop
    nop

    li k0, MAIN_PROG_ADDR
    nop
    nop
    nop
    nop
    nop
    nop
    jr k0
    nop
    nop
    nop
    nop
    nop
    nop
