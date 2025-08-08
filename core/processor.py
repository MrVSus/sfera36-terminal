from .command_parser import CommandParser
from .command_handlers import CommandHandlers

class CPU:
    def __init__(self):
        self.registers = {f'R{i}': 0 for i in range(8)}  # R0-R7
        self.memory = {}  # Память: {адрес: значение}
        self.parser = CommandParser()  # Инициализация парсера
        self.opcodes = CommandHandlers()
        self.pc = None  # Счетчик команд

    def execute(self, raw_command):
        try:
            parsed = self.parser.parse(raw_command)
            
            if parsed['type'] == 'REG_READ':
                return self._read_register(parsed['reg'])
            elif parsed['type'] == 'MEM_OP':
                return self._write_memory(parsed['addr'], parsed['value'])
            elif parsed['type'] == 'EXEC_AT':
                return self._run_program(parsed['addr'])
            return "Неизвестная команда"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    def _read_register(self, reg_name):
        """Чтение регистра Rn/ или n/"""
        reg = reg_name if reg_name.startswith('R') else f'R{reg_name}'
        value = self.registers.get(reg, 0)
        return f"{reg}={value} (0o{oct(value)[2:]})"

    def _write_memory(self, addr, value):
        """Запись в память XXXX/YYYYY"""
        addr_int = int(addr, 8)
        
        if value == '0':
            self.memory[addr_int] = 0
            return f"Маркер остановки по адресу {oct(addr_int)}"
        
        self.memory[addr_int] = int(value, 8)
        return f"Записано по адресу {oct(addr_int)}"

    def _run_program(self, start_addr):
        """Выполнение программы с адреса XXXXG"""
        self.pc = int(start_addr, 8)
        output = []
        
        while self.pc in self.memory:
            cmd_value = self.memory[self.pc]
            
            if cmd_value == 0:  # Маркер остановки
                self.pc = None
                output.append("Программа завершена")
                break
                
            # Преобразуем в строку формата 005104
            cmd_str = f"{cmd_value:06d}"
            
            if cmd_str.startswith('00'):
                handler = self.handlers.get_handler(cmd_value)
                if handler:
                    reg_num = int(cmd_str[-1])
                    result = handler(self, reg_num)
                    output.append(result)
            
            self.pc += 2  # Переход к следующей команде
        
        return "\n".join(output) if output else "Нет команд для выполнения"