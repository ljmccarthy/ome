# ome - Object Message Expressions
# Copyright (c) 2015 Luke McCarthy <luke@iogopro.co.uk>. All rights reserved.

from ..ast import BuiltInMethod
from ..constants import *

class Target_x86_64(object):
    stack_pointer = 'rsp'
    context_pointer = 'rbp'
    nursery_bump_pointer = 'rbx'
    nursery_limit_pointer = 'r12'
    arg_registers = ('rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9')
    return_register = 'rax'
    temp_registers = ('r10', 'r11')

    define_constant_format = '%define {0} {1}\n'

    def __init__(self, emitter):
        self.emit = emitter
        self.num_jumpback_labels = 0
        self.num_traceback_labels = 0
        self.tracebacks = {}

    def emit_enter(self, num_stack_slots):
        if num_stack_slots > 0:
            self.emit('sub rsp, %s', num_stack_slots * 8)

    def emit_leave(self, num_stack_slots):
        self.emit.label('.exit')
        if num_stack_slots > 0:
            self.emit('add rsp, %s', num_stack_slots * 8)
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
            const_emit('add eax, 0x%x', MIN_CONSTANT_TAG)
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
            if ins.traceback_info.id in self.tracebacks:
                traceback_label = self.tracebacks[ins.traceback_info.id]
            else:
                traceback_label = '.traceback_%d' % self.num_traceback_labels
                self.num_traceback_labels += 1
                self.tracebacks[ins.traceback_info.id] = traceback_label
                tb_emit = self.emit.tail_emitter(traceback_label)
                tb_emit('lea rdi, [rel %s]', ins.traceback_info.file_info)
                tb_emit('lea rsi, [rel %s]', ins.traceback_info.source_line)
                tb_emit('mov rdx, %s', (ins.traceback_info.column << 16) | ins.traceback_info.underline)
                tb_emit('call OME_append_traceback')
                tb_emit('jmp .exit')
        else:
            traceback_label = '.exit'

        self.emit('call %s', ins.call_label)
        if ins.num_stack_args > 0:
            self.emit('add rsp, %s', ins.num_stack_args * 8)
        self.emit('test rax, rax')
        self.emit('js %s', traceback_label)

    def emit_tag(self, reg, tag):
        self.emit('shl %s, %s', reg, NUM_TAG_BITS)
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
        self.emit('shr %s, %s', ins.dest, NUM_TAG_BITS)

    def LOAD_VALUE(self, ins):
        value = encode_tagged_value(ins.value, ins.tag)
        if value == 0:
            self.emit('xor %s, %s', ins.dest, ins.dest)
        else:
            self.emit('mov %s, 0x%x', ins.dest, value)

    def LOAD_LABEL(self, ins):
        self.emit('lea %s, [rel %s]', ins.dest, ins.label)
        self.emit_tag(ins.dest, ins.tag)

    def GET_SLOT(self, ins):
        self.emit('mov %s, [%s+%s]', ins.dest, ins.object, ins.slot_index * 8)

    def SET_SLOT(self, ins):
        self.emit('mov [%s+%s], %s', ins.object, ins.slot_index * 8, ins.value)

builtin_macros = '''
%define GC_DEBUG      0
%define PAGE_SIZE     0x1000
%define STACK_SIZE    0x1000
%define NURSERY_SIZE  0x3800

%define OME_Value(value, tag) (((tag) << NUM_DATA_BITS) | (value))
%define OME_Constant(value) OME_Value(value, Tag_Constant)
%define OME_Error_Tag(tag) ((tag) | (1 << (NUM_TAG_BITS - 1)))
%define OME_Error_Constant(value) OME_Value(value, OME_Error_Tag(Tag_Constant))

%define False OME_Value(0, Tag_Boolean)
%define True OME_Value(1, Tag_Boolean)

; Thread context structure
%define TC_stack_limit 0
%define TC_traceback_pointer 8
%define TC_nursery_base_pointer 16
%define TC_SIZE 24

; Traceback entry structure
%define TB_file_info 0
%define TB_source_line 8
%define TB_column 16
%define TB_SIZE 24

%macro get_gc_object_size 2
	mov %1, [%2-8]
	shr %1, 1
	and %1, GC_SIZE_MASK
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
	lea rsp, [rax+STACK_SIZE-TC_SIZE]       ; stack pointer (grows down)
	mov rbp, rsp                            ; thread context pointer
	lea rbx, [rsp+TC_SIZE]                  ; GC nursery pointer (grows up)
	lea r12, [rbx+NURSERY_SIZE]             ; GC nursery limit
	mov [rbp+TC_stack_limit], rax
	mov [rbp+TC_traceback_pointer], rax
	mov [rbp+TC_nursery_base_pointer], rbx
	call OME_toplevel       ; create top-level block
	mov rdi, rax
	call OME_main           ; call main method on top-level block
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
	sub r14, TB_SIZE
	cmp r14, r13
	jb .failure
	lea rsi, [rel OME_message_traceback]
	mov rdx, OME_message_traceback.size
	mov rdi, STDERR
	call OME_write
.tbloop:
	; file and line info
	mov rsi, [r14+TB_file_info]
	mov edx, dword [rsi]
	add rsi, 4
	mov rdi, STDERR
	call OME_write
	; source code line
	mov rsi, [r14+TB_source_line]
	mov edx, dword [rsi]
	add rsi, 4
	mov rdi, STDERR
	call OME_write
	; red squiggle underline
	mov rcx, [r14+TB_column]
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
	mov rcx, OME_vt100_red.size
	rep movsb               ; VT100 red
	mov rcx, rdx
	mov al, '^'             ; squiggles
	rep stosb
	lea rsi, [rel OME_vt100_clear]
	mov rcx, OME_vt100_clear.size
	rep movsb               ; VT100 clear
	mov rsi, rsp
	mov rdx, r15
	mov rdi, STDERR
	call OME_write
	add rsp, r15
	sub r14, TB_SIZE
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
	jmp OME_exit
.newline:
	lea rsi, [rel OME_message_traceback]
	mov rdx, 1
	mov rdi, STDERR
	jmp OME_write

align 16
; rdi = number of slots
OME_allocate:
	mov rax, rbx
	lea rbx, [rbx+rdi*8+8]  ; add object size to bump pointer
	cmp rbx, r12            ; check if beyond limit
	jae .full
	mov rcx, 1              ; object header present bit
	shl rdi, 1
	or rcx, rdi             ; total number of slots
	shl rdi, GC_SIZE_BITS
	or rcx, rdi             ; number of slots to scan
	mov [rax], rcx          ; store header
	add rax, 8              ; return address after header
	ret
.full:
	mov rbx, rdi            ; save number of slots argument
%if GC_DEBUG
	; print debug message
	lea rsi, [rel OME_message_collect_nursery]
	mov rdx, OME_message_collect_nursery.size
	mov rdi, STDERR
	call OME_write
%endif
	mov r10, [rbp+TC_nursery_base_pointer]
	lea rdi, [rbp+TC_SIZE]          ; space 1 is just after the TC data
	cmp rdi, r10
	jne .space1
	add rdi, NURSERY_SIZE           ; space 2 is after space 1
.space1:
	mov [rbp+TC_nursery_base_pointer], rdi
	mov r8, rsp
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
	cmp rsi, r12
	jae .stacknext
	mov rcx, [rsi-8]        ; get header or forwarding pointer
	test rcx, 1
	jz .stackforward
	mov [rdi], rcx          ; store header in to-space
	add rdi, 8
	mov [rsi-8], rdi        ; store forwarding pointer
	mov r11, rdi
	tag_pointer r11, rax
	mov [r8], r11           ; store new pointer to stack
	shr rcx, 1              ; get object size
	and rcx, GC_SIZE_MASK
	test rcx, rcx           ; sanity check object size is not 0
	jz .stacknext
	rep movsq               ; copy object
	jmp .stacknext
.stackforward:
	tag_pointer rcx, rax    ; store forwarded pointer to stack
	mov [r8], rcx
.stacknext:
	add r8, 8
	cmp r8, rbp
	jb .stackloop
	; now scan objects in to space
	mov r8, [rbp+TC_nursery_base_pointer]
	jmp .tospacenext
.tospaceloop:
	mov rdx, [r8]
	add r8, 8
	mov rcx, rdx
	shr rcx, GC_SIZE_BITS + 1       ; get number of fields to scan
	and rcx, GC_SIZE_MASK
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
	cmp rsi, r12
	jae .fieldnext
	mov rcx, [rsi-8]        ; get header or forwarding pointer
	test rcx, 1
	jz .fieldforward
	mov [rdi], rcx          ; store header in to-space
	add rdi, 8
	mov [rsi-8], rdi        ; store forwarding pointer
	mov r11, rdi
	tag_pointer r11, rax
	mov [r8], r11           ; store new pointer to field
	shr rcx, 1              ; get object size
	and rcx, GC_SIZE_MASK
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
	shr rdx, GC_SIZE_BITS + 1       ; get number of fields to scan
	and rdx, GC_SIZE_MASK
	sub rcx, rdx
	lea r8, [r8+rcx*8]              ; add to end pointer
.tospacenext:
	cmp r8, rdi
	jb .tospaceloop
	mov r12, [rbp+TC_nursery_base_pointer]
	add r12, NURSERY_SIZE   ; set GC nursery limit
	mov r8, rbx             ; save number of slots argument to r8
	mov rbx, rdi            ; set GC nursery pointer
	; clear unused area
	xor rax, rax
	mov rcx, r12
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
	mov rdx, OME_message_done.size
	mov rdi, STDERR
	call OME_write
%endif
	mov rdi, r8             ; restore number of slots argument
	jmp OME_allocate

OME_panic:
	mov rdi, STDERR
	call OME_write
	mov rdi, 1
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
	mov r8, [rbp+TC_traceback_pointer]
	lea rcx, [r8+TB_SIZE]
	cmp rcx, rsp            ; check to make sure we don't overwrite stack
	ja .exit
	mov [rbp+TC_traceback_pointer], rcx
	mov [r8+TB_file_info], rdi
	mov [r8+TB_source_line], rsi
	mov [r8+TB_column], rdx
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

OME_message_mmap_failed:
.str:	db "Aborted: Failed to allocate thread context", 10
.size equ $-.str

OME_message_collect_nursery:
.str:	db "Running garbage collector..."
.size equ $-.str

OME_message_done:
.str:	db " done", 10
.size equ $-.str
'''

builtin_methods = [

BuiltInMethod('print:', constant_to_tag(Constant_BuiltIn), ['string'], '''\
	mov rdi, STDOUT
	jmp OME_print_value
'''),

BuiltInMethod('catch:', constant_to_tag(Constant_BuiltIn), ['do'], '''\
	mov rdi, rsi
	call OME_message_do__0
	mov rdi, [rbp+TC_stack_limit]
	mov [rbp+TC_traceback_pointer], rdi     ; reset traceback pointer
	shl rax, 1                              ; clear error bit if present
	shr rax, 1
	ret
'''),

BuiltInMethod('try:', constant_to_tag(Constant_BuiltIn), ['do', 'catch:'],'''\
	sub rsp, 8
	mov [rsp], rsi
	mov rdi, rsi
	call OME_message_do__0
	test rax, rax
	jns .exit
	mov rdi, [rbp+TC_stack_limit]
	mov [rbp+TC_traceback_pointer], rdi     ; reset traceback pointer
	shl rax, 1                              ; clear error bit if present
	shr rax, 1
	mov rdi, [rsp]
	mov rsi, rax
	add rsp, 8
	jmp OME_message_catch__1
.exit:
	add rsp, 8
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
	push rsi
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
	add rsp, 8
	ret
.type_error:
	add rsp, 8
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
	sub rsp, 32
	mov [rsp+24], rdi       ; save tagged pointer for GC
	untag_pointer rdi
	get_gc_object_size rcx, rdi
	test rcx, rcx           ; check if zero
	jz .exit
	lea rcx, [rdi+rcx*8]    ; end of array
	mov [rsp], rdi          ; save array pointer
	mov [rsp+8], rcx        ; save end pointer
	mov [rsp+16], rsi       ; save block
	mov rdx, rdi
	mov rdi, rsi
.loop:
	mov rsi, [rdx]
	call OME_message_item__1
	test rax, rax           ; check for error
	js .exit
	mov rdx, [rsp]          ; load array pointer
	mov rcx, [rsp+8]        ; load end pointer
	mov rdi, [rsp+16]       ; load block
	add rdx, 8
	mov [rsp], rdx
	cmp rdx, rcx
	jb .loop
.exit:
	xor rax, rax            ; return False
	add rsp, 32
	ret
''')

]
