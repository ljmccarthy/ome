# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ..ast import BuiltInMethod
from ..constants import *

DWORD_MAX = (1 << 32) - 1

byte_register = {
    'rax': 'al',
    'rbx': 'bl',
    'rcx': 'cl',
    'rdx': 'dl',
    'rsi': 'sil',
    'rdi': 'dil',
    'rbp': 'bpl',
    'rsp': 'spl',
    'r8':  'r8b',
    'r9':  'r9b',
    'r10': 'r10b',
    'r11': 'r11b',
    'r12': 'r12b',
    'r13': 'r13b',
    'r14': 'r14b',
    'r15': 'r15b',
}

dword_register = {
    'rax': 'eax',
    'rbx': 'ebx',
    'rcx': 'ecx',
    'rdx': 'edx',
    'rsi': 'esi',
    'rdi': 'edi',
    'rbp': 'ebp',
    'rsp': 'esp',
    'r8':  'r8d',
    'r9':  'r9d',
    'r10': 'r10d',
    'r11': 'r11d',
    'r12': 'r12d',
    'r13': 'r13d',
    'r14': 'r14d',
    'r15': 'r15d',
}

# Register usage
#
# rsp - Call stack pointer (grows down)
# rbp - Thread context pointer, bottom of call stack
# r13 - GC allocation pointer
# r14 - GC allocation limit
# r15 - Data stack pointer (grows up)
#
# The GC scans and updates the data stack and ignores the call stack.
# GC-allocated pointers must never be stored in the call stack.
# The data stack must contain only tagged values or GC-allocated pointers.

class Target_x86_64(object):
    return_register = 'rax'
    arg_registers = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
    temp_registers = ('r10', 'r11')

    define_constant_format = '%define {0} {1}\n'

    def __init__(self, emitter):
        self.emit = emitter
        self.num_jumpback_labels = 0
        self.num_traceback_labels = 0
        self.tracebacks = {}

    def emit_enter(self, num_stack_slots):
        if num_stack_slots > 0:
            self.emit('add dsp, %s', num_stack_slots * 8)

    def emit_leave(self, num_stack_slots):
        self.emit.label('.exit')
        if num_stack_slots > 0:
            self.emit('sub dsp, %s', num_stack_slots * 8)
        self.emit('ret')

    def emit_empty_dispatch(self):
        self.emit('jmp OME_not_understood_error')

    def emit_dispatch(self, any_constant_tags):
        self.emit('mov rax, %s', self.arg_registers[0])
        self.emit('get_tag rax')
        if any_constant_tags:
            self.emit('cmp eax, %s', Tag_Constant)
            self.emit('je .constant')
        self.emit.label('.dispatch')
        if any_constant_tags:
            const_emit = self.emit.tail_emitter('.constant')
            const_emit('mov eax, edi')
            const_emit('add eax, 0x%x', MIN_CONSTANT_TAG)
            const_emit('jmp .dispatch')
        not_understood_emit = self.emit.tail_emitter('.not_understood')
        not_understood_emit('jmp OME_not_understood_error')

    def emit_dispatch_compare_eq(self, tag, tag_label, exit_label):
        self.emit('cmp eax, 0x%x', tag)
        self.emit('jne %s', exit_label)
        self.emit('jmp %s', tag_label)

    def emit_dispatch_compare_gte(self, tag, gte_label):
        self.emit('cmp eax, 0x%x', tag)
        self.emit('jae %s', gte_label)

    def emit_jump(self, label):
        self.emit('jmp %s', label)

    def MOVE(self, ins):
        self.emit('mov %s, %s', ins.dest_reg, ins.source_reg)

    def SPILL(self, ins):
        self.emit('mov [dsp-%s], %s', ins.stack_slot * 8, ins.register)

    def UNSPILL(self, ins):
        self.emit('mov %s, [dsp-%s]', ins.register, ins.stack_slot * 8)

    def PUSH(self, ins):
        self.emit('mov [dsp], %s', ins.source_reg)
        self.emit('add dsp, 8')

    def CALL(self, ins):
        if ins.traceback_info and ins.check_error:
            if ins.traceback_info.id in self.tracebacks:
                traceback_label = self.tracebacks[ins.traceback_info.id]
            else:
                traceback_label = '.traceback_%d' % self.num_traceback_labels
                self.num_traceback_labels += 1
                self.tracebacks[ins.traceback_info.id] = traceback_label
                tb_emit = self.emit.tail_emitter(traceback_label)
                tb_emit('lea rdi, [rel %s]', ins.traceback_info.file_info)
                tb_emit('lea rsi, [rel %s]', ins.traceback_info.source_line)
                tb_emit('mov edx, %s', (ins.traceback_info.column << 16) | ins.traceback_info.underline)
                tb_emit('call OME_append_traceback')
                tb_emit('jmp .exit')
        else:
            traceback_label = '.exit'

        self.emit('call %s', ins.call_label)
        if ins.num_stack_args > 0:
            self.emit('sub dsp, %s', ins.num_stack_args * 8)
        if ins.check_error:
            self.emit('test rax, rax')
            self.emit('js %s', traceback_label)

    def TAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit('tag_pointer %s, %s', ins.dest, ins.tag)

    def UNTAG(self, ins):
        if ins.dest != ins.source:
            self.emit('mov %s, %s', ins.dest, ins.source)
        self.emit('untag_pointer %s', ins.dest)

    def LOAD_VALUE(self, ins):
        tagged_value = encode_tagged_value(ins.value, ins.tag)
        if tagged_value == 0:
            self.emit('xor %s, %s', ins.dest, ins.dest)
        else:
            rot_value = (ins.value << NUM_TAG_BITS) | ins.tag
            if tagged_value > DWORD_MAX and rot_value <= DWORD_MAX:
                self.emit('mov %s, 0x%x', dword_register[ins.dest], rot_value)
                self.emit('ror %s, %s', ins.dest, NUM_TAG_BITS)
            elif tagged_value <= DWORD_MAX:
                self.emit('mov %s, 0x%x', dword_register[ins.dest], tagged_value)
            else:
                self.emit('mov %s, 0x%x', ins.dest, tagged_value)

    def LOAD_LABEL(self, ins):
        self.emit('lea %s, [rel %s]', ins.dest, ins.label)
        self.emit('tag_pointer %s, %s', ins.dest, ins.tag)

    def GET_SLOT(self, ins):
        self.emit('mov %s, [%s+%s]', ins.dest, ins.object, ins.slot_index * 8)

    def SET_SLOT(self, ins):
        self.emit('mov [%s+%s], %s', ins.object, ins.slot_index * 8, ins.value)

builtin_macros = '''
%define GC_DEBUG      0
%define PAGE_SIZE     0x1000
%define STACK_SIZE    0x800
%define NURSERY_SIZE  0x7800

%define OME_Value(value, tag) (((tag) << NUM_DATA_BITS) | (value))
%define OME_Constant(value) OME_Value(value, Tag_Constant)
%define OME_Error_Tag(tag) ((tag) | (1 << (NUM_TAG_BITS - 1)))
%define OME_Error_Constant(value) OME_Value(value, OME_Error_Tag(Tag_Constant))

%define False OME_Value(0, Tag_Boolean)
%define True OME_Value(1, Tag_Boolean)

; Data stack pointer
%define dsp r15

%macro save 1-*
	%assign %%offset 0
	%rep %0
	mov qword [dsp+%%offset], %1
	%assign %%offset %%offset+8
	%rotate 1
	%endrep
	lea dsp, [dsp+%%offset]
%endmacro

%macro restore 1-*
	lea dsp, [dsp-%%size]
	%assign %%offset 0
	%rep %0
	mov %1, qword [dsp+%%offset]
	%assign %%offset %%offset+8
	%rotate 1
	%endrep
	%%size equ %%offset
%endmacro

%macro drop 1
	lea dsp, [dsp-(%1)*8]
%endmacro

struc LargeObjectHeader
	.next: resq 1
	.prev: resq 1
	.header: resq 1
	.size:
endstruc

; Thread context structure
struc TC
	.call_stack_limit: resq 1
	.traceback_pointer: resq 1
	.nursery_base: resq 1
	.data_stack_base: resq 1
	.large_object_next: resq 1
	.large_object_prev: resq 2
	.size:
endstruc

; Traceback entry structure
struc TB
	.file_info: resq 1
	.source_line: resq 1
	.column: resq 1
	.size:
endstruc

struc StringBuffer
	.buffer: resq 1
	.cached_string: resq 1
	.position: resd 1
	align 8
	.size:
endstruc

%macro get_gc_object_size 2
	mov %1, [%2-8]
	shr %1, NUM_GC_HEADER_FLAGS
	and %1, GC_SIZE_MASK
%endmacro

%macro get_gc_object_size_bytes 2
	get_gc_object_size %1, %2
	shl %1, 3
%endmacro

%macro get_tag 1
	shr %1, NUM_DATA_BITS
%endmacro

%macro get_tag_noerror 1
	shl %1, 1
	shr %1, NUM_DATA_BITS + 1
%endmacro

%macro tag_pointer 2
	shl %1, NUM_TAG_BITS
	or %1, %2
	ror %1, NUM_TAG_BITS
%endmacro

%macro tag_value 2
	shl %1, NUM_TAG_BITS
	or %1, %2
	ror %1, NUM_TAG_BITS
%endmacro

%macro tag_integer 1
	tag_value %1, Tag_Small_Integer
%endmacro

%macro untag_pointer 1
	shl %1, NUM_TAG_BITS
	shr %1, NUM_TAG_BITS
%endmacro

%macro untag_value 1
	shl %1, NUM_TAG_BITS
	shr %1, NUM_TAG_BITS
%endmacro

%macro untag_integer 1
	shl %1, NUM_TAG_BITS
	sar %1, NUM_TAG_BITS
%endmacro

%macro unwrap_error 1
	shl %1, 1
	shr %1, 1
%endmacro

%macro object_header 2
	dq ((%2) << (GC_SIZE_BITS + NUM_GC_HEADER_FLAGS)) | ((%1) << NUM_GC_HEADER_FLAGS) | 1
%endmacro

%macro constant_string 2
%1:
	dd .end-$-5
	db %2, 0
.end:
	align 8
%endmacro
'''

builtin_code = '''
OME_start:
	call OME_allocate_thread_context
	lea rbp, [rax+STACK_SIZE-TC.size]       ; thread context pointer
	mov rsp, rbp                            ; call stack pointer (grows down)
	lea r13, [rbp+TC.size]                  ; GC nursery pointer (grows up)
	lea r14, [r13+NURSERY_SIZE]             ; GC nursery limit
	lea dsp, [r14+NURSERY_SIZE]             ; data stack pointer (grows up)
	mov [rbp+TC.call_stack_limit], rax
	mov [rbp+TC.traceback_pointer], rax
	mov [rbp+TC.nursery_base], r13
	mov [rbp+TC.data_stack_base], dsp
	lea rdi, [rbp+TC.large_object_next]
	mov [rbp+TC.large_object_next], rdi
	mov [rbp+TC.large_object_prev], rdi
	call OME_toplevel       ; create top-level block
	mov rdi, rax
	call OME_main           ; call main method on top-level block
	mov edi, EXIT_SUCCESS
	test rax, rax           ; check for error
	jns OME_exit
	unwrap_error rax
	push rax                ; save error value
	call OME_print_traceback
	call .newline           ; print error value
	pop rsi
	mov edi, STDERR
	call OME_print_value
	call .newline
	mov edi, EXIT_FAILURE
	jmp OME_exit
.newline:
	lea rsi, [rel OME_message_traceback]
	mov edx, 1
	mov edi, STDERR
	jmp OME_write

OME_print_traceback:
	push r13
	push r14
	push r15
	; print traceback
	mov r13, [rbp+TC.call_stack_limit]
	mov r14, [rbp+TC.traceback_pointer]
	sub r14, TB.size
	cmp r14, r13
	jb .exit
	lea rsi, [rel OME_message_traceback]
	mov edx, OME_message_traceback.size
	mov edi, STDERR
	call OME_write
.tbloop:
	; file and line info
	mov rsi, [r14+TB.file_info]
	mov edx, dword [rsi]
	add esi, 4
	mov edi, STDERR
	call OME_write
	; source code line
	mov rsi, [r14+TB.source_line]
	mov edx, dword [rsi]
	add rsi, 4
	mov edi, STDERR
	call OME_write
	; red squiggle underline
	mov rcx, [r14+TB.column]
	mov rdx, rcx
	and rdx, 0xffff         ; get number of squiggles
	shr rcx, 16             ; get number of spaces
	lea r15, [rcx+rdx+1+OME_vt100_red.size+OME_vt100_clear.size]
	sub rsp, r15            ; allocate temp stack space for string
	mov rdi, rsp
	mov byte [rdi], 10      ; newline
	inc rdi
	mov al, ' '
	rep stosb               ; spaces
	lea rsi, [rel OME_vt100_red]
	mov ecx, OME_vt100_red.size
	rep movsb               ; VT100 red
	mov rcx, rdx
	mov al, '^'             ; squiggles
	rep stosb
	lea rsi, [rel OME_vt100_clear]
	mov ecx, OME_vt100_clear.size
	rep movsb               ; VT100 clear
	mov rsi, rsp
	mov rdx, r15
	mov edi, STDERR
	call OME_write
	add rsp, r15
	sub r14, TB.size
	cmp r14, r13
	jae .tbloop
.exit:
	pop r15
	pop r14
	pop r13
	ret

align 16
OME_allocate_slots:
	mov rsi, rdi
; rdi = number of slots to allocate
; rsi = number of slots containing GC-scannable pointers
OME_allocate:
	mov rcx, rsi            ; number of slots to scan
	shl rcx, GC_SIZE_BITS
	or rcx, rdi             ; total number of slots
	shl rcx, NUM_GC_HEADER_FLAGS
	or ecx, GC_FLAG_PRESENT
	cmp rdi, MAX_SMALL_OBJECT_SIZE
	ja .large
	cmp rsi, rdi
	ja .toobig
	mov rax, r13
	lea r13, [r13+rdi*8+8]  ; add object size to bump pointer
	cmp r13, r14            ; check if beyond limit
	jae .full
	mov [rax], rcx          ; store header
	add rax, 8              ; return address after header
	ret
.large:
	cmp rdi, MAX_LARGE_OBJECT_SIZE
	ja .toobig
	push rcx
	lea rdi, [LargeObjectHeader.size+rdi*8]
	call OME_vmem_allocate
	pop qword [rax+LargeObjectHeader.header]
	mov rdi, [rbp+TC.large_object_next]
	mov rsi, [rbp+TC.large_object_prev]
	mov [rdi+LargeObjectHeader.prev], rax
	mov [rsi+LargeObjectHeader.next], rax
	mov [rax+LargeObjectHeader.next], rdi
	mov [rax+LargeObjectHeader.prev], rsi
	add rax, LargeObjectHeader.size
	ret
.toobig:
	lea rsi, [rel OME_message_invalid_allocation]
	mov edx, OME_message_invalid_allocation.size
	jmp OME_panic
.full:
	push rdi                ; save arguments
	push rsi
%if GC_DEBUG
	; print debug message
	lea rsi, [rel OME_message_collect_nursery]
	mov edx, OME_message_collect_nursery.size
	mov edi, STDERR
	call OME_write
%endif
	mov r10, [rbp+TC.nursery_base]
	lea rdi, [rbp+TC.size]          ; space 1 is just after the TC data
	cmp rdi, r10
	jne .space1
	add rdi, NURSERY_SIZE           ; space 2 is after space 1
.space1:
	mov [rbp+TC.nursery_base], rdi
	mov r8, [rbp+TC.data_stack_base]
.stackloop:
	mov rsi, [r8]           ; get tagged pointer from stack
	mov rax, rsi
	untag_pointer rsi
	get_tag rax
	test rax, rax
	jz .stackuntagged
	cmp rax, 255            ; check tag is pointer type
	jbe .stacknext
.stackuntagged:
	cmp rsi, r10            ; check pointer in from-space
	jb .stacknext
	cmp rsi, r14
	jae .stacknext
	mov rcx, [rsi-8]        ; get header or forwarding pointer
	test rcx, GC_FLAG_PRESENT
	jz .stackforward
	mov [rdi], rcx          ; store header in to-space
	add rdi, 8
	mov [rsi-8], rdi        ; store forwarding pointer
	mov r11, rdi
	tag_pointer r11, rax
	mov [r8], r11           ; store new pointer to stack
	shr rcx, NUM_GC_HEADER_FLAGS
	and rcx, GC_SIZE_MASK   ; get object size
	test rcx, rcx           ; sanity check object size is not 0
	jz .stacknext
	rep movsq               ; copy object
	jmp .stacknext
.stackforward:
	tag_pointer rcx, rax    ; store forwarded pointer to stack
	mov [r8], rcx
.stacknext:
	add r8, 8
	cmp r8, dsp
	jb .stackloop
	; now scan objects in to space
	mov r8, [rbp+TC.nursery_base]
	jmp .tospacenext
.tospaceloop:
	mov rdx, [r8]
	add r8, 8
	mov rcx, rdx
	shr rcx, GC_SIZE_BITS + NUM_GC_HEADER_FLAGS
	and rcx, GC_SIZE_MASK           ; get number of fields to scan
	lea r9, [r8+rcx*8]              ; compute address of last field to scan
.fieldloop:
	mov rsi, [r8]           ; get tagged pointer from field
	mov rax, rsi
	untag_pointer rsi
	get_tag rax
	test rax, rax
	jz .fielduntagged
	cmp rax, 255            ; check tag is pointer type
	jbe .fieldnext
.fielduntagged:
	cmp rsi, r10            ; check pointer in from-space
	jb .fieldnext
	cmp rsi, r14
	jae .fieldnext
	mov rcx, [rsi-8]        ; get header or forwarding pointer
	test rcx, GC_FLAG_PRESENT
	jz .fieldforward
	mov [rdi], rcx          ; store header in to-space
	add rdi, 8
	mov [rsi-8], rdi        ; store forwarding pointer
	mov r11, rdi
	tag_pointer r11, rax
	mov [r8], r11           ; store new pointer to field
	shr rcx, NUM_GC_HEADER_FLAGS
	and rcx, GC_SIZE_MASK   ; get object size
	test rcx, rcx           ; sanity check object size is not 0
	jz .fieldnext
	rep movsq               ; copy object
	jmp .fieldnext
.fieldforward:
	tag_pointer rcx, rax    ; store forwarded pointer to field
	mov [r8], rcx
.fieldnext:
	add r8, 8
	cmp r8, r9
	jb .fieldloop
	mov rcx, rdx
	shr rcx, 1                      ; get object size
	and rcx, GC_SIZE_MASK
	shr rdx, GC_SIZE_BITS + NUM_GC_HEADER_FLAGS
	and rdx, GC_SIZE_MASK           ; get number of fields to scan
	sub rcx, rdx
	lea r8, [r8+rcx*8]              ; add to end pointer
.tospacenext:
	cmp r8, rdi
	jb .tospaceloop
	mov r14, [rbp+TC.nursery_base]
	add r14, NURSERY_SIZE   ; set GC nursery limit
	mov r13, rdi            ; set GC nursery pointer
	; clear unused area
	xor rax, rax
	mov rcx, r14
	sub rcx, rdi
	shr rcx, 3
	rep stosq
%if GC_DEBUG
	; clear from-space
	mov rdi, r10
	mov rcx, NURSERY_SIZE/8
	xor rax, rax
	rep stosq
	; print debug message
	lea rsi, [rel OME_message_done]
	mov edx, OME_message_done.size
	mov edi, STDERR
	call OME_write
%endif
	pop rsi                 ; restore arguments
	pop rdi
	jmp OME_allocate

; rdi = object to resize
; rsi = new size (number of slots)
OME_resize:
	mov rax, rsi
	lea rdx, [LargeObjectHeader.size+rsi*8]
	get_gc_object_size rsi, rdi
	cmp rsi, MAX_SMALL_OBJECT_SIZE
	jbe .panic
	lea rsi, [LargeObjectHeader.size+rsi*8]
	sub rdi, LargeObjectHeader.size
	push rax
	call OME_vmem_resize
	pop rdx
	shl rdx, NUM_GC_HEADER_FLAGS
	or edx, GC_FLAG_PRESENT
	mov [rax+LargeObjectHeader.header], rdx
	mov rdi, [rax+LargeObjectHeader.next]
	mov rsi, [rax+LargeObjectHeader.prev]
	mov [rdi+LargeObjectHeader.prev], rax
	mov [rsi+LargeObjectHeader.next], rax
	add rax, LargeObjectHeader.size
	ret
.panic:
	lea rsi, [rel OME_message_invalid_allocation]
	mov edx, OME_message_invalid_allocation.size
	jmp OME_panic

; rsi = panic message
; rdx = panic message length
OME_panic:
	mov edi, STDERR
	call OME_write
	mov edi, EXIT_FAILURE
	jmp OME_exit

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
	call OME_write
	ret

; rdi = traceback file_info
; rsi = traceback source_line
; rdx = (column << 16) | underline
OME_append_traceback:
	mov r8, [rbp+TC.traceback_pointer]
	lea rcx, [r8+TB.size]
	cmp rcx, rsp            ; check to make sure we don't overwrite stack
	ja .exit
	mov [rbp+TC.traceback_pointer], rcx
	mov [r8+TB.file_info], rdi
	mov [r8+TB.source_line], rsi
	mov [r8+TB.column], rdx
.exit:
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
	shl rdx, NUM_TAG_BITS
	sar rdx, NUM_TAG_BITS
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
constant_string OME_string_empty, ""
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

OME_vt100_red:
.str:	db 0x1b, "[31m"
.size equ $-.str

OME_vt100_clear:
.str:	db 0x1b, "[0m"
.size equ $-.str

OME_message_invalid_allocation:
.str:	db "Aborted: Invalid allocation request", 10
.size equ $-.str

OME_message_mmap_failed:
.str:	db "Aborted: mmap() failed", 10
.size equ $-.str

%if GC_DEBUG
OME_message_collect_nursery:
.str:	db "Running garbage collector..."
.size equ $-.str

OME_message_done:
.str:	db " done", 10
.size equ $-.str
%endif
'''

builtin_methods = [

BuiltInMethod('print:', constant_to_tag(Constant_BuiltIn), ['string'], '''\
	mov rdi, STDOUT
	jmp OME_print_value
'''),

BuiltInMethod('catch:', constant_to_tag(Constant_BuiltIn), ['do'], '''\
	mov rdi, rsi
	call OME_message_do__0
	mov rdi, [rbp+TC.call_stack_limit]
	mov [rbp+TC.traceback_pointer], rdi     ; reset traceback pointer
	unwrap_error rax                        ; clear error bit if present
	ret
'''),

BuiltInMethod('try:', constant_to_tag(Constant_BuiltIn), ['do', 'catch:'],'''\
	save rsi
	mov rdi, rsi
	call OME_message_do__0
	test rax, rax
	jns .exit
	mov rdi, [rbp+TC.call_stack_limit]
	mov [rbp+TC.traceback_pointer], rdi     ; reset traceback pointer
	unwrap_error rax                        ; clear error bit if present
	restore rdi
	mov rsi, rax
	jmp OME_message_catch__1
.exit:
	drop 1
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
	save rsi
	mov rdi, rsi
.loop:
	call OME_message_while__0
	mov rdi, [dsp-8]
	test rax, rax
	jz .exit                ; exit if |while| returned False
	js .exit                ; exit if |while| returned an error
	cmp rax, True           ; compare with True
	jne .type_error         ; if not True then we have a type error
	call OME_message_do__0
	mov rdi, [dsp-8]
	test rax, rax
	jns .loop               ; repeat if |do| did not return an error
.exit:
	drop 1
	ret
.type_error:
	drop 1
	jmp OME_type_error
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
	push rdi
	mov rdi, 3                      ; 3 slots = 24 bytes
	xor rsi, rsi
	call OME_allocate               ; pre-allocate string on heap
	mov rdi, rax
	pop r9
	untag_integer r9
	mov r11, rdi
	tag_pointer r11, Tag_String     ; tagged and ready for returning
	mov rsi, rsp                    ; rsi = string output cursor
	mov r8, rsp
	sub rsp, 16                     ; allocate temp stack space for string
	mov r10, 10                     ; divisor
	mov rax, r9                     ; number for division
	mov rdx, rax
	sar rdx, 63                     ; compute absolute value
	xor rax, rdx
	sub rax, rdx
.divloop:
	xor rdx, rdx            ; clear for division
	dec rsi                 ; next character
	idiv r10                ; divide by 10
	add dl, '0'             ; digit in remainder
	mov byte [rsi], dl      ; store digit
	test rax, rax           ; loop if not zero
	jnz .divloop
	test r9, r9
	jns .positive
	dec rsi
	mov byte [rsi], '-'     ; add sign
.positive:
	mov rcx, r8
	sub rcx, rsi            ; compute length
	mov dword [rdi], ecx    ; store length
	add rdi, 4
	rep movsb       ; copy from stack to allocated string
	mov rsp, r8     ; restore stack pointer
	mov rax, r11    ; tagged return value
	ret
'''),

BuiltInMethod('+', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	untag_integer rdi
	untag_integer rax
	add rax, rdi
	jmp OME_check_overflow
'''),

BuiltInMethod('-', Tag_Small_Integer, [], '''\
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

BuiltInMethod('×', Tag_Small_Integer, [], '''\
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

BuiltInMethod('power:', Tag_Small_Integer, [], '''\
	untag_integer rdi
	mov rax, rdi
	mov rcx, rsi
	untag_integer rcx
	get_tag rsi
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	test rcx, rcx
	jz .one
	js .zero
.loop:
	imul rdi
	mov r8, rax
	shl r8, NUM_TAG_BITS
	sar r8, NUM_TAG_BITS
	cmp r8, rax
	jne OME_overflow_error
	sub rcx, 1
	jnz .loop
	tag_integer rax
	ret
.zero:
	test rdi, rdi
	jz OME_divide_by_zero_error
	mov rax, OME_Value(0, Tag_Small_Integer)
	ret
.one:
	mov rax, OME_Value(1, Tag_Small_Integer)
	ret
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

BuiltInMethod('abs', Tag_Small_Integer, [], '''\
	untag_integer rdi
	mov rax, rdi
	sar rdi, 63
	xor rax, rdi
	sub rax, rdi
	tag_integer rax
	ret
'''),

BuiltInMethod('min:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rsi
	untag_integer rdi
	untag_integer rax
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	cmp rax, rdi
	cmovg rax, rdi
	tag_integer rax
	ret
'''),

BuiltInMethod('max:', Tag_Small_Integer, [], '''\
	mov rax, rsi
	get_tag rsi
	untag_integer rdi
	untag_integer rax
	cmp rsi, Tag_Small_Integer
	jne OME_type_error
	cmp rax, rdi
	cmovl rax, rdi
	tag_integer rax
	ret
'''),

BuiltInMethod('negate', Tag_Small_Integer, [], '''\
	mov rax, rdi
	untag_integer rax
	neg rax
	tag_integer rax
	ret
'''),

BuiltInMethod('==', Tag_Small_Integer, [], '''\
	xor rax, rax
	cmp rdi, rsi
	sete al
	ret
'''),

BuiltInMethod('≠', Tag_Small_Integer, [], '''\
	xor rax, rax
	cmp rdi, rsi
	setne al
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

BuiltInMethod('==', Tag_Boolean, [], '''\
	xor rax, rax
	cmp rdi, rsi
	sete al
	ret
'''),

BuiltInMethod('≠', Tag_Boolean, [], '''\
	xor rax, rax
	cmp rdi, rsi
	setne al
	ret
'''),

BuiltInMethod('then:', Tag_Boolean, ['do'], '''\
	mov rax, rdi
	mov rdi, rsi
	test rax, rax
	jnz OME_message_do__0
	ret
'''),

BuiltInMethod('else:', Tag_Boolean, ['do'], '''\
	mov rax, rdi
	mov rdi, rsi
	test rax, rax
	jz OME_message_do__0
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
	get_gc_object_size rax, rdi
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
	get_gc_object_size rcx, rdi
	cmp rsi, rcx                    ; check index
	jae OME_index_error
	mov rax, qword [rdi+rsi*8]
	ret
'''),

BuiltInMethod('each:', Tag_Array, ['item:'], '''\
	push rbx
	xor rbx, rbx
	untag_pointer rdi
	get_gc_object_size rax, rdi
	test rax, rax           ; check if zero
	jz .exit
	save rdi, rsi           ; save array and block
	mov rdx, rdi
	mov rdi, rsi
.loop:
	mov rsi, [rdx+rbx*8]
	call OME_message_item__1
	inc rbx
	test rax, rax           ; check for error
	js .exit
	mov rdi, [dsp-8]        ; load block
	mov rdx, [dsp-16]       ; load array pointer
	get_gc_object_size rax, rdx
	cmp rbx, rax
	jb .loop
.exit:
	xor rax, rax            ; return False
	drop 2
	pop rbx
	ret
'''),

BuiltInMethod('?make-string-buffer:', constant_to_tag(Constant_BuiltIn), [], '''\
	mov rdi, rsi
	get_tag rsi
	untag_integer rdi
	cmp esi, Tag_Small_Integer
	jne OME_type_error
	cmp rdi, MAX_SMALL_OBJECT_SIZE*8
	ja OME_overflow_error
	add rdi, 7                      ; convert bytes to qwords
	shr rdi, 3
	xor rsi, rsi
	call OME_allocate
	save rax
	mov edi, StringBuffer.size/8    ; allocate StringBuffer object
	mov esi, 2
	call OME_allocate_slots
	restore rdx
	mov [rax+StringBuffer.buffer], rdx
	tag_pointer rax, Tag_String_Buffer
	ret
'''),

BuiltInMethod('write:', Tag_String_Buffer, ['string'], '''\
	untag_pointer rdi
	mov rax, rsi
	get_tag rax
	cmp eax, Tag_String
	jne .notstring
.withstring:
	untag_pointer rsi
	mov rax, [rdi+StringBuffer.buffer]
	mov r8d, [rdi+StringBuffer.position]
	get_gc_object_size_bytes rdx, rax
	mov ecx, [rsi]          ; get string length
	test ecx, ecx
	jz .empty
	lea r9, [rcx+r8]        ; get size after write
	cmp r9, rdx             ; do we have enough space?
	ja .resize
.continue:
	xor r10, r10
	mov [rdi+StringBuffer.position], r9d
	mov [rdi+StringBuffer.cached_string], r10  ; invalidate cached string
	add rsi, 4
	lea rdi, [rax+r8]
	rep movsb
	mov rax, r9
.exit:
	tag_integer rax
	ret
.empty:
	mov rax, r8
	jmp .exit
.notstring:
	save rdi
	mov rdi, rsi
	call OME_message_string__0
	restore rdi
	mov rsi, rax
	get_tag rax
	cmp eax, Tag_String
	jne OME_type_error
	jmp .withstring
.resize:
	shl rdx, 1
	cmp rdx, MAX_LARGE_OBJECT_SIZE*8
	ja OME_overflow_error
	cmp r9, rdx
	ja .resize
	save rdi, rsi
	get_gc_object_size rcx, rax
	cmp ecx, MAX_SMALL_OBJECT_SIZE
	ja .resizelarge
	mov rdi, rdx
	add rdi, 7
	shr rdi, 3              ; convert bytes to qwords
	xor rsi, rsi
	call OME_allocate
	restore r10, r11
	mov rdi, rax
	mov rsi, [r10+StringBuffer.buffer]
	mov ecx, [r10+StringBuffer.position]
	mov r8, rcx
	add rcx, 7
	shr rcx, 3
	rep movsq
	mov rdi, r10
	mov rsi, r11
	mov [rdi+StringBuffer.buffer], rax
	mov ecx, [rsi]
	lea r9, [rcx+r8]
	jmp .continue
.resizelarge:
	mov rdi, rax
	mov rsi, rdx
	add rsi, 7
	shr rsi, 3
	call OME_resize
	restore rdi, rsi
	mov r8, [rdi+StringBuffer.position]
	mov [rdi+StringBuffer.buffer], rax
	mov ecx, [rsi]
	lea r9, [rcx+r8]
	jmp .continue
'''),

BuiltInMethod('string', Tag_String_Buffer, [], '''\
	mov r8, rdi
	untag_pointer r8
	mov rax, [r8+StringBuffer.cached_string]
	test rax, rax
	jnz .exit
	mov edi, [r8+StringBuffer.position]
	test edi, edi
	jz .empty
	save r8
	add rdi, 4+7            ; allocate string
	shr rdi, 3
	xor rsi, rsi
	call OME_allocate
	restore r8
	mov rsi, [r8+StringBuffer.buffer]
	mov ecx, [r8+StringBuffer.position]
	mov [rax], ecx          ; store length
	add rcx, 7
	shr rcx, 3
	lea rdi, [rax+4]
	rep movsq
	mov [r8+StringBuffer.cached_string], rax
.exit
	tag_pointer rax, Tag_String
	ret
.empty:
	lea rax, [rel OME_string_empty]
	jmp .exit
'''),

BuiltInMethod('clear', Tag_String_Buffer, [], '''\
	xor rcx, rcx
	untag_pointer rdi
	mov [rdi+StringBuffer.cached_string], rcx
	mov [rdi+StringBuffer.position], ecx
	ret
'''),

BuiltInMethod('size', Tag_String_Buffer, [], '''\
	untag_pointer rdi
	mov eax, [rdi+StringBuffer.position]
	tag_integer rax
	ret
'''),

BuiltInMethod('reserved-size', Tag_String_Buffer, [], '''\
	untag_pointer rdi
	mov rsi, [rdi+StringBuffer.buffer]
	get_gc_object_size_bytes rax, rsi
	tag_integer rax
	ret
'''),

]

def generate_builtins():
    for op, flag in [('<', 'l'), ('≤', 'le'), ('>', 'g'), ('≥', 'ge')]:
        builtin_methods.append(BuiltInMethod(op, Tag_Small_Integer, [], '''\
	xor rax, rax
	mov rdx, rsi
	get_tag rdx
	untag_integer rdi
	untag_integer rsi
	cmp rdx, Tag_Small_Integer
	jne OME_type_error
	cmp rdi, rsi
	set%s al
	ret
''' % flag))

generate_builtins()
