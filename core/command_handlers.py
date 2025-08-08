class CommandHandlers:
    def __init__(self):
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

    def get_handler(self, cmd_value):
        cmd_str = f"{cmd_value:06d}"
        if cmd_str.startswith('00'):
            return self.opcodes.get(cmd_str[2:4])
        return None
    
    def handle_clr(self, cpu, cmd):
        """Очистка регистра (50)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        cpu.registers.general[reg] = 0
        self._update_flags(cpu, 0)
        return f"Регистр {reg} очищен"
    
    def handle_com(self, cpu, cmd):
        """Инверсия регистра (51)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        value = cpu.registers.general[reg]
        cpu.registers.general[reg] = ~value & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"Инверсия {reg} = {cpu.registers.general[reg]}"
    
    def handle_inc(self, cpu, cmd):
        """Инкремент регистра (52)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        cpu.registers.general[reg] = (cpu.registers.general[reg] + 1) & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"INC {reg} = {cpu.registers.general[reg]}"
    
    def handle_dec(self, cpu, cmd):
        """Декремент регистра (53)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        cpu.registers.general[reg] = (cpu.registers.general[reg] - 1) & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"DEC {reg} = {cpu.registers.general[reg]}"
    
    def handle_neg(self, cpu, cmd):
        """Смена знака (54)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        value = cpu.registers.general[reg]
        cpu.registers.general[reg] = (-value) & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"NEG {reg} = {cpu.registers.general[reg]}"
    
    def handle_tst(self, cpu, cmd):
        """Тестирование регистра (57)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        value = cpu.registers.general[reg]
        self._update_flags(cpu, value)
        return f"TST {reg} = {value}"
    
    def handle_asr(self, cpu, cmd):
        """Арифметический сдвиг вправо (62)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        value = cpu.registers.general[reg]
        cpu.registers.general[reg] = (value >> 1) & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"ASR {reg} = {cpu.registers.general[reg]}"
    
    def handle_asl(self, cpu, cmd):
        """Арифметический сдвиг влево (63)"""
        reg = self._validate_reg(cpu, cmd['reg'])
        value = cpu.registers.general[reg]
        cpu.registers.general[reg] = (value << 1) & 0xFFFF
        self._update_flags(cpu, cpu.registers.general[reg])
        return f"ASL {reg} = {cpu.registers.general[reg]}"
    