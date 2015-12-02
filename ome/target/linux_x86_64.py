# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from . import arch_x86_64 as arch

class Target_Linux_x86_64(arch.Target_x86_64):
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

%define PROT_READ 0x1
%define PROT_WRITE 0x2
%define PROT_EXEC 0x4

%define STDOUT 1
%define STDERR 2
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
	mov rax, SYS_exit
	syscall

; rdi = file descriptor
; rsi = point to string
; rdx = number of bytes
OME_write:
	mov rax, SYS_write
	syscall
	ret

OME_allocate_thread_context:
	mov rax, SYS_mmap
	xor rdi, rdi                                            ; addr
	mov rsi, STACK_SIZE + NURSERY_SIZE*2 + PAGE_SIZE*2      ; size
	xor rdx, rdx                                            ; PROT_NONE
	mov r10, MAP_PRIVATE|MAP_ANONYMOUS
	mov r8, r8
	dec r8
	xor r9, r9
	syscall
	lea rdi, [rax+PAGE_SIZE]  ; save pointer returned by mmap
	push rdi
	shr rax, 47   ; test for MAP_FAILED or address that is too big
	jnz .panic
	mov rax, SYS_mprotect
	mov rsi, STACK_SIZE + NURSERY_SIZE*2
	mov rdx, PROT_READ|PROT_WRITE
	syscall
	test rax, rax
	js .panic
	pop rax
	ret
.panic:
	lea rsi, [rel OME_message_mmap_failed]
	mov rdx, OME_message_mmap_failed.size
	jmp OME_panic
''' + arch.builtin_code
