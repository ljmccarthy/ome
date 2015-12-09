# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from . import arch_x86_64 as arch

class Target_Linux_x86_64(arch.Target_x86_64):

    platform = ('Linux', 'x86_64')

    @classmethod
    def get_assembler_args(cls, outfile):
        return ['yasm', '-f', 'elf64', '-o', outfile, '-']

    @classmethod
    def get_linker_args(cls, infile, outfile):
        return ['ld', '-s', '-o', outfile, infile]

    builtin_methods = arch.builtin_methods

    builtin_macros = arch.builtin_macros + '''
; System call numbers
%define SYS_write 1
%define SYS_mmap 9
%define SYS_mprotect 10
%define SYS_munmap 11
%define SYS_mremap 25
%define SYS_exit 60

%define MAP_PRIVATE 0x2
%define MAP_ANONYMOUS 0x20
%define MREMAP_MAYMOVE 0x1

%define PROT_READ 0x1
%define PROT_WRITE 0x2
%define PROT_EXEC 0x4

%define STDOUT 1
%define STDERR 2

%define EXIT_SUCCESS 0
%define EXIT_FAILURE 1
'''

    builtin_data = 'section .rodata\n\n' + arch.builtin_data

    builtin_code = '''
section .text

bits 64
default rel

global _start
_start:
	jmp OME_start

; rdi = exit code
OME_exit:
	mov eax, SYS_exit
	syscall

; rdi = file descriptor
; rsi = point to string
; rdx = number of bytes
OME_write:
	mov eax, SYS_write
	syscall
	ret

; rdi = size in bytes
OME_vmem_allocate:
	mov eax, SYS_mmap
	mov rsi, rdi                            ; size
	xor rdi, rdi                            ; addr
	mov edx, PROT_READ|PROT_WRITE           ; prot
	mov r10d, MAP_PRIVATE|MAP_ANONYMOUS     ; flags
	xor r8, r8
	dec r8                                  ; fd
	xor r9, r9                              ; offset
	syscall
	test rax, rax
	js .panic
	ret
.panic:
	lea rsi, [rel OME_message_mmap_failed]
	mov edx, OME_message_mmap_failed.size
	jmp OME_panic

; rdi = pointer to block allocated by OME_vm_allocate
; rsi = old size
; rdx = new size
OME_vmem_resize:
	mov eax, SYS_mremap
	mov r10d, MREMAP_MAYMOVE
	syscall
	test rax, rax
	js OME_vmem_allocate.panic
	ret

OME_allocate_thread_context:
	mov eax, SYS_mmap
	xor rdi, rdi                                            ; addr
	mov esi, STACK_SIZE*2 + NURSERY_SIZE*2 + PAGE_SIZE*2    ; size
	xor rdx, rdx                                            ; PROT_NONE
	mov r10d, MAP_PRIVATE|MAP_ANONYMOUS
	xor r8, r8
	dec r8
	xor r9, r9
	syscall
	lea rdi, [rax+PAGE_SIZE]  ; save pointer returned by mmap
	push rdi
	shr rax, 47   ; test for MAP_FAILED or address that is too big
	jnz .panic
	mov eax, SYS_mprotect
	mov esi, STACK_SIZE*2 + NURSERY_SIZE*2
	mov edx, PROT_READ|PROT_WRITE
	syscall
	test rax, rax
	js .panic
	pop rax
	ret
.panic:
	add rsp, 8
	lea rsi, [rel OME_message_mmap_failed]
	mov edx, OME_message_mmap_failed.size
	jmp OME_panic
''' + arch.builtin_code
