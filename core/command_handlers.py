class CommandHandlers:

    def __init__(self, cpu):
        self.cpu = cpu
        self._one = {
            '050': self.op_clr,
            '051': self.op_com,
            '052': self.op_inc,
            '053': self.op_dec,
            '054': self.op_neg,
            '057': self.op_tst,
            '067': self.op_mfps,   
            '064': self.op_mtps,   

        }
        self._branch = {
            0o000400: self.op_br,   # BR offset
            0o001000: self.op_bne,  # BNE offset
            0o001400: self.op_beq,  # BEQ offset
            0o010000: self.op_bpl,  # BPL offset
            0o010400: self.op_bmi,  # BMI offset
            0o000100: self.op_jmp,  # JMP <dst>
        }       
    
        self._two = {
            0o01: self.op_mov,   
            0o11: self.op_movb,  
            0o06: self.op_add,
            0o16: self.op_sub,
        }

    # ---------- Диспетчер ----------
    def execute(self, *, pc: int, raw_word: str):
        raw = str(raw_word).zfill(6)

        try:
            word = int(raw, 8)
        except Exception:
            return (f"UNKNOWN {raw}", 0)

        opcode_high = (word >> 12) & 0o17

        # --- двухоперандные ---
        if opcode_high in self._two:
            src_mode = (word >> 9) & 0o7
            src_reg  = (word >> 6) & 0o7
            dst_mode = (word >> 3) & 0o7
            dst_reg  = word & 0o7
            handler = self._two[opcode_high]
            return handler(pc, f"{raw[:2]}", src_mode, src_reg, dst_mode, dst_reg, raw)

        # --- однооперандные ---
        op3 = raw[1:4]
        if op3 in self._one:
            wb_flag = raw[0]
            mode    = int(raw[4], 8)
            reg     = int(raw[5], 8)
            return self._one[op3](pc, wb_flag, mode, reg, raw)

        # --- Ветвления ---
        opcode8 = (word >> 8) & 0xFF
        offset  = word & 0xFF
        if 0o0400 <= word <= 0o0777:
            return self.op_br(pc, word)
        elif 0o001000 <= word <= 0o001377:
            return self.op_bne(pc, word)
        elif 0o001400 <= word <= 0o001777:
            return self.op_beq(pc, word)
        elif 0o100000 <= word <= 0o100377:
            return self.op_bpl(pc, word)
        elif 0o100400 <= word <= 0o100777:
            return self.op_bmi(pc, word)
        elif 0o0100 <= word <= 0o0177:
            return self.op_jmp(pc, word)

        return (f"UNKNOWN {raw}", 0)




    # ---------- Декодеры ----------
    def decode_src(self, is_word: bool, pc: int, mode: int, reg: int):
        val, wb, extra, ea = self.cpu.resolve_operand(
            is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=False
        )
        return val, wb, extra, ea

    def decode_dst(self, is_word: bool, pc: int, mode: int, reg: int):
        val, wb, extra, ea = self.cpu.resolve_operand(
            is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True
        )
        return val, wb, extra, ea

    # ---------- Флаги ----------
    def _set_nz(self, value: int, is_word: bool):
        mask = 0xFFFF if is_word else 0xFF
        sign_bit = 15 if is_word else 7
        v = value & mask
        n = (v >> sign_bit) & 1
        z = 1 if v == 0 else 0
        self.cpu._set_flag("N", n)
        self.cpu._set_flag("Z", z)

    # ---------- CLR / CLRB ----------
    def op_clr(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        _, wb, extra, _ = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        wb(0)
        self.cpu._set_flag("N", 0)
        self.cpu._set_flag("Z", 1)
        self.cpu._set_flag("V", 0)
        self.cpu._set_flag("C", 0)
        return ("CLR" if is_word else "CLRB"), extra

    # ---------- COM / COMB ----------
    def op_com(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, _ = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        newv = (~val) & (0xFFFF if is_word else 0xFF)
        wb(newv)
        self.cpu._set_flag("N", (newv & (0x8000 if is_word else 0x80)) != 0)
        self.cpu._set_flag("Z", newv == 0)
        self.cpu._set_flag("V", 0)
        self.cpu._set_flag("C", 1)
        return ("COM" if is_word else "COMB"), extra

    # ---------- INC / INCB ----------
    def op_inc(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)

        if is_word:
            newv = (val + 1) & 0xFFFF
            wb(newv)
            self.cpu._set_flag("N", (newv & 0x8000) != 0)
            self.cpu._set_flag("Z", newv == 0)
            self.cpu._set_flag("C", newv == 0)
            self.cpu._set_flag("V", newv == 0x8000)   # overflow при +1 к 0x7FFF
            return "INC", extra
        else:
            newv = (val + 1) & 0xFF
            if ea is None:
                full_old = self.cpu.get_register(f"R{reg}")
                full_new = (full_old & 0xFF00) | newv
                wb(full_new)
            else:
                wb(newv)
            self.cpu._set_flag("N", (newv & 0x80) != 0)
            self.cpu._set_flag("Z", newv == 0)
            self.cpu._set_flag("C", newv == 0)
            self.cpu._set_flag("V", newv == 0x80)     # overflow при +1 к 0x7F
            return "INCB", extra
        
    # ---------- DEC / DECB ----------
    def op_dec(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, _ = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        newv = (val - 1) & (0xFFFF if is_word else 0xFF)
        wb(newv)
        self.cpu._set_flag("N", (newv & (0x8000 if is_word else 0x80)) != 0)
        self.cpu._set_flag("Z", newv == 0)
        self.cpu._set_flag("C", newv == (0xFFFF if is_word else 0xFF))
        self.cpu._set_flag("V", newv == (0x7FFF if is_word else 0x7F))
        return ("DEC" if is_word else "DECB"), extra

    # ---------- NEG / NEGB ----------
    def op_neg(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, _ = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        mask = 0xFFFF if is_word else 0xFF
        newv = ((~val) + 1) & mask
        wb(newv)
        self.cpu._set_flag("N", (newv & (0x8000 if is_word else 0x80)) != 0)
        self.cpu._set_flag("Z", newv == 0)
        self.cpu._set_flag("C", val != 0)
        self.cpu._set_flag("V", val == (0x8000 if is_word else 0x80))
        return ("NEG" if is_word else "NEGB"), extra

    # ---------- MOV ----------
    def op_mov(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, _ = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        _, d_wb, d_ex, _ = self.decode_dst(True, dst_pc, dm, dr)
        d_wb(s_val & 0xFFFF)
        self.cpu._set_flag("N", (s_val & 0x8000) != 0)
        self.cpu._set_flag("Z", s_val == 0)
        self.cpu._set_flag("V", 0)
        return "MOV", s_ex + d_ex

    # ---------- MOVB ----------
    def op_movb(self, pc, kind2, sm, sr, dm, dr, raw):
        # MOVB — копирование байта (8 бит)
        s_val, _, s_ex, s_ea = self.decode_src(False, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        _, d_wb, d_ex, d_ea = self.decode_dst(False, dst_pc, dm, dr)

        # если это память — читаем и записываем только нужный байт
        if d_ea is not None:
            dest_base = int(d_ea) & ~1
            old_word = self.cpu._mem_read_word(dest_base)

            if (int(d_ea) & 1):
                # нечётный адрес → старший байт
                new_word = ((s_val & 0xFF) << 8) | (old_word & 0x00FF)
            else:
                # чётный адрес → младший байт
                new_word = (old_word & 0xFF00) | (s_val & 0xFF)

            self.cpu._mem_write_word(dest_base, new_word)
        else:
            # если регистр — записываем только младший байт
            old_full = self.cpu.get_register(f"R{dr}")
            new_full = (old_full & 0xFF00) | (s_val & 0xFF)
            self.cpu.set_register(f"R{dr}", new_full)

        # Флаги
        self.cpu._set_flag("N", (s_val & 0x80) != 0)
        self.cpu._set_flag("Z", (s_val & 0xFF) == 0)
        self.cpu._set_flag("V", 0)

        # PDP-11: флаг C копируется из старшего бита исходного байта
        self.cpu._set_flag("C", (s_val >> 7) & 1)

        return "MOVB", s_ex + d_ex

    
    # ---------- ADD ----------
    def op_add(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, _ = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, d_wb, d_ex, _ = self.decode_dst(True, dst_pc, dm, dr)
        full = d_val + s_val
        res = full & 0xFFFF
        d_wb(res)
        self.cpu._set_flag("N", (res & 0x8000) != 0)
        self.cpu._set_flag("Z", res == 0)
        self.cpu._set_flag("C", full > 0xFFFF)
        self.cpu._set_flag("V", ((s_val ^ res) & (d_val ^ res) & 0x8000) != 0)
        return "ADD", s_ex + d_ex

    # ---------- SUB ----------
    def op_sub(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, _ = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, d_wb, d_ex, _ = self.decode_dst(True, dst_pc, dm, dr)
        res = (d_val - s_val) & 0xFFFF
        d_wb(res)
        self.cpu._set_flag("N", (res & 0x8000) != 0)
        self.cpu._set_flag("Z", res == 0)
        self.cpu._set_flag("C", d_val < s_val)
        self.cpu._set_flag("V", ((d_val ^ s_val) & (d_val ^ res) & 0x8000) != 0)
        return "SUB", s_ex + d_ex
    
    # ---------- TST / TSTB ----------
    def op_tst(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, _, extra, _ = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc)
        if is_word:
            self.cpu._set_flag("N", (val & 0x8000) != 0)
            self.cpu._set_flag("Z", val == 0)
        else:
            self.cpu._set_flag("N", (val & 0x80) != 0)
            self.cpu._set_flag("Z", (val & 0xFF) == 0)
        self.cpu._set_flag("V", 0)
        self.cpu._set_flag("C", 0)
        return ("TST" if is_word else "TSTB"), extra


    # ---------- MFPS ----------
    def op_mfps(self, pc, wb_flag, mode, reg, raw):
        regname = f"R{reg}"
        psw = self.cpu.db.get_psw() & 0xFF
        old = self.cpu.get_register(regname)
        new = (old & 0xFF00) | psw
        self.cpu.set_register(regname, new)
        return f"MFPS {regname}", 0

    # ---------- MTPS ----------
    def op_mtps(self, pc, wb_flag, mode, reg, raw):
        regname = f"R{reg}"
        reg_val = self.cpu.get_register(regname) & 0xFF
        self.cpu.db.set_psw(reg_val)
        return f"MTPS {regname}", 0

    # ---------- ВЕТВЛЕНИЯ ----------

    def _get_psw_flag(self, name):
        psw = self.cpu.db.get_psw()
        mask = {"C":1, "V":2, "Z":4, "N":8}[name]
        return 1 if (psw & mask) else 0

    def _branch_offset(self, pc, word):
        offset = word & 0xFF
        if offset & 0x80:  # отрицательное
            offset -= 0x100
        return (pc + 2 + offset * 2) & 0xFFFF

    def op_br(self, pc, word):
        new_pc = self._branch_offset(pc, word)
        self.cpu.set_register("R7", new_pc)
        return f"BR {new_pc:06o}", 0

    def op_bne(self, pc, word):
        z = self.cpu._get_flag("Z")
        if self.cpu.debug:
            print(f"[BNE] pc={pc:06o} Z={z}")
        if z == 0:
            new_pc = self._branch_offset(pc, word)
            self.cpu._set_pc(new_pc)
            return f"BNE {new_pc:06o}", 0
        return "BNE (no branch)", 0

    def op_beq(self, pc, word):
        z = self.cpu._get_flag("Z")
        if self.cpu.debug:
            print(f"[BEQ] pc={pc:06o} Z={z}")
        if z == 1:
            new_pc = self._branch_offset(pc, word)
            self.cpu._set_pc(new_pc)
            return f"BEQ {new_pc:06o}", 0
        return "BEQ (no branch)", 0

    def op_bpl(self, pc, word):
        n = self.cpu._get_flag("N")
        if self.cpu.debug:
            print(f"[BPL] pc={pc:06o} N={n}")
        if n == 0:
            new_pc = self._branch_offset(pc, word)
            self.cpu._set_pc(new_pc)
            return f"BPL {new_pc:06o}", 0
        return "BPL (no branch)", 0

    def op_bmi(self, pc, word):
        n = self.cpu._get_flag("N")
        if self.cpu.debug:
            print(f"[BMI] pc={pc:06o} N={n}")
        if n == 1:
            new_pc = self._branch_offset(pc, word)
            self.cpu._set_pc(new_pc)
            return f"BMI {new_pc:06o}", 0
        return "BMI (no branch)", 0

    def op_jmp(self, pc, word):
        mode = (word >> 3) & 0x7
        reg = word & 0x7
        _, _, _, ea = self.cpu.resolve_operand(is_word=True, mode=mode, reg=reg, pc=pc)
        if ea is not None:
            self.cpu.set_register("R7", ea & 0xFFFF)
            return f"JMP {ea:06o}", 0
        return "JMP (invalid)", 0
