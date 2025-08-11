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
        """Основной метод выполнения команд"""
        handler = self.opcodes.get(opcode)
        if not handler:
            raise ValueError(f"Неизвестный код операции: {opcode}")
        
        return handler(
            word_byte=word_byte,
            addr_mode=addr_mode,
            reg_num=reg_num,
            pc=pc
        )
    def _validate_reg(self, cpu, reg_name):
        if reg_name == 'R7':
            raise ValueError("Регистр R7 нельзя использовать в операциях")  
    def _update_flags(self, cpu, value, carry=None):
        # Установка флагов N (negative) и Z (zero)
        cpu.flags.N = (value >> 15) & 1
        cpu.flags.Z = 1 if value == 0 else 0
        
        # Флаг C (carry)
        if carry is not None:
            cpu.flags.C = carry
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
    