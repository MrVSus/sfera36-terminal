class CommandHandlers:
    def __init__(self, cpu):
        self.cpu = cpu
        self.opcodes = {
            '050': self.handle_clr,
            '051': self.handle_com,
            '052': self.handle_inc,
            '053': self.handle_dec,
            '054': self.handle_neg,
            '057': self.handle_tst,
            '062': self.handle_asr,
            '063': self.handle_asl
        }

    def execute(self, opcode, word_byte, addr_mode, reg_num, pc):
        handler = self.opcodes.get(opcode)
        if not handler:
            raise ValueError(f"Неизвестный код операции: {opcode}")
        return handler(word_byte, addr_mode, reg_num, pc)

    def _update_flags(self, value, is_word, carry=None):
        mask = 0xFFFF if is_word else 0xFF
        sign_bit = 15 if is_word else 7
        v = value & mask
        self.cpu.flags.N = (v >> sign_bit) & 1
        self.cpu.flags.Z = 1 if v == 0 else 0
        if carry is not None:
            self.cpu.flags.C = 1 if carry else 0

    def handle_clr(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        write_back(0)
        self._update_flags(0, word_byte == '0')
        return f"CLR -> 0"

    def handle_com(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        mask = 0xFFFF if word_byte == '0' else 0xFF
        new_val = (~val) & mask
        write_back(new_val)
        self._update_flags(new_val, word_byte == '0')
        return f"COM: {val} -> {new_val}"

    def handle_inc(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        mask = 0xFFFF if word_byte == '0' else 0xFF
        new_val = (val + 1) & mask
        write_back(new_val)
        carry = 1 if new_val == 0 else 0
        self._update_flags(new_val, word_byte == '0', carry)
        return f"INC: {val} -> {new_val}"

    def handle_dec(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        mask = 0xFFFF if word_byte == '0' else 0xFF
        new_val = (val - 1) & mask
        write_back(new_val)
        carry = 1 if new_val == mask else 0
        self._update_flags(new_val, word_byte == '0', carry)
        return f"DEC: {val} -> {new_val}"

    def handle_neg(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        mask = 0xFFFF if word_byte == '0' else 0xFF
        new_val = (-val) & mask
        write_back(new_val)
        carry = 1 if val != 0 else 0
        self._update_flags(new_val, word_byte == '0', carry)
        return f"NEG: {val} -> {new_val}"

    def handle_tst(self, word_byte, addr_mode, reg_num, pc):
        val, _ = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        self._update_flags(val, word_byte == '0')
        return f"TST: {val}"

    def handle_asr(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        is_word = (word_byte == '0')
        mask = 0xFFFF if is_word else 0xFF
        sign_bit = 15 if is_word else 7
        sign = (val >> sign_bit) & 1
        new_val = ((val >> 1) | (sign << sign_bit)) & mask
        carry = val & 1
        write_back(new_val)
        self._update_flags(new_val, is_word, carry)
        return f"ASR: {val} -> {new_val}"

    def handle_asl(self, word_byte, addr_mode, reg_num, pc):
        val, write_back = self.cpu.resolve_operand(word_byte, addr_mode, reg_num)
        is_word = (word_byte == '0')
        mask = 0xFFFF if is_word else 0xFF
        carry = 1 if (val & (1 << (15 if is_word else 7))) else 0
        new_val = (val << 1) & mask
        write_back(new_val)
        self._update_flags(new_val, is_word, carry)
        return f"ASL: {val} -> {new_val}"