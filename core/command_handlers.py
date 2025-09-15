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
            '1067': self.op_mfps,   
            '1064': self.op_mtps,   

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

        if opcode_high in self._two:
            src_mode = (word >> 9) & 0o7
            src_reg  = (word >> 6) & 0o7
            dst_mode = (word >> 3) & 0o7
            dst_reg  = word & 0o7
            handler = self._two[opcode_high]
            return handler(pc, f"{raw[:2]}", src_mode, src_reg, dst_mode, dst_reg, raw)

        op3 = raw[1:4]
        if op3 in self._one:
            wb_flag = raw[0]
            mode    = int(raw[4], 8)
            reg     = int(raw[5], 8)
            return self._one[op3](pc, wb_flag, mode, reg, raw)

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
        self.cpu.flags.N = (v >> sign_bit) & 1
        self.cpu.flags.Z = 1 if v == 0 else 0

    # ---------- CLR / CLRB ----------
    def op_clr(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        if not wb:
            raise ValueError("CLR/CLRB: destination not writable")
        wb(0)
        self.cpu.flags.N = 0
        self.cpu.flags.Z = 1
        self.cpu.flags.C = 0
        return ("CLR" if is_word else "CLRB"), extra

    # ---------- COM / COMB ----------
    def op_com(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        if not wb:
            raise ValueError("COM/COMB: destination not writable")
        newv = (~val) & (0xFFFF if is_word else 0xFF)
        wb(newv)
        self.cpu.flags.N = 1 if (newv & (0x8000 if is_word else 0x80)) else 0
        self.cpu.flags.Z = 1 if newv == 0 else 0
        self.cpu.flags.C = 1
        return ("COM" if is_word else "COMB"), extra

    # ---------- INC / INCB ----------
    def op_inc(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        if not wb:
            raise ValueError("INC/INCB: destination not writable")
        mask = 0xFFFF if is_word else 0xFF
        newv = (val + 1) & mask
        wb(newv)
        self.cpu.flags.N = 1 if (newv & (0x8000 if is_word else 0x80)) else 0
        self.cpu.flags.Z = 1 if newv == 0 else 0
        self.cpu.flags.C = 1 if newv == 0 else 0
        return ("INC" if is_word else "INCB"), extra

    # ---------- DEC / DECB ----------
    def op_dec(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        if not wb:
            raise ValueError("DEC/DECB: destination not writable")
        mask = 0xFFFF if is_word else 0xFF
        newv = (val - 1) & mask
        wb(newv)
        self.cpu.flags.N = 1 if (newv & (0x8000 if is_word else 0x80)) else 0
        self.cpu.flags.Z = 1 if newv == 0 else 0
        self.cpu.flags.C = 1 if newv == mask else 0
        return ("DEC" if is_word else "DECB"), extra

    # ---------- NEG / NEGB ----------
    def op_neg(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, wb, extra, ea = self.cpu.resolve_operand(is_word=is_word, mode=mode, reg=reg, pc=pc, as_dest=True)
        if not wb:
            raise ValueError("NEG/NEGB: destination not writable")
        mask = 0xFFFF if is_word else 0xFF
        newv = ((~val) + 1) & mask
        wb(newv)
        self.cpu.flags.N = 1 if (newv & (0x8000 if is_word else 0x80)) else 0
        self.cpu.flags.Z = 1 if newv == 0 else 0
        self.cpu.flags.C = 1 if val != 0 else 0
        return ("NEG" if is_word else "NEGB"), extra

    # ---------- MOV ----------
    def op_mov(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, s_ea = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        _, d_wb, d_ex, d_ea = self.decode_dst(True, dst_pc, dm, dr)
        if not d_wb:
            raise ValueError("MOV: destination not writable")
        d_wb(s_val & 0xFFFF)
        self.cpu.flags.N = 1 if (s_val & 0x8000) else 0
        self.cpu.flags.Z = 1 if s_val == 0 else 0
        return "MOV", s_ex + d_ex

    # ---------- MOVB ----------
    def op_movb(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _s_wb, s_ex, s_ea = self.decode_src(False, pc, sm, sr)
        dst_pc = (pc + (s_ex * 2)) & 0xFFFF
        d_val, d_wb, d_ex, d_ea = self.decode_dst(False, dst_pc, dm, dr)
        if not d_wb and d_ea is None:
            raise ValueError("MOVB: destination not writable")
        if s_ea is not None:
            s_word = self.cpu._mem_read_word(s_ea & ~1)
        else:

            s_word = s_val & 0xFF  
            s_word = (s_word << 8) | s_word  

        s_hi = (s_word >> 8) & 0xFF
        s_lo = s_word & 0xFF

        if d_ea is not None:
            dest_base = int(d_ea) & ~1
            old_word = self.cpu._mem_read_word(dest_base)

            if (int(d_ea) & 1):  
                
                new_word = ((s_hi & 0xFF) << 8) | (old_word & 0x00FF)
            else:  
                
                new_word = (old_word & 0xFF00) | (s_lo & 0xFF)


            self.cpu._mem_write_word(dest_base, new_word)
        else:
            d_wb(s_val & 0xFF)

        self._set_nz(s_val, is_word=False)

        return "MOVB", s_ex + d_ex
    # ---------- ADD ----------
    def op_add(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, s_ea = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, d_wb, d_ex, d_ea = self.decode_dst(True, dst_pc, dm, dr)
        if not d_wb:
            raise ValueError("ADD: destination not writable")
        full = d_val + s_val
        res = full & 0xFFFF
        d_wb(res)
        self.cpu.flags.N = 1 if (res & 0x8000) else 0
        self.cpu.flags.Z = 1 if res == 0 else 0
        self.cpu.flags.C = 1 if full > 0xFFFF else 0
        return "ADD", s_ex + d_ex

    # ---------- SUB ----------
    def op_sub(self, pc, kind2, sm, sr, dm, dr, raw):
        s_val, _, s_ex, s_ea = self.decode_src(True, pc, sm, sr)
        dst_pc = (pc + s_ex * 2) & 0xFFFF
        d_val, d_wb, d_ex, d_ea = self.decode_dst(True, dst_pc, dm, dr)
        if not d_wb:
            raise ValueError("SUB: destination not writable")
        res = (d_val - s_val) & 0xFFFF
        d_wb(res)
        self.cpu.flags.N = 1 if (res & 0x8000) else 0
        self.cpu.flags.Z = 1 if res == 0 else 0
        self.cpu.flags.C = 1 if d_val < s_val else 0
        return "SUB", s_ex + d_ex
       # -----------TST/TSTB---------
    def op_tst(self, pc, wb_flag, mode, reg, raw):
        is_word = (wb_flag == '0')
        val, _, extra, _ = self.cpu.resolve_operand(
            is_word=is_word, mode=mode, reg=reg, pc=pc
        )

        if is_word:
            self.cpu.flags.N = 1 if (val & 0x8000) else 0
            self.cpu.flags.Z = 1 if val == 0 else 0
        else:
            self.cpu.flags.N = 1 if (val & 0x80) else 0
            self.cpu.flags.Z = 1 if (val & 0xFF) == 0 else 0

        self.cpu.flags.V = 0
        self.cpu.flags.C = 0

        return ("TST" if is_word else "TSTB"), extra


    def op_mfps(self, pc, wb_flag, mode, reg, raw):
        regname = f"R{reg}"
        psw = self.cpu.db.get_psw() & 0xFF
        self.cpu.set_register(regname, psw)
        return f"MFPS {regname}", 0

    def op_mtps(self, pc, wb_flag, mode, reg, raw):
        regname = f"R{reg}"
        psw_val = self.cpu.get_register(regname) & 0xFF
        self.cpu.db.set_psw(psw_val)
        return f"MTPS {regname}", 0
