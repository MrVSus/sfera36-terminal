# core/processor.py
from types import SimpleNamespace
from data.database import DatabaseManager
from .command_parser import CommandParser
from .command_handlers import CommandHandlers


class CPU:
    """
    Эмулятор «Сфера-36» (урезанный PDP-11-подобный формат).
    ВАЖНО:
    - Память БД задана с MIN_ADDR=0o1000. Чтобы сценарии из лекций с низкими адресами (<= 0o1777)
      работали без изменения БД, используем внутреннее отображение низкой страницы на окно в БД.
    - Все адресные режимы возвращают extra_words — количество ДОП. слов, съеденных операндом,
      чтобы ПК сдвигался корректно (иначе после #imm / X(PC) следующий fetch ломается).
    """

    def __init__(self, db_manager=None, db_debug=False, debug=False):
        self.db = db_manager or DatabaseManager(debug=db_debug)
        self.parser = CommandParser()
        self.opcodes = CommandHandlers(self)
        self.flags = SimpleNamespace(N=0, Z=0, C=0)
        self.debug = debug

        # Окно для отображения низких адресов (0..01777) на БД (1000..2777)
        self._lowpage_base = self.db.MIN_ADDR  # 0o1000

    # ---------- Регистры ----------
    def get_register(self, reg_name: str) -> int:
        reg_num = int(reg_name[1:])
        return self.db.get_register_value(reg_num) & 0xFFFF

    def set_register(self, reg_name: str, value: int):
        reg_num = int(reg_name[1:])
        self.db.set_register_value(reg_num, int(value) & 0xFFFF)

    def _get_pc(self) -> int:
        return self.get_register('R7')

    def _set_pc(self, value: int):
        self.set_register('R7', int(value) & 0xFFFF)

    # ---------- Команды консоли ----------
    def execute(self, raw_command: str):
        try:
            parsed = self.parser.parse(raw_command)

            if parsed['type'] == 'REG_READ':
                value = self.get_register(parsed['reg'])
                return f"{parsed['reg']}={value:o}"

            elif parsed['type'] == 'REG_WRITE':
                val = int(parsed['value'], 8)
                self.set_register(parsed['reg'], val)
                return f"{parsed['reg']} <- {parsed['value']}"

            elif parsed['type'] == 'MEM_READ':
                addr_dec = int(parsed['addr'], 8)
                val = self._mem_read_word(addr_dec)
                return f"[{parsed['addr']}] = {val:06o}"

            elif parsed['type'] == 'MEM_WRITE':
                addr_dec = int(parsed['addr'], 8)
                # Сохраняем как есть (октал строка/число) через наши хелперы (они сами нормализуют)
                sval = parsed['value']
                if sval == '0':
                    self._mem_write_word(addr_dec, 0)  # маркер остановки
                else:
                    iv = int(sval, 8)
                    self._mem_write_word(addr_dec, iv)
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

    # ---------- Исполнение программы ----------
    def _run_program(self):
        out_lines = []
        pc = self._get_pc()

        while True:
            word_str = self._raw_mem_fetch(pc)
            # HALT: точный 0
            try:
                word_val = int(word_str, 8)
            except ValueError:
                out_lines.append(f"{pc:o}: Неверные данные в памяти: {word_str}")
                break

            if word_val == 0:
                out_lines.append(f"Программа завершена по адресу {pc:o}")
                self._set_pc((pc + 2) & 0xFFFF)
                break

            if len(word_str) != 6 or not all(c in '01234567' for c in word_str):
                out_lines.append(f"{pc:o}: Пропуск некорректного слова {word_str}")
                pc = (pc + 2) & 0xFFFF
                self._set_pc(pc)
                continue

            # Декод
            w_or_b  = word_str[0]
            opcode3 = word_str[1:4]
            a4      = word_str[4]
            r5      = word_str[5]

            # ВАЖНО: значение по умолчанию
            extra_words = 0

            try:
                text, extra_words = self.opcodes.execute(
                    opcode=opcode3,
                    word_byte=w_or_b,
                    addr_tail=(a4, r5),
                    pc=pc,
                    raw_word=word_str
                )
                out_lines.append(f"{pc:o}: {text}")
            except StopIteration:
                out_lines.append(f"Программа завершена по адресу {pc:o}")
                self._set_pc((pc + 2) & 0xFFFF)
                break
            except Exception as e:
                # Логируем ошибку и пропускаем ТОЛЬКО текущее слово команды
                out_lines.append(f"{pc:o}: Ошибка при исполнении: {e}")
                extra_words = 0  # явное значение на случай будущих правок

            # Шаг ПК: 1 слово команды + доп. слова операндов
            pc = (pc + 2 + (extra_words * 2)) & 0xFFFF
            self._set_pc(pc)

        return "\n".join(out_lines)


    # ---------- Нормализация строк/чисел ----------
    def _raw_mem_fetch(self, addr: int) -> str:
        """Возвращает ровно 6-значную октальную строку или '0' если маркер остановки."""
        phys = self._map_addr(addr)
        s = self.db.get_memory_value(phys)
        if s == '0':
            return '000000'
        # гарантируем 6 знаков
        return s.zfill(6)

    def _oct_to_int(self, s):
        if s is None:
            return 0
        ss = str(s).strip()
        if ss == '0' or ss == '':
            return 0
        return int(ss, 8)

    def _int_to_oct6(self, v):
        return f"{int(v) & 0xFFFF:06o}"

    # ---------- Отображение низкой страницы ----------
    def _map_addr(self, addr: int) -> int:
        """Проецируем 0..01777 в окно [MIN_ADDR .. MIN_ADDR+01777] БД, остальное проверяем как обычно."""
        addr = int(addr) & 0xFFFF
        if 0 <= addr <= 0o1777:
            return self._lowpage_base + addr  # 0o1000..0o2777
        # иначе — обычная проверка БД
        self.db.validate_address(addr)
        return addr

    # ---------- Память: слово/байт ----------
    def _mem_read_word(self, addr: int) -> int:
        base = addr & ~1
        phys = self._map_addr(base)
        raw = self.db.get_memory_value(phys)
        return self._oct_to_int(raw) & 0xFFFF

    def _mem_write_word(self, addr: int, val: int):
        base = addr & ~1
        phys = self._map_addr(base)
        sval = self._int_to_oct6(val)
        self.db.set_memory_value(phys, sval)

    def _mem_read_byte(self, addr: int) -> int:
        base = addr & ~1
        w = self._mem_read_word(base)
        if addr & 1:
            return (w >> 8) & 0xFF
        else:
            return w & 0xFF

    def _mem_write_byte(self, addr: int, b: int):
        base = addr & ~1
        w = self._mem_read_word(base)
        b = int(b) & 0xFF
        if addr & 1:
            w = ((b << 8) | (w & 0x00FF)) & 0xFFFF
        else:
            w = ((w & 0xFF00) | b) & 0xFFFF
        self._mem_write_word(base, w)

    # ---------- Адресация ----------
    def resolve_operand(self, *, is_word: bool, mode: int, reg: int, pc: int, as_dest: bool = False):
        
        data_step = 2 if is_word else 1
        ptr_step  = 2  # указатели всегда словные
        reg_name = f"R{reg}"

        def read_ea(addr):
            return self._mem_read_word(addr) if is_word else self._mem_read_byte(addr)

        def write_ea(addr, v):
            if is_word:
                self._mem_write_word(addr, v & 0xFFFF)
            else:
                self._mem_write_byte(addr, v & 0xFF)

        # ---------- mode 0: register ----------
        if mode == 0:
            cur = self.get_register(reg_name) & 0xFFFF
            if is_word:
                return cur, (lambda v: self.set_register(reg_name, v & 0xFFFF)) if as_dest else None, 0
            else:
                lo = cur & 0xFF
                def wb(v):
                    v = v & 0xFF
                    self.set_register(reg_name, ((cur & 0xFF00) | v))
                return lo, wb if as_dest else None, 0

        # ---------- mode 1: @Rn ----------
        if mode == 1:
            ea = self.get_register(reg_name)
            val = read_ea(ea)
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 0

        # ---------- mode 2: (Rn)+  /  #imm (если Rn=PC) ----------
        if mode == 2:
            if reg == 7:
                # #imm — содержимое следующего слова
                imm = self._mem_read_word((pc + 2) & 0xFFFF)
                if as_dest:
                    raise ValueError("Непосредственный операнд не может быть приёмником")
                val = imm if is_word else (imm & 0xFF)
                return val, None, 1
            ea = self.get_register(reg_name)
            val = read_ea(ea)
            self.set_register(reg_name, (ea + data_step) & 0xFFFF)  # всегда инкремент
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 0

        # ---------- mode 3: @(Rn)+  /  @#abs (если Rn=PC) ----------
        if mode == 3:
            if reg == 7:
                abs_addr = self._mem_read_word((pc + 2) & 0xFFFF)
                val = read_ea(abs_addr)
                return val, (lambda v: write_ea(abs_addr, v)) if as_dest else None, 1
            ptr_addr = self.get_register(reg_name)
            ea = self._mem_read_word(ptr_addr)
            self.set_register(reg_name, (ptr_addr + ptr_step) & 0xFFFF)  # всегда инкремент указателя
            val = read_ea(ea)
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 0

        # ---------- mode 4: -(Rn) ----------
        if mode == 4:
            new_addr = (self.get_register(reg_name) - data_step) & 0xFFFF
            self.set_register(reg_name, new_addr)  # всегда декремент
            val = read_ea(new_addr)
            return val, (lambda v: write_ea(new_addr, v)) if as_dest else None, 0

        # ---------- mode 5: @-(Rn) ----------
        if mode == 5:
            new_addr = (self.get_register(reg_name) - ptr_step) & 0xFFFF
            self.set_register(reg_name, new_addr)  # всегда декремент указателя
            ea = self._mem_read_word(new_addr)
            val = read_ea(ea)
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 0

        # ---------- mode 6: X(Rn) / PC-relative ----------
        if mode == 6:
            disp = self._mem_read_word((pc + 2) & 0xFFFF)
            base = (self.get_register(reg_name) if reg != 7 else (pc + 2)) & 0xFFFF
            ea = (base + disp) & 0xFFFF
            val = read_ea(ea)
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 1

        # ---------- mode 7: @X(Rn) / PC-relative deferred ----------
        if mode == 7:
            disp = self._mem_read_word((pc + 2) & 0xFFFF)
            base = (self.get_register(reg_name) if reg != 7 else (pc + 2)) & 0xFFFF
            ptr = (base + disp) & 0xFFFF
            ea = self._mem_read_word(ptr)
            val = read_ea(ea)
            return val, (lambda v: write_ea(ea, v)) if as_dest else None, 1  # одно слово смещения

        raise ValueError(f"Неизвестный режим адресации: {mode} для R{reg}")
