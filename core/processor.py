from types import SimpleNamespace
from data.database import DatabaseManager
from .command_parser import CommandParser
from .command_handlers import CommandHandlers

class Registers:
    def __init__(self):
        self.regs = [0] * 8  # R0..R7

    def get(self, n: int) -> int:
        return self.regs[n] & 0xFFFF

    def set(self, n: int, val: int):
        self.regs[n] = val & 0xFFFF

    def __getitem__(self, key):
        if isinstance(key, str) and key.startswith("R"):
            return self.get(int(key[1:]))
        return self.get(key)

    def __setitem__(self, key, value):
        if isinstance(key, str) and key.startswith("R"):
            self.set(int(key[1:]), value)
        else:
            self.set(key, value)
class Memory:
    def __init__(self, size=65536):
        self.mem = [0] * size  # 64K памяти по байтам

    def get_byte(self, addr: int) -> int:
        return self.mem[addr & 0xFFFF]

    def set_byte(self, addr: int, val: int):
        self.mem[addr & 0xFFFF] = val & 0xFF

    def get_word(self, addr: int) -> int:
        lo = self.get_byte(addr)
        hi = self.get_byte(addr + 1)
        return ((hi << 8) | lo) & 0xFFFF

    def set_word(self, addr: int, val: int):
        self.set_byte(addr, val & 0xFF)         # младший байт
        self.set_byte(addr + 1, (val >> 8) & 0xFF)  # старший байт

class CPU:

    def __init__(self, db_manager=None, db_debug=False, debug=False):
        self.db = db_manager or DatabaseManager(debug=db_debug)
        self.parser = CommandParser()
        self.opcodes = CommandHandlers(self)
        self.flags = SimpleNamespace(N=0, Z=0, C=0)
        self.debug = debug
        self.mem = Memory()
        self.regs = Registers()

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
                return f"{value:06o}"

            elif parsed['type'] == 'REG_WRITE':
                val = int(parsed['value'], 8)
                self.set_register(parsed['reg'], val)
                return None

            elif parsed['type'] == 'MEM_READ':
                addr_dec = int(parsed['addr'], 8)
                val = self._mem_read_word(addr_dec)
                return f"{val:06o}"

            elif parsed['type'] == 'MEM_WRITE':
                addr_dec = int(parsed['addr'], 8)
                sval = parsed['value']
                if sval == '0':
                    self._mem_write_word(addr_dec, 0)
                else:
                    iv = int(sval, 8)
                    self._mem_write_word(addr_dec, iv)
                return None

            elif parsed['type'] == 'EXEC_AT':
                start_addr = int(parsed['addr'], 8)
                self._set_pc(start_addr)
                self._run_program()
                return None

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

            try:
                word_val = int(word_str, 8)  # октальное → int
            except ValueError:
                out_lines.append(f"{pc:o}: Неверные данные в памяти: {word_str}")
                break

            if word_val == 0:
                out_lines.append(f"Программа завершена по адресу {pc:o}")
                self._set_pc((pc + 2) & 0xFFFF)
                break

            # ---------- новый декодер ----------
            opcode   = (word_val >> 12) & 0o17
            src_mode = (word_val >> 9) & 0o7
            src_reg  = (word_val >> 6) & 0o7
            dst_mode = (word_val >> 3) & 0o7
            dst_reg  = word_val & 0o7

            # вызываем обработчик
            try:
                text, extra_words = self.opcodes.execute(
                    opcode=opcode,
                    src_mode=src_mode,
                    src_reg=src_reg,
                    dst_mode=dst_mode,
                    dst_reg=dst_reg,
                    pc=pc,
                    raw_word=word_val
                )
                if text:
                    out_lines.append(f"{pc:o}: {text}")
            except StopIteration:
                out_lines.append(f"Программа завершена по адресу {pc:o}")
                self._set_pc((pc + 2) & 0xFFFF)
                break
            except Exception as e:
                out_lines.append(f"{pc:o}: Ошибка при исполнении: {e}")
                extra_words = 0

            # шаг PC
            pc = (pc + 2 + (extra_words * 2)) & 0xFFFF
            self._set_pc(pc)

        return "\n".join(out_lines)


    # ---------- Нормализация строк/чисел ----------
    def _raw_mem_fetch(self, addr: int) -> str:
        phys = self._map_addr(addr)
        s = self.db.get_memory_value(phys)
        if s == '0':
            return '000000'
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
        addr = int(addr) & 0xFFFF
        if 0 <= addr <= 0o1777:
            return self._lowpage_base + addr
        self.db.validate_address(addr)
        return addr

        # ---------- Память: слово/байт ----------
    def _mem_read_word(self, addr: int) -> int:
        base = addr & ~1
        phys = self._map_addr(base)
        return self.db.get_word(phys) & 0xFFFF

    def _mem_write_word(self, addr: int, val: int):
        base = addr & ~1
        phys = self._map_addr(base)
        self.db.set_word(phys, int(val) & 0xFFFF)

    def _mem_read_byte(self, addr: int) -> int:
        phys = self._map_addr(addr)
        return self.db.get_byte(phys) & 0xFF

    def _mem_write_byte(self, addr: int, b: int):
        phys = self._map_addr(addr)
        self.db.set_byte(phys, int(b) & 0xFF)


    # ---------- Адресация ----------
    def resolve_operand(self, is_word: bool, mode: int, reg: int, pc: int, as_dest: bool):
        step = 2 if is_word else 1
        print(f"[DEBUG] resolve_operand вызван: mode={mode}, reg={reg}, is_word={is_word}, as_dest={as_dest}")
        def read(addr):
            return self.mem.get_word(addr) if is_word else self.mem.get_byte(addr)

        def write(addr, val):
            if is_word:
                self.mem.set_word(addr, val)
            else:
                self.mem.set_byte(addr, val)

        # mode 0: Rn
        if mode == 0:
            val = self.regs[reg]
            if not is_word:
                val &= 0xFF
            def store(v):
                if is_word:
                    self.regs[reg] = v
                else:
                    old = self.regs[reg]
                    self.regs[reg] = (old & 0xFF00) | (v & 0xFF)
            return val, store if as_dest else None

        # mode 1: (Rn)
        if mode == 1:
            addr = self.regs[reg]
            val = read(addr)
            return val, (lambda v: write(addr, v)) if as_dest else None

        # mode 2: (Rn)+
        if mode == 2:  # (R)+
            addr = self.registers[reg]
            val = self.get_word(addr) if is_word else self.get_byte(addr)
            self.registers[reg] += step
            def store(v):
                if is_word:
                    self.set_word(addr, v)
                else:
                    self.set_byte(addr, v)
            return val, (store if as_dest else None), 0

        # mode 3: @(Rn)+
        if mode == 3:
            ptr = self.regs[reg]
            ea = self.mem.get_word(ptr)
            self.regs[reg] = (ptr + 2) & 0xFFFF
            val = read(ea)
            return val, (lambda v: write(ea, v)) if as_dest else None

        # mode 4: -(Rn)
        if mode == 4:
            self.registers[reg] -= step
            addr = self.registers[reg]
            val = self.get_word(addr) if is_word else self.get_byte(addr)
            def store(v):
                if is_word:
                    self.set_word(addr, v)
                else:
                    self.set_byte(addr, v)
            return val, (store if as_dest else None), 0

        # mode 5: @-(Rn)
        if mode == 5:
            new_addr = (self.regs[reg] - 2) & 0xFFFF
            self.regs[reg] = new_addr
            ea = self.mem.get_word(new_addr)
            val = read(ea)
            return val, (lambda v: write(ea, v)) if as_dest else None

        # mode 6: X(Rn)
        if mode == 6:
            disp = self.mem.get_word(self.regs[7])
            self.regs[7] = (self.regs[7] + 2) & 0xFFFF
            base = self.regs[reg]
            ea = (base + disp) & 0xFFFF
            val = read(ea)
            return val, (lambda v: write(ea, v)) if as_dest else None

        # mode 7: @X(Rn)
        if mode == 7:
            disp = self.mem.get_word(self.regs[7])
            self.regs[7] = (self.regs[7] + 2) & 0xFFFF
            base = self.regs[reg]
            ptr = (base + disp) & 0xFFFF
            ea = self.mem.get_word(ptr)
            val = read(ea)
            return val, (lambda v: write(ea, v)) if as_dest else None

        raise ValueError(f"Неизвестный режим адресации {mode}, R{reg}")