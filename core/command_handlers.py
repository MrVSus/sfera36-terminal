# core/command_handlers.py

class CommandHandlers:

    def __init__(self, cpu):
        self.cpu = cpu

        # Карты опкодов
        self.opcodes_two_addr = {
            '01': self._op_mov,
            '11': self._op_movb,
            '02': self._op_cmp,
            '12': self._op_cmpb,
            '03': self._op_bit,
            '13': self._op_bitb,
            '04': self._op_bic,
            '14': self._op_bicb,
            '05': self._op_bis,
            '15': self._op_bisb,
            '06': self._op_add,
            '16': self._op_sub,
        }

        self.opcodes_one_addr = {
            '050': self._op_clr,
            '051': self._op_com,
            '052': self._op_inc,
            '053': self._op_dec,
            '054': self._op_neg,
            '057': self._op_tst,
            '062': self._op_asr,
            '063': self._op_asl,
        }

    # ------------------ ВСПОМОГАТЕЛЬНОЕ: парсинг слова ------------------

    def _parse_two_addr(self, raw_word: str):
        # D0..D5 — символы '0'..'7'
        D = raw_word
        size_is_word = (D[0] == '0')
        op2 = D[0:2]                  # '01','11',..
        src_mode = int(D[2], 8)
        src_reg  = int(D[3], 8)
        dst_mode = int(D[4], 8)
        dst_reg  = int(D[5], 8)
        return size_is_word, op2, src_mode, src_reg, dst_mode, dst_reg

    def _parse_one_addr(self, raw_word: str):
        D = raw_word
        size_is_word = (D[0] == '0')
        op3 = D[1:4]                  # '050','051',...
        mode = int(D[4], 8)
        reg  = int(D[5], 8)
        return size_is_word, op3, mode, reg

    # ------------------ ФЛАГИ ------------------

    def _upd_flags_nz(self, value: int, is_word: bool):
        mask = 0xFFFF if is_word else 0xFF
        sign = 0x8000 if is_word else 0x80
        v = value & mask
        self.cpu.flags.N = 1 if (v & sign) else 0
        self.cpu.flags.Z = 1 if v == 0 else 0

    def _upd_flags_nzc(self, value: int, is_word: bool, carry: int | None):
        self._upd_flags_nz(value, is_word)
        if carry is not None:
            self.cpu.flags.C = 1 if carry else 0

    # ------------------ ДВУАДРЕСНЫЕ ------------------

    def _two_addr_common(self, raw_word: str, pc: int):
        is_word, op2, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        # Источник
        s_val, _s_w, s_ex = self.cpu.resolve_operand(
            is_word=is_word, mode=s_mode, reg=s_reg, pc=pc, as_dest=False
        )
        # Приёмник (учитываем слова источника!)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        _d_val, d_w, d_ex = self.cpu.resolve_operand(
            is_word=is_word, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=True
        )
        return is_word, op2, s_val, d_w, (s_ex + d_ex)

    def _op_mov(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        if d_w: d_w(s_val)
        self._upd_flags_nz(s_val, True)
        return "MOV", extra

    def _op_movb(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        # для MOVB is_word=False
        if d_w: d_w(s_val & 0xFF)
        self._upd_flags_nz(s_val, False)
        return "MOVB", extra

    def _op_add(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        # Для add нужен d_val, но адресация уже отработала (декремент/инкремент выполнены).
        # Возьмем фактическое место назначения ещё раз для чтения:
        # Трюк: повторим адресацию приёмника как источник (as_dest=False) с тем же d_pc.
        is_word2, op2, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        d_pc = (pc + (extra - 0) * 2) & 0xFFFF  # грубо: в этом простом варианте повторно считаем ниже
        # Правильнее — заново вычислить (s_ex) и затем d_pc, как в _two_addr_common:
        # Пересчёт:
        s_val2, _, s_ex = self.cpu.resolve_operand(is_word=is_word2, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, _dex = self.cpu.resolve_operand(is_word=True, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)

        res = (d_val + (s_val & 0xFFFF)) & 0xFFFF
        carry = 1 if (d_val + (s_val & 0xFFFF)) > 0xFFFF else 0
        if d_w: d_w(res)
        self._upd_flags_nzc(res, True, carry)
        return "ADD", s_ex + _dex

    def _op_sub(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        is_word2, op2, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val2, _, s_ex = self.cpu.resolve_operand(is_word=is_word2, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=True, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)

        res = (d_val - (s_val & 0xFFFF)) & 0xFFFF
        carry = 1 if d_val < (s_val & 0xFFFF) else 0
        if d_w: d_w(res)
        self._upd_flags_nzc(res, True, carry)
        return "SUB", s_ex + d_ex

    def _op_cmp(self, raw_word: str, pc: int):
        is_word, _, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val, _sw, s_ex = self.cpu.resolve_operand(is_word=True, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=True, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)
        res = (d_val - s_val) & 0xFFFF
        carry = 1 if d_val < s_val else 0
        self._upd_flags_nzc(res, True, carry)
        return "CMP", s_ex + d_ex

    def _op_cmpb(self, raw_word: str, pc: int):
        is_word, _, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val, _sw, s_ex = self.cpu.resolve_operand(is_word=False, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=False, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)
        res = ((d_val & 0xFF) - (s_val & 0xFF)) & 0xFF
        carry = 1 if (d_val & 0xFF) < (s_val & 0xFF) else 0
        self._upd_flags_nzc(res, False, carry)
        return "CMPB", s_ex + d_ex

    def _op_bit(self, raw_word: str, pc: int):
        is_word, _, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val, _sw, s_ex = self.cpu.resolve_operand(is_word=True, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=True, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)
        res = d_val & s_val
        self._upd_flags_nz(res, True)
        return "BIT", s_ex + d_ex

    def _op_bitb(self, raw_word: str, pc: int):
        is_word, _, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val, _sw, s_ex = self.cpu.resolve_operand(is_word=False, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=False, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)
        res = (d_val & s_val) & 0xFF
        self._upd_flags_nz(res, False)
        return "BITB", s_ex + d_ex

    def _op_bic(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        # заново получим d_val для флага:
        is_word2, op2, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val2, _sw, s_ex = self.cpu.resolve_operand(is_word=True, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=True, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)

        res = d_val & (~s_val)
        if d_w: d_w(res & 0xFFFF)
        self._upd_flags_nz(res, True)
        return "BIC", s_ex + d_ex

    def _op_bicb(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        is_word2, op2, s_mode, s_reg, d_mode, d_reg = self._parse_two_addr(raw_word)
        s_val2, _sw, s_ex = self.cpu.resolve_operand(is_word=False, mode=s_mode, reg=s_reg, pc=pc, as_dest=False)
        d_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, _dw, d_ex = self.cpu.resolve_operand(is_word=False, mode=d_mode, reg=d_reg, pc=d_pc, as_dest=False)

        res = (d_val & (~s_val)) & 0xFF
        if d_w: d_w(res)
        self._upd_flags_nz(res, False)
        return "BICB", s_ex + d_ex

    def _op_bis(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        if d_w: d_w((s_val) & 0xFFFF)
        self._upd_flags_nz(s_val, True)
        return "BIS", extra

    def _op_bisb(self, raw_word: str, pc: int):
        is_word, _, s_val, d_w, extra = self._two_addr_common(raw_word, pc)
        if d_w: d_w(s_val & 0xFF)
        self._upd_flags_nz(s_val, False)
        return "BISB", extra

    # ------------------ ОДНОАДРЕСНЫЕ ------------------

    def _one_addr_common(self, raw_word: str, pc: int, for_write: bool):
        is_word, op3, mode, reg = self._parse_one_addr(raw_word)
        val, wb, extra = self.cpu.resolve_operand(
            is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=for_write
        )
        return is_word, op3, val, wb, extra

    def _op_clr(self, raw_word: str, pc: int):
        is_word, _, _val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("CLR требует адрес для записи")
        wb(0)
        self._upd_flags_nzc(0, is_word, carry=0)
        return "CLR", extra

    def _op_com(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("COM требует адрес для записи")
        mask = 0xFFFF if is_word else 0xFF
        res = (~val) & mask
        wb(res)
        # PDP-11: C=1 для COM
        self._upd_flags_nzc(res, is_word, carry=1)
        return "COM", extra

    def _op_inc(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("INC требует адрес для записи")
        mask = 0xFFFF if is_word else 0xFF
        res = (val + 1) & mask
        carry = 1 if res == 0 else 0
        wb(res)
        self._upd_flags_nzc(res, is_word, carry)
        return "INC", extra

    def _op_dec(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("DEC требует адрес для записи")
        mask = 0xFFFF if is_word else 0xFF
        res = (val - 1) & mask
        carry = 1 if res == mask else 0
        wb(res)
        self._upd_flags_nzc(res, is_word, carry)
        return "DEC", extra

    def _op_neg(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("NEG требует адрес для записи")
        mask = 0xFFFF if is_word else 0xFF
        res = (-val) & mask
        carry = 1 if val != 0 else 0
        wb(res)
        self._upd_flags_nzc(res, is_word, carry)
        return "NEG", extra

    def _op_tst(self, raw_word: str, pc: int):
        is_word, _, val, _wb, extra = self._one_addr_common(raw_word, pc, False)
        self._upd_flags_nz(val, is_word)
        return "TST", extra

    def _op_asr(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("ASR требует адрес для записи")
        if is_word:
            carry = val & 1
            res = ((val >> 1) | (val & 0x8000)) & 0xFFFF
        else:
            carry = val & 1
            res = ((val >> 1) | (val & 0x80)) & 0xFF
        wb(res)
        self._upd_flags_nzc(res, is_word, carry)
        return "ASR", extra

    def _op_asl(self, raw_word: str, pc: int):
        is_word, _, val, wb, extra = self._one_addr_common(raw_word, pc, True)
        if not wb: raise ValueError("ASL требует адрес для записи")
        if is_word:
            carry = 1 if (val & 0x8000) else 0
            res = (val << 1) & 0xFFFF
        else:
            carry = 1 if (val & 0x80) else 0
            res = (val << 1) & 0xFF
        wb(res)
        self._upd_flags_nzc(res, is_word, carry)
        return "ASL", extra

    # ------------------ ДИСПЕТЧЕР ------------------

    def execute(self, *, opcode: str, word_byte: str, addr_tail, pc: int, raw_word: str):
        """
        Универсальный вход для CPU._run_program.
        Мы не полагаемся на переданный opcode, а распознаём сами из raw_word.
        """
        D0D1 = raw_word[:2]
        if D0D1 in self.opcodes_two_addr:
            # двухадресная
            return self.opcodes_two_addr[D0D1](raw_word, pc)

        # одноадресная
        _is_word, op3, _mode, _reg = self._parse_one_addr(raw_word)
        if op3 in self.opcodes_one_addr:
            return self.opcodes_one_addr[op3](raw_word, pc)

        # неизвестно — считаем, что доп. слов нет
        return f"Неизвестная команда {raw_word}", 0
