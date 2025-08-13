# core/processor.py
from types import SimpleNamespace
from data.database import DatabaseManager
from .command_parser import CommandParser
from .command_handlers import CommandHandlers


class CPU:
    def __init__(self, db_manager=None):
        self.db = db_manager or DatabaseManager()
        self.parser = CommandParser()
        self.opcodes = CommandHandlers(self)
        # Флаги процессора
        self.flags = SimpleNamespace(N=0, Z=0, C=0)

    # --- Работа с регистрами (R0..R7 в POH) ---
    def get_register(self, reg_name):
        reg_num = int(reg_name[1:])
        return self.db.get_register_value(reg_num)

    def set_register(self, reg_name, value):
        reg_num = int(reg_name[1:])
        self.db.set_register_value(reg_num, value & 0xFFFF)

    # PC — это R7
    def _get_pc(self):
        return self.db.get_register_value(7)

    def _set_pc(self, value):
        self.db.set_register_value(7, value & 0xFFFF)

    # --- Парсер команд из консоли ---
    def execute(self, raw_command):
        try:
            parsed = self.parser.parse(raw_command)

            if parsed['type'] == 'REG_READ':
                value = self.get_register(parsed['reg'])
                return f"{parsed['reg']}={value:o}"

            elif parsed['type'] == 'REG_WRITE':
                # принимаем значение в восьмеричной форме от пользователя
                val = int(parsed['value'], 8)
                self.set_register(parsed['reg'], val)
                return f"{parsed['reg']} <- {parsed['value']}"

            elif parsed['type'] == 'MEM_READ':
                addr_dec = int(parsed['addr'], 8)
                self.db.validate_address(addr_dec)
                val = self.db.get_memory_value(addr_dec)
                return f"[{parsed['addr']}] = {val}"

            elif parsed['type'] == 'MEM_WRITE':
                addr_dec = int(parsed['addr'], 8)
                self.db.validate_address(addr_dec)
                # при записи от пользователя сохраняем строку как есть (восьмеричная запись)
                self.db.set_memory_value(addr_dec, parsed['value'])
                return f"[{parsed['addr']}] <- {parsed['value']}"

            elif parsed['type'] == 'EXEC_AT':
                start_addr = int(parsed['addr'], 8)
                self._set_pc(start_addr)
                return self._run_program()

            elif parsed['type'] == 'QUIT':
                return "QUIT"

            return "Неизвестная команда"
        except Exception as e:
            return f"Ошибка: {str(e)}"

    # --- Выполнение программы с текущего PC ---
    def _run_program(self):
        output = []

        while True:
            pc = self._get_pc()                    # адрес текущей инструкции
            cmd_value = self.db.get_memory_value(pc)

            # маркер остановки
            if cmd_value == '0':
                output.append(f"Программа завершена по адресу {pc:o}")
                # после нуля R7 должен указывать на слово через 2 слова
                self._set_pc(pc + 4)
                break

            cmd_str = str(cmd_value).strip()

            # если в ячейке нечисловая строка — считаем это неинструкционным словом
            if not cmd_str.isdigit():
                output.append(f"Найдено неинструкционное слово '{cmd_str}' по адресу {pc:o}. Выполнение остановлено.")
                self._set_pc(pc + 4)
                break

            # приведение к формату 6 цифр (если короче — дополняем нулями слева)
            cmd_str = cmd_str.zfill(6)

            # парсим инструкцию
            word_byte = cmd_str[0]          # '0' - слово, '1' - байт
            opcode = cmd_str[1:4]
            addr_mode = cmd_str[4]
            reg_num = int(cmd_str[5])

            # Advance PC to the next word BEFORE executing — so resolve_operand can use PC for literals/displacements.
            self._set_pc(pc + 4)

            try:
                if opcode in self.opcodes.opcodes:
                    result = self.opcodes.execute(
                        opcode=opcode,
                        word_byte=word_byte,
                        addr_mode=addr_mode,
                        reg_num=reg_num,
                        pc=pc
                    )
                    output.append(f"{pc:o}: {result}")
                else:
                    output.append(f"{pc:o}: Неизвестный код операции {opcode}")

                # после выполнения следующая итерация возьмёт self._get_pc() как адрес следующей инструкции
                # (resolve_operand и команды сами могут менять R7 при необходимости)
            except Exception as e:
                output.append(f"Ошибка выполнения по адресу {pc:o}: {str(e)}")
                self._set_pc(0)
                break

        return "\n".join(output)

    # --- Разрешение операндов (использует R7 как PC) ---
    def resolve_operand(self, word_byte, addr_mode, reg_num):
        """
        Возвращает (value:int, write_back_fn)
        - value — целое (int) уже интерпретированное из восьмеричной строки
        - write_back_fn(addr_val) — функция записи, которая запишет значение в память (октальной строкой) или в регистр
        """
        is_word = (word_byte == '0')
        step = 2 if is_word else 1
        mask = 0xFFFF if is_word else 0xFF
        reg_name = f"R{reg_num}"

        def read_mem_int(addr):
            # read memory cell as octal string and return int
            raw = self.db.get_memory_value(addr)
            return int(raw, 8) & mask

        def write_mem_from_int(addr, val_int):
            # write integer into memory as 6-digit octal string
            self.db.set_memory_value(addr, f"{val_int & mask:06o}")

        # 0 — Rn (регистровый)
        if addr_mode == '0':
            val = self.get_register(reg_name) & mask
            return val, lambda v: self.set_register(reg_name, v & mask)

        # 1 — @Rn (косвенно через регистр)
        elif addr_mode == '1':
            addr = self.get_register(reg_name)
            val = read_mem_int(addr)
            return val, lambda v: write_mem_from_int(addr, v)

        # 2 — (Rn)+ (постинкремент)
        elif addr_mode == '2':
            addr = self.get_register(reg_name)
            val = read_mem_int(addr)
            self.set_register(reg_name, addr + step)
            return val, lambda v: write_mem_from_int(addr, v)

        # 3 — @(Rn)+
        elif addr_mode == '3':
            indir_addr = self.get_register(reg_name)
            addr = int(self.db.get_memory_value(indir_addr), 8)  # адрес берём как октальную строку
            val = read_mem_int(addr)
            self.set_register(reg_name, indir_addr + step)
            return val, lambda v: write_mem_from_int(addr, v)

        # 4 — -(Rn)
        elif addr_mode == '4':
            new_addr = self.get_register(reg_name) - step
            self.set_register(reg_name, new_addr)
            val = read_mem_int(new_addr)
            return val, lambda v: write_mem_from_int(new_addr, v)

        # 5 — @-(Rn)
        elif addr_mode == '5':
            new_addr = self.get_register(reg_name) - step
            self.set_register(reg_name, new_addr)
            indir_addr = int(self.db.get_memory_value(new_addr), 8)
            val = read_mem_int(indir_addr)
            return val, lambda v: write_mem_from_int(indir_addr, v)

        # 6 — A(Rn) : displacement хранится в ячейке по текущему PC (R7), который уже был advance'нут
        elif addr_mode == '6':
            disp_addr = self._get_pc()
            displacement = int(self.db.get_memory_value(disp_addr), 8)  # displacement читаем как октальную строку
            # consume displacement word
            self._set_pc(disp_addr + step)
            addr = self.get_register(reg_name) + displacement
            val = read_mem_int(addr)
            return val, lambda v: write_mem_from_int(addr, v)

        # 7 — @A(Rn)
        elif addr_mode == '7':
            disp_addr = self._get_pc()
            displacement = int(self.db.get_memory_value(disp_addr), 8)
            self._set_pc(disp_addr + step)
            indir_addr = self.get_register(reg_name) + displacement
            final_addr = int(self.db.get_memory_value(indir_addr), 8)
            val = read_mem_int(final_addr)
            return val, lambda v: write_mem_from_int(final_addr, v)

        # PC-relative / through R7 modes (we expect reg_num == 7 for these)
        elif addr_mode == '27' and reg_num == 7:
            pc_addr = self._get_pc()
            immediate_value = int(self.db.get_memory_value(pc_addr), 8) & mask
            self._set_pc(pc_addr + step)
            return immediate_value, lambda v: None

        elif addr_mode == '37' and reg_num == 7:
            pc_addr = self._get_pc()
            indir_addr = int(self.db.get_memory_value(pc_addr), 8)
            self._set_pc(pc_addr + step)
            val = int(self.db.get_memory_value(indir_addr), 8) & mask
            return val, lambda v: write_mem_from_int(indir_addr, v)

        elif addr_mode == '67' and reg_num == 7:
            pc_addr = self._get_pc()
            displacement = int(self.db.get_memory_value(pc_addr), 8)
            self._set_pc(pc_addr + step)
            final_addr = displacement
            val = int(self.db.get_memory_value(final_addr), 8) & mask
            return val, lambda v: write_mem_from_int(final_addr, v)

        elif addr_mode == '77' and reg_num == 7:
            pc_addr = self._get_pc()
            displacement = int(self.db.get_memory_value(pc_addr), 8)
            self._set_pc(pc_addr + step)
            indir_addr = int(self.db.get_memory_value(displacement), 8)
            val = int(self.db.get_memory_value(indir_addr), 8) & mask
            return val, lambda v: write_mem_from_int(indir_addr, v)

        else:
            raise ValueError(f"Неизвестный режим адресации: {addr_mode} для R{reg_num}")
