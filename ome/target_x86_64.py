# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from .ast import BuiltInMethod
from .constants import *

def get_sp_adjustment(num_stack_slots):
    """
    Return number of bytes to adjust stack pointer.
    Enforced 16 byte alignment.
    """
    n = num_stack_slots * 8
    return n + (n % 16)

class Target_x86_64(object):
    stack_pointer = 'rsp'
    context_pointer = 'rbp'
    nursery_bump_pointer = 'rbx'
    nursery_limit_pointer = 'r12'
    arg_registers = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
    return_register = 'rax'
    temp_registers = ('r10', 'r11')

    def __init__(self, emitter):
        self.emit = emitter
        self.num_jumpback_labels = 0
        self.num_traceback_labels = 0

    def emit_enter(self, num_stack_slots):
        if num_stack_slots > 0:
            self.emit('sub rsp, %s', get_sp_adjustment(num_stack_slots))

    def emit_leave(self, num_stack_slots):
        self.emit.label('.exit')
        if num_stack_slots > 0:
            self.emit('add rsp, %s', get_sp_adjustment(num_stack_slots))
        self.emit('ret')

    def emit_empty_dispatch(self):
        self.emit('jmp OME_not_understood_error')

    def emit_dispatch(self, any_constant_tags):
        self.emit('mov rax, %s', self.arg_registers[0])
        self.emit('shr rax, %s', NUM_DATA_BITS)
        if any_constant_tags:
            self.emit('cmp rax, %s', Tag_Constant)
            self.emit('je .constant')
        self.emit.label('.dispatch')
        if any_constant_tags:
            const_emit = self.emit.tail_emitter('.constant')
            const_emit('mov eax, edi')
            const_emit('add rax, 0x%x', MIN_CONSTANT_TAG)
            const_emit('jmp .dispatch')
        not_understood_emit = self.emit.tail_emitter('.not_understood')
        not_understood_emit('jmp OME_not_understood_error')

    def emit_dispatch_compare_eq(self, tag, tag_label, exit_label):
        self.emit('cmp rax, 0x%X', tag)
        self.emit('jne %s', exit_label)
        self.emit('jmp %s', tag_label)

    def emit_dispatch_compare_gte(self, tag, gte_label):
        self.emit('cmp rax, 0x%X', tag)
        self.emit('jae %s', gte_label)

    def emit_jump(self, label):
        self.emit('jmp %s', label)

    def MOVE(self, ins):
        self.emit('mov %s, %s', ins.dest_reg, ins.source_reg)

    def SPILL(self, ins):
        self.emit('mov [rsp+%s], %s', ins.stack_slot * 8, ins.register)

    def UNSPILL(self, ins):
        self.emit('mov %s, [rsp+%s]', ins.register, ins.stack_slot * 8)

    def PUSH(self, ins):
        self.emit('push %s', ins.source_reg)

    def CALL(self, ins):
        if ins.traceback_info:
            traceback_label = '.traceback_%d' % self.num_traceback_labels
            self.num_traceback_labels += 1
        else:
            traceback_label = '.exit'

        self.emit('call %s', ins.call_label)
        if ins.num_stack_args > 0:
            self.emit('add rsp, %s', ins.num_stack_args * 8)
        self.emit('test rax, rax')
        self.emit('js %s', traceback_label)

        if ins.traceback_info:
            tb_emit = self.emit.tail_emitter(traceback_label)
            tb_emit('mov rdi, [rbp+TC_traceback_pointer]')
            tb_emit('lea rsi, [rdi+TB_SIZE]')
            tb_emit('cmp rsi, rsp')  # Check to make sure we don't overwrite stack
            tb_emit('ja .exit')
            tb_emit('mov [rbp+TC_traceback_pointer], rsi')
            tb_emit('lea rsi, [rel %s]', ins.traceback_info.file_info)
            tb_emit('mov [rdi+TB_file_info], rsi')
            tb_emit('lea rsi, [rel %s]', ins.traceback_info.source_line)
            tb_emit('mov [rdi+TB_source_line], rsi')
            tb_emit('jmp .exit')

    def emit_tag(self, reg, tag):
        self.emit('shl %s, %s', reg, NUM_TAG_BITS - 3)
        self.emit('or %s, %s', reg, tag)
        self.emit('ror %s, %s', reg, NUM_TAG_BITS)

    def TAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit_tag(ins.dest, ins.tag)

    def UNTAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit('shl %s, %s', ins.dest, NUM_TAG_BITS)
        self.emit('shr %s, %s', ins.dest, NUM_TAG_BITS - 3)

    def LOAD_VALUE(self, ins):
        value = encode_tagged_value(ins.value, ins.tag)
        if value == 0:
            self.emit('xor %s, %s', ins.dest, ins.dest)
        else:
            self.emit('mov %s, 0x%x', ins.dest, value)

    def LOAD_STRING(self, ins):
        self.emit('lea %s, [rel %s]', ins.dest, ins.data_label)
        self.emit_tag(ins.dest, Tag_String)

    def GET_SLOT(self, ins):
        self.emit('mov %s, [%s+%s]', ins.dest, ins.object, ins.slot_index * 8)

    def SET_SLOT(self, ins):
        self.emit('mov [%s+%s], %s', ins.object, ins.slot_index * 8, ins.value)

    def emit_create(self, dest, num_slots):
        return_label = '.gc_return_%d' % self.num_jumpback_labels
        full_label = '.gc_full_%d' % self.num_jumpback_labels
        self.num_jumpback_labels += 1

        self.emit.label(return_label)
        self.emit('mov %s, %s', dest, self.nursery_bump_pointer)
        self.emit('add %s, %s', self.nursery_bump_pointer, (num_slots + 1) * 8)
        self.emit('cmp %s, %s', self.nursery_bump_pointer, self.nursery_limit_pointer)
        self.emit('jae %s', full_label)
        self.emit('mov dword [%s], %s', dest, num_slots)  # TODO: GC header
        self.emit('add %s, 8', dest)

        tail_emit = self.emit.tail_emitter(full_label)
        tail_emit('call OME_collect_nursery')
        tail_emit('jmp %s', return_label)

    def CREATE(self, ins):
        self.emit_create(ins.dest, ins.num_slots)

    def CREATE_ARRAY(self, ins):
        self.emit_create(ins.dest, ins.size)
        self.emit('mov dword [%s-4], %s', ins.dest, ins.size)

    builtin_code = '''\
%define OME_NUM_TAG_BITS {NUM_TAG_BITS}
%define OME_NUM_DATA_BITS {NUM_DATA_BITS}

%define OME_Value(value, tag) (((tag) << OME_NUM_DATA_BITS) | (value))
%define OME_Constant(value) OME_Value(value, Tag_Constant)
%define OME_Error_Tag(tag) ((tag) | (1 << (OME_NUM_TAG_BITS - 1)))
%define OME_Error_Constant(value) OME_Value(value, OME_Error_Tag(Tag_Constant))

%define Tag_Boolean 0
%define Tag_Constant 1
%define Tag_Small_Integer 2
%define Tag_String 256
%define Constant_BuiltIn 1
%define Constant_NotUnderstoodError 2
%define Constant_TypeError 3
%define Constant_IndexError 4
%define Constant_OverflowError 5
%define Constant_DivideByZeroError 6

%define False OME_Value(0, Tag_Boolean)
%define True OME_Value(1, Tag_Boolean)

%define TC_stack_limit 0
%define TC_traceback_pointer 8
%define TC_SIZE 16

%define TB_file_info 0
%define TB_source_line 8
%define TB_SIZE 16

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

%macro gc_alloc 3
	mov %1, rbx
	add rbx, (%2) + 8
	cmp rbx, r12
	jae %3
	mov dword [%1], %2
	add %1, 8
%endmacro

%macro gc_return 1
	call OME_collect_nursery
	jmp %1
%endmacro

%macro get_tag 1
	shr %1, OME_NUM_DATA_BITS
%endmacro

%macro tag_pointer 2
	shl %1, OME_NUM_TAG_BITS - 3
	or %1, %2
	ror %1, OME_NUM_TAG_BITS
%endmacro

%macro tag_value 2
	shl %1, OME_NUM_TAG_BITS
	or %1, %2
	ror %1, OME_NUM_TAG_BITS
%endmacro

%macro tag_integer 1
	tag_value %1, Tag_Small_Integer
%endmacro

%macro untag_pointer 1
	shl %1, OME_NUM_TAG_BITS
	shr %1, OME_NUM_TAG_BITS - 3
%endmacro

%macro untag_value 1
	shl %1, OME_NUM_TAG_BITS
	shr %1, OME_NUM_TAG_BITS
%endmacro

%macro untag_integer 1
	shl %1, OME_NUM_TAG_BITS
	sar %1, OME_NUM_TAG_BITS
%endmacro

%macro constant_string 2
%1:
	dd .end-$-5
	db %2, 0
.end:
	align 8
%endmacro

default rel

global _start
_start:
	call OME_allocate_thread_context
	lea rsp, [rax+0x1000-TC_SIZE]   ; stack pointer (grows down)
	mov rbp, rsp                    ; thread context pointer
	lea rbx, [rsp+TC_SIZE]          ; GC nursery pointer (grows up)
	lea r12, [rax+0x4000]           ; GC nursery limit
	mov [rbp+TC_stack_limit], rax
	mov [rbp+TC_traceback_pointer], rax
	call OME_toplevel               ; create top-level block
	mov rdi, rax
	call {MAIN}             ; call main method on top-level block
	xor rdi, rdi
	test rax, rax
	jns .success
.abort:
	; save error value
	shl rax, 1
	shr rax, 1
	push rax
	; print traceback
	mov r13, [rbp+TC_stack_limit]
	mov r14, [rbp+TC_traceback_pointer]
	sub r14, TC_SIZE
	cmp r14, r13
	jb .failure
	lea rsi, [rel OME_message_traceback]
	mov rdx, OME_message_traceback.size
	mov rax, SYS_write
	mov rdi, 2
	syscall
.tbloop:
	mov rsi, [r14+TB_file_info]
	mov edx, dword [rsi]
	add rsi, 4
	mov rax, SYS_write
	mov rdi, 2
	syscall
	mov rsi, [r14+TB_source_line]
	mov edx, dword [rsi]
	add rsi, 4
	mov rax, SYS_write
	mov rdi, 2
	syscall
	sub r14, TC_SIZE
	cmp r14, r13
	jae .tbloop
.failure:
	; print error value
	call .newline
	pop rsi
	mov rdi, 2
	call OME_print_value
	call .newline
	mov rdi, 1
.success:
	mov rax, SYS_exit
	syscall
.newline:
	lea rsi, [rel OME_message_traceback]
	mov rdx, 1
	mov rax, SYS_write
	mov rdi, 2
	syscall
	ret

OME_allocate_thread_context:
	mov rax, SYS_mmap
	xor rdi, rdi	  ; addr
	mov rsi, 0xA000   ; size
	xor rdx, rdx	  ; PROT_NONE
	mov r10, MAP_PRIVATE|MAP_ANONYMOUS
	mov r8, r8
	dec r8
	xor r9, r9
	syscall
	lea rdi, [rax+0x1000]  ; save pointer returned by mmap
	push rdi
	shr rax, 47   ; test for MAP_FAILED or address that is too big
	jnz .panic
	mov rax, SYS_mprotect
	mov rsi, 0x8000
	mov rdx, PROT_READ|PROT_WRITE
	syscall
	test rax, rax
	js .panic
	pop rax
	ret
.panic:
	mov rsi, OME_message_mmap_failed
	mov rdx, OME_message_mmap_failed.size
	jmp OME_panic

OME_collect_nursery:
	lea rsi, [rel OME_message_collect_nursery]
	mov rdx, OME_message_collect_nursery.size
OME_panic:
	mov rax, SYS_write
	mov rdi, 2
	syscall
	mov rax, SYS_exit
	mov rdi, 1
	syscall

; rdi = file descriptor
; rsi = value
OME_print_value:
	push rdi
	mov rdi, rsi
	call OME_message_string__0
	pop rdi
	mov rsi, rax
	get_tag rax
	cmp rax, Tag_String
	jne OME_type_error
	untag_pointer rsi
	mov edx, dword [rsi]
	add rsi, 4
	mov rax, SYS_write
	syscall
	ret

OME_type_error:
	mov rax, OME_Error_Constant(Constant_TypeError)
	ret

OME_index_error:
	mov rax, OME_Error_Constant(Constant_IndexError)
	ret

OME_not_understood_error:
	mov rax, OME_Error_Constant(Constant_NotUnderstoodError)
	ret

OME_check_overflow:
	mov rdx, rax
	shl rdx, OME_NUM_TAG_BITS
	sar rdx, OME_NUM_TAG_BITS
	cmp rdx, rax
	jne OME_overflow_error
	tag_integer rax
	ret

OME_overflow_error:
	mov rax, OME_Error_Constant(Constant_OverflowError)
	ret

OME_divide_by_zero_error:
	mov rax, OME_Error_Constant(Constant_DivideByZeroError)
	ret
'''

    builtin_data = '''\
align 8
constant_string OME_string_false, "False"
constant_string OME_string_true, "True"
constant_string OME_string_not_understood_error, "Not-Understood-Error"
constant_string OME_string_type_error, "Type-Error"
constant_string OME_string_index_error, "Index-Error"
constant_string OME_string_overflow_error, "Overflow-Error"
constant_string OME_string_divide_by_zero_error, "Divide-By-Zero-Error"

OME_message_traceback:
.str:	db 10, "Traceback (most recent call last):"
.size equ $-.str

OME_message_mmap_failed:
.str:	db "Aborted: Failed to allocate thread context", 10
.size equ $-.str

OME_message_collect_nursery:
.str:	db "Garbage collector called", 10
.size equ $-.str
'''

    builtin_methods = [

BuiltInMethod('print:', constant_to_tag(Constant_BuiltIn), ['string'], '''\
	mov rdi, 1
	jmp OME_print_value
'''),

BuiltInMethod('catch:', constant_to_tag(Constant_BuiltIn), ['do'], '''\
	mov rdi, rsi
	call OME_message_do__0
	shl rax, 1              ; clear error bit if present
	shr rax, 1
	ret
'''),

BuiltInMethod('try:', constant_to_tag(Constant_BuiltIn), ['do', 'catch:'],'''\
	sub rsp, 16
	mov [rsp], rsi
	mov rdi, rsi
	call OME_message_do__0
	test rax, rax
	jns .exit
	shl rax, 1      ; clear error bit if present
	shr rax, 1
	mov rdi, [rsp]
	mov rsi, rax
	call OME_message_catch__1
.exit:
	add rsp, 16
	ret
'''),

BuiltInMethod('error:', constant_to_tag(Constant_BuiltIn), [], '''\
	mov rax, rsi
	shl rax, 1
	or al, 1        ; set error bit
	ror rax, 1      ; rotate error bit in to position
	ret
'''),

BuiltInMethod('for:', constant_to_tag(Constant_BuiltIn), ['do', 'while'], '''\
	sub rsp, 16
	mov [rsp], rsi
	mov rdi, rsi
.loop:
	call OME_message_while__0
	mov rdi, [rsp]
	test rax, rax
	jz .exit                ; exit if |while| returned False
	js .exit                ; exit if |while| returned an error
	cmp rax, True           ; compare with True
	jne .type_error         ; if not True then we have a type error
	call OME_message_do__0
	mov rdi, [rsp]
	test rax, rax
	jns .loop               ; repeat if |do| did not return an error
.exit:
	add rsp, 16
	ret
.type_error:
	add rsp, 16
	mov rax, OME_Error_Constant(Constant_TypeError)
	ret
'''),

BuiltInMethod('string', Tag_String, [], '''\
	mov rax, rdi
	ret
'''),

BuiltInMethod('string', Tag_Boolean, [], '''\
	lea rax, [rel OME_string_false]
	test rdi, rdi
	jz .exit
	lea rax, [rel OME_string_true]
.exit:
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', constant_to_tag(Constant_NotUnderstoodError), [], '''\
	lea rax, [rel OME_string_not_understood_error]
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', constant_to_tag(Constant_TypeError), [], '''\
	lea rax, [rel OME_string_type_error]
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', constant_to_tag(Constant_IndexError), [], '''\
	lea rax, [rel OME_string_index_error]
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', constant_to_tag(Constant_OverflowError), [], '''\
	lea rax, [rel OME_string_overflow_error]
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', constant_to_tag(Constant_DivideByZeroError), [], '''\
	lea rax, [rel OME_string_divide_by_zero_error]
	tag_pointer rax, Tag_String
	ret
'''),

BuiltInMethod('string', Tag_Small_Integer, [], '''\
	untag_integer rdi               ; untag integer
.gc_return_0:
	gc_alloc rsi, 24, .gc_full_0    ; pre-allocate string on heap
	mov r11, rsi
	tag_pointer r11, Tag_String     ; tagged and ready for returning
	mov rcx, rsp                    ; rcx = string output cursor
	sub rsp, 16                     ; allocate temp stack space for string
	mov r10, 10                     ; divisor
	dec rcx
	mov byte [rcx], 0       ; nul terminator
	mov rax, rdi            ; number for division
	test rax, rax
	jns .divloop
	neg rax
.divloop:
	xor rdx, rdx            ; clear for division
	dec rcx                 ; next character
	idiv r10                ; divide by 10
	add dl, '0'             ; digit in remainder
	mov byte [rcx], dl      ; store digit
	test rax, rax           ; loop if not zero
	jnz .divloop
	test rdi, rdi
	jns .positive
	dec rcx
	mov byte [rcx], '-'     ; add sign
.positive:
	lea rdi, [rsp+16]       ; original stack pointer
	mov rdx, rdi
	sub rdx, rcx            ; compute length
	mov dword [rsi], edx    ; store length
	add rsi, 4
	; copy from stack to allocated string
.copyloop:
	mov al, byte [rcx]
	mov byte [rsi], al
	inc rsi
	inc rcx
	cmp rcx, rdi
	jb .copyloop
	mov rsp, rdi    ; restore stack pointer
	mov rax, r11    ; tagged return value
	ret
.gc_full_0:
	gc_return .gc_return_0
'''),

BuiltInMethod('plus:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rdi
	untag_integer rax
	add rax, rdi
	jmp OME_check_overflow
'''),

BuiltInMethod('minus:', Tag_Small_Integer, [], '''\
	mov rax, rdi
	mov rdx, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rax
	untag_integer rdx
	sub rax, rdx
	jmp OME_check_overflow
'''),

BuiltInMethod('times:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rdi
	untag_integer rax
	imul rdi
	mov rcx, rdx
	sar rcx, 64    ; get all 0 or 1 bits
	cmp rcx, rdx
	jne OME_overflow_error
	jmp OME_check_overflow
'''),

BuiltInMethod('div:', Tag_Small_Integer, [], '''\
	mov rax, rdi
	mov rcx, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rax
	untag_integer rcx
	test rcx, rcx
	jz OME_divide_by_zero_error
	mov rdx, rax
	sar rdx, 32
	idiv ecx
	shl rax, 32
	sar rax, 32
	tag_integer rax
	ret
'''),

BuiltInMethod('mod:', Tag_Small_Integer, [], '''\
	mov rax, rdi
	mov rcx, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rax
	untag_integer rcx
	test rcx, rcx
	jz OME_divide_by_zero_error
	mov rdx, rax
	sar rdx, 32
	idiv ecx
	mov rax, rdx
	shl rax, 32
	sar rax, 32
	tag_integer rax
	ret
'''),

BuiltInMethod('less-than:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rax
	cmp rax, Tag_Small_Integer
	jne OME_type_error
	untag_integer rdi
	untag_integer rsi
	xor rax, rax
	cmp rdi, rsi
	setl al
	ret
'''),

BuiltInMethod('less-or-equal:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rax
	cmp rax, Tag_Small_Integer
	jne OME_type_error
	untag_integer rdi
	untag_integer rsi
	xor rax, rax
	cmp rdi, rsi
	setle al
	ret
'''),

BuiltInMethod('equals:', Tag_Small_Integer, [], '''\
	xor rax, rax
	cmp rdi, rsi
	sete al
	ret
'''),

BuiltInMethod('not', Tag_Boolean, [], '''\
	mov rax, rdi
	xor rax, 1
	ret
'''),

BuiltInMethod('and:', Tag_Boolean, [], '''\
	mov rax, rdi
	test rax, rax
	jz .exit
	mov rax, rsi
.exit:
	ret
'''),

BuiltInMethod('or:', Tag_Boolean, [], '''\
	mov rax, rdi
	test rax, rax
	jnz .exit
	mov rax, rsi
.exit:
	ret
'''),

BuiltInMethod('equals:', Tag_Boolean, [], '''\
	xor rax, rax
	cmp rdi, rsi
	sete al
	ret
'''),

BuiltInMethod('then:', Tag_Boolean, ['do'], '''\
	mov rax, rdi
	mov rdi, rsi
	test rax, rax
	jnz OME_message_do__0
	ret
'''),

BuiltInMethod('if:', Tag_Boolean, ['then', 'else'], '''\
	mov rax, rdi
	mov rdi, rsi
	test rax, rax
	jnz OME_message_then__0
	jmp OME_message_else__0
'''),


BuiltInMethod('size', Tag_Array, [], '''\
	untag_pointer rdi
	mov eax, dword [rdi-4]
	tag_integer rax
	ret
'''),

BuiltInMethod('at:', Tag_Array, [], '''\
	untag_pointer rdi
	mov rax, rsi
	get_tag rax
	cmp rax, Tag_Small_Integer
	jne OME_type_error
	untag_integer rsi
	test rsi, rsi
	js OME_index_error
	mov ecx, dword [rdi-4]          ; load array size
	cmp rsi, rcx                    ; check index
	jae OME_index_error
	mov rax, qword [rdi+rsi*8]
	ret
'''),

BuiltInMethod('each:', Tag_Array, ['item:'], '''\
	sub rsp, 32
	untag_value rdi
	mov ecx, dword [rdi*8-4]  ; load array size
	test ecx, ecx             ; check if zero
	jz .exit
	lea rcx, [rdi+rcx]      ; end of array
	mov [rsp], rdi          ; save array pointer
	mov [rsp+8], rcx        ; save end pointer
	mov [rsp+16], rsi       ; save block
	mov rdx, rdi
	mov rdi, rsi
.loop:
	mov rsi, qword [rdx*8]
	call OME_message_item__1
	test rax, rax           ; check for error
	js .exit
	mov rdx, [rsp]          ; load array pointer
	mov rcx, [rsp+8]        ; load end pointer
	mov rdi, [rsp+16]       ; load block
	inc rdx
	mov [rsp], rdx
	cmp rdx, rcx
	jb .loop
	xor rax, rax            ; return False
.exit:
	add rsp, 32
	ret
''')

]
