# core/command_handlers.py

class CommandHandlers:
    """
    Обработчики одноадресных и двухадресных команд “Сферы-36”.
    Все хендлеры возвращают (message: str, extra_words: int).
    extra_words — суммарное количество ДОП. слов (16 бит), съеденных обоими операндами.
    """
    def __init__(self, cpu):
        self.cpu = cpu

        # Одноадресные по 3-значному коду (X[1:4])
        self.opcodes_one_addr = {
            '050': self.handle_clr,
            '051': self.handle_com,
            '052': self.handle_inc,
            '053': self.handle_dec,
            '054': self.handle_neg,
            '057': self.handle_tst,
            '062': self.handle_asr,
            '063': self.handle_asl,
        }

        # Двухадресные — по первым двум цифрам слова (X[:2])
        self.opcodes_two_addr = {
            '01': self.handle_mov,
            '11': self.handle_movb,
            '02': self.handle_cmp,
            '12': self.handle_cmpb,
            '03': self.handle_bit,
            '13': self.handle_bitb,
            '04': self.handle_bic,
            '14': self.handle_bicb,
            '05': self.handle_bis,
            '15': self.handle_bisb,
            '06': self.handle_add,
            '16': self.handle_sub,
        }

    # ---------- helpers ----------
    def _validate_reg_not_r7(self, reg_num: int, addr_mode: int):
        # запрещаем модифицировать R7 прямым регистром (mode 0) для команд записи
        if reg_num == 7 and addr_mode == 0:
            raise ValueError("Регистр R7 нельзя использовать как приёмник в режиме 0")

    def _update_flags(self, value: int, is_word: bool, carry: int | None = None):
        mask = 0xFFFF if is_word else 0xFF
        sign_bit = 15 if is_word else 7
        v = value & mask
        self.cpu.flags.N = (v >> sign_bit) & 1
        self.cpu.flags.Z = 1 if v == 0 else 0
        if carry is not None:
            self.cpu.flags.C = 1 if carry else 0

    def _fmt_word(self, v: int) -> str:
        return self.cpu._int_to_oct6(v)

    def _fmt_byte(self, v: int) -> str:
        return f"{v & 0xFF:03o}"

    def _wb_union(self, s_extra: int, d_extra: int) -> int:
        return (s_extra or 0) + (d_extra or 0)

    # ---------- одноадресные ----------
    def handle_clr(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        _val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        write_back(0)
        self._update_flags(0, is_word, carry=0)
        return ("CLR -> " + (self._fmt_word(0) if is_word else self._fmt_byte(0))), extra

    def handle_com(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        mask = 0xFFFF if is_word else 0xFF
        new = (~val) & mask
        write_back(new)
        self._update_flags(new, is_word, carry=1)
        msg = ("COM: " if is_word else "COMB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    def handle_inc(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        mask = 0xFFFF if is_word else 0xFF
        new = (val + 1) & mask
        carry = 1 if new == 0 else 0
        write_back(new)
        self._update_flags(new, is_word, carry)
        msg = ("INC: " if is_word else "INCB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    def handle_dec(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        mask = 0xFFFF if is_word else 0xFF
        new = (val - 1) & mask
        carry = 1 if new == mask else 0
        write_back(new)
        self._update_flags(new, is_word, carry)
        msg = ("DEC: " if is_word else "DECB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    def handle_neg(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        mask = 0xFFFF if is_word else 0xFF
        new = (-val) & mask
        carry = 1 if val != 0 else 0
        write_back(new)
        self._update_flags(new, is_word, carry)
        msg = ("NEG: " if is_word else "NEGB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    def handle_tst(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        val, _wb, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=False
        )
        self._update_flags(val, is_word, carry=None)
        msg = ("TST: " if is_word else "TSTB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val))
        return msg, extra

    def handle_asr(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        if is_word:
            carry = val & 1
            new = ((val >> 1) | (val & 0x8000)) & 0xFFFF
        else:
            carry = val & 1
            new = ((val >> 1) | (val & 0x80)) & 0xFF
        write_back(new)
        self._update_flags(new, is_word, carry)
        msg = ("ASR: " if is_word else "ASRB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    def handle_asl(self, word_byte, addr_mode, reg_num, pc):
        is_word = (word_byte == '0')
        self._validate_reg_not_r7(reg_num, addr_mode)
        val, write_back, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=addr_mode, reg=reg_num, pc=pc, as_dest=True
        )
        if is_word:
            carry = 1 if (val & 0x8000) else 0
            new = (val << 1) & 0xFFFF
        else:
            carry = 1 if (val & 0x80) else 0
            new = (val << 1) & 0xFF
        write_back(new)
        self._update_flags(new, is_word, carry)
        msg = ("ASL: " if is_word else "ASLB: ") + \
              (self._fmt_word(val) if is_word else self._fmt_byte(val)) + " -> " + \
              (self._fmt_word(new) if is_word else self._fmt_byte(new))
        return msg, extra

    # ---------- двухадресные ----------
    def handle_mov(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        d_w(s_val)
        self._update_flags(s_val, True, carry=None)
        return f"MOV: {self._fmt_word(s_val)} -> dest", self._wb_union(s_ex, d_ex)

    def handle_movb(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=False, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=False, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        d_w(s_val)
        self._update_flags(s_val, False, carry=None)
        return f"MOVB: {self._fmt_byte(s_val)} -> dest", self._wb_union(s_ex, d_ex)

    def handle_add(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = (d_val + s_val) & 0xFFFF
        carry = 1 if (d_val + s_val) > 0xFFFF else 0
        d_w(res)
        self._update_flags(res, True, carry)
        return f"ADD: {self._fmt_word(d_val)} + {self._fmt_word(s_val)} -> {self._fmt_word(res)}", self._wb_union(s_ex, d_ex)

    def handle_sub(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = (d_val - s_val) & 0xFFFF
        carry = 1 if d_val < s_val else 0
        d_w(res)
        self._update_flags(res, True, carry)
        return f"SUB: {self._fmt_word(d_val)} - {self._fmt_word(s_val)} -> {self._fmt_word(res)}", self._wb_union(s_ex, d_ex)

    def handle_cmp(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, _dw,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=False
        )
        res = (d_val - s_val) & 0xFFFF
        carry = 1 if d_val < s_val else 0
        self._update_flags(res, True, carry)
        return f"CMP: {self._fmt_word(d_val)} ? {self._fmt_word(s_val)}", self._wb_union(s_ex, d_ex)

    def handle_cmpb(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=False, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, _dw,  d_ex = self.cpu.resolve_operand(
            is_word=False, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=False
        )
        res = (d_val - s_val) & 0xFF
        carry = 1 if (d_val & 0xFF) < (s_val & 0xFF) else 0
        self._update_flags(res, False, carry)
        return f"CMPB: {self._fmt_byte(d_val)} ? {self._fmt_byte(s_val)}", self._wb_union(s_ex, d_ex)

    def handle_bit(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, _dw,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=False
        )
        res = d_val & s_val
        self._update_flags(res, True, carry=None)
        return f"BIT: {self._fmt_word(d_val)} & {self._fmt_word(s_val)}", self._wb_union(s_ex, d_ex)

    def handle_bitb(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=False, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, _dw,  d_ex = self.cpu.resolve_operand(
            is_word=False, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=False
        )
        res = (d_val & s_val) & 0xFF
        self._update_flags(res, False, carry=None)
        return f"BITB: {self._fmt_byte(d_val)} & {self._fmt_byte(s_val)}", self._wb_union(s_ex, d_ex)

    def handle_bic(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = d_val & (~s_val)
        d_w(res)
        self._update_flags(res, True, carry=None)
        return f"BIC: {self._fmt_word(d_val)} & ~{self._fmt_word(s_val)} -> {self._fmt_word(res)}", self._wb_union(s_ex, d_ex)

    def handle_bicb(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=False, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=False, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = (d_val & (~s_val)) & 0xFF
        d_w(res)
        self._update_flags(res, False, carry=None)
        return f"BICB: {self._fmt_byte(d_val)} & ~{self._fmt_byte(s_val)} -> {self._fmt_byte(res)}", self._wb_union(s_ex, d_ex)

    def handle_bis(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=True, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=True, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = d_val | s_val
        d_w(res)
        self._update_flags(res, True, carry=None)
        return f"BIS: {self._fmt_word(d_val)} | {self._fmt_word(s_val)} -> {self._fmt_word(res)}", self._wb_union(s_ex, d_ex)

    def handle_bisb(self, _wb, src_mode, src_reg, dst_mode, dst_reg, pc):
        s_val, _sw, s_ex = self.cpu.resolve_operand(
            is_word=False, mode=src_mode, reg=src_reg, pc=pc, as_dest=False
        )
        d_val, d_w,  d_ex = self.cpu.resolve_operand(
            is_word=False, mode=dst_mode, reg=dst_reg, pc=pc + (s_ex * 2), as_dest=True
        )
        res = (d_val | s_val) & 0xFF
        d_w(res)
        self._update_flags(res, False, carry=None)
        return f"BISB: {self._fmt_byte(d_val)} | {self._fmt_byte(s_val)} -> {self._fmt_byte(res)}", self._wb_union(s_ex, d_ex)

    # ---------- универсальный вызов ----------
    def execute(self, *, opcode, word_byte, addr_tail, pc, raw_word):
        """
        ВАЖНО: сначала пробуем ДВУХАДРЕСНЫЕ (по X[:2]),
        только если не подошло — проверяем одноадресные (по X[1:4]).
        Так мы корректно распознаём MOV/MOVB и т.п.
        """
        # 1) двухадресные
        key2 = raw_word[:2]
        if key2 in self.opcodes_two_addr:
            handler = self.opcodes_two_addr[key2]
            src_mode = int(raw_word[2], 8)
            src_reg  = int(raw_word[3], 8)
            dst_mode = int(raw_word[4], 8)
            dst_reg  = int(raw_word[5], 8)
            msg, extra = handler(word_byte, src_mode, src_reg, dst_mode, dst_reg, pc)
            return msg, extra

        # 2) одноадресные
        if opcode in self.opcodes_one_addr:
            handler = self.opcodes_one_addr[opcode]
            addr_mode = int(addr_tail[0], 8)
            reg_num   = int(addr_tail[1], 8)
            msg, extra = handler(word_byte, addr_mode, reg_num, pc)
            return msg, extra

        raise ValueError(f"Неизвестный код операции: {opcode} ({raw_word})")
