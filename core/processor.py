from data.database import DatabaseManager
from .command_parser import CommandParser
from .command_handlers import CommandHandlers

class CPU:
    def __init__(self, db_manager=None):
        self.db = db_manager or DatabaseManager()
        self.parser = CommandParser()
        self.opcodes = CommandHandlers(self)
        
    def get_register(self, reg_name):
        """Чтение значения регистра"""
        if reg_name == 'R7':
            return self._get_pc()
        
        reg_num = int(reg_name[1:])
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                'SELECT value FROM registers WHERE reg_num = ?',
                (reg_num,)
            )
            return cursor.fetchone()[0]
    
    def set_register(self, reg_name, value):
        """Запись значения в регистр"""
        if reg_name == 'R7':
            self._set_pc(value)
            return
        
        reg_num = int(reg_name[1:])
        with self.db.get_connection() as conn:
            conn.execute(
                'UPDATE registers SET value = ? WHERE reg_num = ?',
                (value, reg_num)
            )
            conn.commit()
    
    def _get_pc(self):
        """Чтение программного счётчика (R7)"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                'SELECT value FROM program_counter WHERE id = 0'
            )
            return cursor.fetchone()[0]
    
    def _set_pc(self, value):
        """Установка программного счётчика (R7)"""
        with self.db.get_connection() as conn:
            conn.execute(
                'UPDATE program_counter SET value = ? WHERE id = 0',
                (value,)
            )
            conn.commit()
    
    def execute(self, raw_command):
        try:
            parsed = self.parser.parse(raw_command)
            
            if parsed['type'] == 'REG_READ':
                value = self.get_register(parsed['reg'])
                return f"{parsed['reg']}={value} (0o{oct(value)[2:]})"
            
            elif parsed['type'] == 'MEM_OP':
                addr_dec = int(parsed['addr'], 8)
                self.db.validate_address(addr_dec)
                
                if parsed['value'] == '0':
                    self.db.set_memory_value(addr_dec, '0')
                    return f"Маркер остановки по адресу {oct(addr_dec)[2:]}"
                
                self.db.set_memory_value(addr_dec, parsed['value'])
                return f"Записано: {parsed['addr']}₈ -> {parsed['value']}"
            
            elif parsed['type'] == 'EXEC_AT':
                start_addr = int(parsed['addr'], 8)
                self._set_pc(start_addr)
                return self._run_program()
            
            return "Неизвестная команда"
        except Exception as e:
            return f"Ошибка: {str(e)}"
    
    def _run_program(self):
        """Выполнение программы с текущего PC"""
        output = []
        pc = self._get_pc()
        
        while True:
            # 1. Получаем команду из памяти
            cmd_value = self.db.get_memory_value(pc)
            
            # 2. Проверка маркера остановки
            if cmd_value == '0':
                output.append(f"Программа завершена по адресу {oct(pc)[2:]}")
                self._set_pc(pc + 2)  # R7 указывает на следующую ячейку после 0
                break
                
            # 3. Разбор команды
            try:
                # Проверка формата команды (6 цифр)
                if len(cmd_value) != 6 or not cmd_value.isdigit():
                    raise ValueError(f"Некорректный формат команды: {cmd_value}")
                
                # Разбиваем команду на составляющие
                word_byte = cmd_value[0]  # 0 - слово, 1 - байт
                opcode = cmd_value[1:4]   # Код операции
                addr_mode = cmd_value[4]   # Режим адресации
                reg_num = int(cmd_value[5]) # Номер регистра (0-6)
                
                # 4. Выполнение команды
                if opcode in self.opcodes.opcodes:
                    result = self.opcodes.execute(
                        opcode=opcode,
                        word_byte=word_byte,
                        addr_mode=addr_mode,
                        reg_num=reg_num,
                        pc=pc
                    )
                    output.append(f"{oct(pc)[2:]}: {result}")
                else:
                    output.append(f"{oct(pc)[2:]}: Неизвестный код операции {opcode}")
                
                # 5. Переход к следующей команде
                pc += 2
                self._set_pc(pc)
                
            except Exception as e:
                output.append(f"Ошибка выполнения по адресу {oct(pc)[2:]}: {str(e)}")
                self._set_pc(0)
                break
        
        return "\n".join(output)