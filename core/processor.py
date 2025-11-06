
from types import SimpleNamespace
from data.database import DatabaseManager
from .command_handlers import CommandHandlers
from .command_parser import CommandParser

class CPU:

    def __init__(self, db_manager=None, db_debug=False, debug=False):
        self.db = db_manager or DatabaseManager(debug=db_debug)
        self.parser = CommandParser()
        self.op = CommandHandlers(self)
        self.flags = SimpleNamespace(N=0, Z=0, C=0)
        self.debug = debug

        self._lowpage_base = self.db.MIN_ADDR  # 0o1000
        self.last_read = None  # ('mem', addr) или ('reg', 'R1')

   # ---------- Проверка BUS ----------
    def _check_bus(self, addr: int):
        a = int(addr) & 0xFFFF
        # верхняя граница в восьмеричной 0o157776 -> в int:
        max_addr = int('157776', 8)
        if not (0 <= a <= max_addr):
            # возвращаем специфическую строку сверху — но бросим исключение чтобы остановить flow
            raise RuntimeError("BUS ERROR")

    # ---------- Line Feed helper ----------
    def _line_feed(self):
        if not self.last_read:
            return None

        kind = self.last_read[0]

        if kind == 'mem':
            _, addr, width = self.last_read
            step = 1 if width == 'byte' else 2
            next_addr = (int(addr) + step) & 0xFFFF
            try:
                self._check_bus(next_addr)
            except RuntimeError as e:
                return "BUS ERROR"
            if (next_addr & 1) == 0:
                v = self._mem_read_word(next_addr)
                self.last_read = ('mem', next_addr, 'word')
                return f"{v:06o}"
            else:
                v = self._mem_read_byte(next_addr)
                self.last_read = ('mem', next_addr, 'byte')
                return f"{v:03o}"

        elif kind == 'reg':
            _, reg_idx = self.last_read
            next_reg = (int(reg_idx) + 1) % 8
            val = self.db.get_register_value(next_reg) & 0xFFFF
            self.last_read = ('reg', next_reg)
            return f"{val:06o}"

        return None

    # ---------- Регистры ----------
    def get_register(self, reg_name: str) -> int:
        reg_num = int(reg_name[1:])
        return self.db.get_register_value(reg_num) & 0xFFFF

    def set_register(self, reg_name: str, value: int):
        reg_num = int(reg_name[1:])
        self.db.set_register_value(reg_num, int(value) & 0xFFFF)

    def _get_pc(self) -> int:
        return self.get_register("R7")

    def _set_pc(self, value: int):
        self.set_register("R7", int(value) & 0xFFFF)

        # ---------- Консольные команды ----------
    def execute(self, raw_command: str):
        try:
            if raw_command is not None and raw_command.strip() == "":
                return self._line_feed()

            parsed = self.parser.parse(raw_command)

            # ---------- чтение регистра ----------
            if parsed['type'] == 'REG_READ':
                reg = parsed['reg']
                reg_idx = int(reg[1:])
                value = self.get_register(reg)
                self.last_read = ('reg', reg_idx)
                return f"{reg}/ {value:06o}"

            # ---------- запись регистра ----------
            if parsed['type'] == 'REG_WRITE':
                reg = parsed['reg']
                reg_idx = int(reg[1:])
                old_val = self.get_register(reg)
                new_val = int(parsed['value'], 8)
                self.set_register(reg, new_val)
                self.last_read = None
                return f"{reg}/{old_val:06o} {new_val:06o}"

            # ---------- чтение памяти ----------
            if parsed['type'] == 'MEM_READ':
                addr = int(parsed['addr'], 8)
                try:
                    self._check_bus(addr)
                except RuntimeError:
                    return "BUS ERROR"

                if (addr & 1) == 0:
                    v = self._mem_read_word(addr)
                    self.last_read = ('mem', addr, 'word')
                    return f"{addr:06o}/ {v:06o}"
                else:
                    v = self._mem_read_byte(addr)
                    self.last_read = ('mem', addr, 'byte')
                    return f"{addr:06o}/ {v:03o}"

            # ---------- запись памяти ----------
            if parsed['type'] == 'MEM_WRITE':
                addr = int(parsed['addr'], 8)
                try:
                    self._check_bus(addr)
                except RuntimeError:
                    return "BUS ERROR"

                old_val = self._mem_read_word(addr & ~1)
                sval = parsed['value']
                ival = int(sval, 8)

                if sval == '0':
                    self._mem_write_word(addr & ~1, 0)
                else:
                    if (addr & 1) == 0:
                        self._mem_write_word(addr, ival)
                    else:
                        self._mem_write_byte(addr, ival & 0xFF)

                new_val = self._mem_read_word(addr & ~1)
                self.last_read = None
                return f"{addr:06o}/{old_val:06o} {new_val:06o}"

            # ---------- EXECUTE ----------
            if parsed['type'] == 'EXEC_AT':
                addr = int(parsed['addr'], 8)
                try:
                    self._check_bus(addr)
                except RuntimeError:
                    return "BUS ERROR"
                self._set_pc(addr)
                self.last_read = None
                self._run_program()
                r7_val = self.get_register("R7")
                return f"{addr:06o}G {r7_val:06o}"

            # ---------- чтение PSW ----------
            if parsed['type'] == 'PSW_READ':
                psw = self.db.get_psw()
                return f"RS/ {psw:03o}"

            # ---------- запись PSW ----------
            if parsed['type'] == 'PSW_WRITE':
                old_val = self.db.get_psw()
                new_val = int(parsed['value'], 8)
                self.db.set_psw(new_val)
                return f"RS/{old_val:03o} {new_val:03o}"

            if parsed['type'] == 'QUIT':
                return "QUIT"

            return "Ошибка: Неизвестная команда"

        except Exception as e:
            msg = str(e)
            if msg == "BUS ERROR":
                return "BUS ERROR"
            return f"Ошибка: {msg}"


    # ---------- Исполнение программы ----------
    def _run_program(self):
        out = []
        pc = self._get_pc()
        self.executing = True

        while True:
            raw = self._raw_mem_fetch(pc)
            try:
                wval = int(raw, 8)
            except ValueError:
                out.append(f"{pc:06o}: Ошибка: некорректное слово {raw}")
                break

            if wval == 0:
                self._set_pc((pc + 2) & 0xFFFF)
                break

            try:

                text, extra_words = self.op.execute(pc=pc, raw_word=raw)

               
                new_pc = self.get_register("R7")
                if new_pc != pc:
                    pc = new_pc
                else:
                    pc = (pc + 2 + (extra_words * 2)) & 0xFFFF

                if self.debug and text:
                    out.append(f"{pc:06o}: {text}")


                if len(out) > 2000:
                    out.append("ОШИБКА: превышено количество шагов")
                    break

            except Exception as e:
                out.append(f"{pc:06o}: Ошибка: {e}")
                pc = (pc + 2) & 0xFFFF

            self._set_pc(pc)

        return "\n".join(out) if out else ""


    # ---------- Нормализация ----------
    def _raw_mem_fetch(self, addr: int) -> str:
        base = int(addr) & ~1
        phys = self._map_addr(base, for_code=True)
        hi, lo = self.db.get_memory_bytes(phys)  
        word = ((hi << 8) | lo) & 0xFFFF
        if self.debug:
            print(f"[DBG FETCH] logical {base:o} -> phys {phys:o} : {word:06o} (hi={hi:03o} lo={lo:03o})")
        return f"{word:06o}"



    def _oct_to_int(self, s):
        if s is None:
            return 0
        ss = str(s).strip()
        if ss == "0" or ss == "":
            return 0
        return int(ss, 8)

    def _int_to_oct6(self, v):
        return f"{int(v) & 0xFFFF:06o}"

    # ---------- Отображение адресов ----------
    def _map_addr(self, addr: int, *, for_code: bool = False) -> int:
        return int(addr) & 0xFFFF



    # ---------- Память ----------
    def _mem_read_word(self, addr: int) -> int:
        base = int(addr) & ~1
        phys = self._map_addr(base)
        hi, lo = self.db.get_memory_bytes(phys)
        val = ((hi << 8) | lo) & 0xFFFF
        if self.debug:
            print(f"[DBG READ ] logical {base:o} -> phys {phys:o} : {val:06o} (hi={hi:03o} lo={lo:03o})")
        return val

    def _mem_write_word(self, addr: int, value: int):
        base = int(addr) & ~1
        phys = self._map_addr(base)
        v = int(value) & 0xFFFF
        hi = (v >> 8) & 0xFF
        lo = v & 0xFF
        if self.debug:
            print(f"[DBG WRITE] logical {base:o} -> phys {phys:o} : {v:06o} (hi={hi:03o} lo={lo:03o})")
        self.db.set_memory_bytes(phys, hi, lo)

    def _mem_read_byte(self, addr: int) -> int:
        a = int(addr) & 0xFFFF
        base = a & ~1
        w = self._mem_read_word(base)
        return ((w >> 8) & 0xFF) if (a & 1) else (w & 0xFF)

    def _mem_write_byte(self, addr: int, val: int):
        a = int(addr) & 0xFFFF
        base = a & ~1
        cur = self._mem_read_word(base)
        if a & 1:
            new = ((int(val) & 0xFF) << 8) | (cur & 0x00FF)
        else:
            new = (cur & 0xFF00) | (int(val) & 0xFF)
        # dbg
        if self.debug:
            phys = self._map_addr(base)
            print(f"[DBG WRITE-B] logical {a:o} -> phys {phys:o} : byte {int(val)&0xFF:03o}, old_word={cur:06o} -> new_word={new:06o}")
        self._mem_write_word(base, new)

    def _set_flag(self, flag: str, value: int):
        mask = {"C":1, "V":2, "Z":4, "N":8, "T":16}[flag]
        psw = self.db.get_psw()
        if value:
            psw |= mask
        else:
            psw &= ~mask
        self.db.set_psw(psw)

        # синхронизируем кеш-флаги в CPU (все флаги)
        psw_now = self.db.get_psw()
        self.flags.N = 1 if (psw_now & 8) else 0
        self.flags.Z = 1 if (psw_now & 4) else 0
        self.flags.C = 1 if (psw_now & 1) else 0
        self.flags.V = 1 if (psw_now & 2) else 0
        self.flags.T = 1 if (psw_now & 16) else 0

    def _get_flag(self, flag: str) -> int:
        mask = {"C":1, "V":2, "Z":4, "N":8, "T":16}[flag]
        psw = self.db.get_psw() & 0xFF
        return 1 if (psw & mask) else 0




    # ---------- Адресация ----------
    def resolve_operand(self, *, is_word: bool, mode: int, reg: int, pc: int, as_dest: bool = False):
        """
        Режимы адресации для Сфера-36 (PDP-11 подобные).
        Возвращает:
          value, write_back_fn, extra_words, effective_address
        """

        data_step = 2 if is_word else 1  
        ptr_step = 2                     
        reg_name = f"R{reg}"

        # ----------------- helpers -----------------
        def read_ea(addr: int) -> int:
            return self._mem_read_word(addr) if is_word else self._mem_read_byte(addr)

        def write_ea(addr: int, v: int):
            if is_word:
                self._mem_write_word(addr, v & 0xFFFF)
            else:
                self._mem_write_byte(addr, v & 0xFF)

        # ----------------- mode 0: R -----------------
        if mode == 0:
            cur = self.get_register(reg_name) & 0xFFFF
            if is_word:
                def wb_word(v):
                    self.set_register(reg_name, int(v) & 0xFFFF)
                return cur, (wb_word if as_dest else None), 0, None
            else:
                lo = cur & 0xFF
                def wb_byte(v):
                    hi = (cur >> 8) & 0xFF
                    nv = ((hi << 8) | (int(v) & 0xFF)) & 0xFFFF
                    self.set_register(reg_name, nv)
                return lo, (wb_byte if as_dest else None), 0, None

        # ----------------- mode 1: @R -----------------
        if mode == 1:
            ea = self.get_register(reg_name) & 0xFFFF
            val = read_ea(ea)
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 0, ea

        # ----------------- mode 2: (R)+ / #imm -----------------
        if mode == 2:
            if reg == 7:
                # immediate — слово находится в потоке команды по адресу (pc + 2)
                imm_addr = (pc + 2) & 0xFFFF
                imm = self._mem_read_word(imm_addr)

                if as_dest:
                    val = imm if is_word else (imm & 0xFF)
                    def wb(v, a=imm_addr):

                        write_ea(a, v)

                    return val, wb, 1, imm_addr

                val = imm if is_word else (imm & 0xFF)
                return val, None, 1, None

            ea = self.get_register(reg_name) & 0xFFFF
            val = read_ea(ea)
            self.set_register(reg_name, (ea + data_step) & 0xFFFF)
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 0, ea

        # ---------- MODE 3: @(Rn)+ OR @#abs if Rn==7 ----------
        if mode == 3:
            if reg == 7:
                abs_addr = self._mem_read_word((pc + 2) & 0xFFFF)
                val = read_ea(abs_addr)
                wb = (lambda v, a=abs_addr: write_ea(a, v)) if as_dest else None
                return val, wb, 1, abs_addr

            ptr_addr = self.get_register(reg_name) & 0xFFFF
            ea = self._mem_read_word(ptr_addr)  
            self.set_register(reg_name, (ptr_addr + ptr_step) & 0xFFFF)  
            val = read_ea(ea)  
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 0, ea


        # ----------------- mode 4: -(R) -----------------
        if mode == 4:
            new_addr = (self.get_register(reg_name) - data_step) & 0xFFFF
            self.set_register(reg_name, new_addr)
            val = read_ea(new_addr)
            wb = (lambda v, a=new_addr: write_ea(a, v)) if as_dest else None
            return val, wb, 0, new_addr

        # ----------------- mode 5: @-(R) -----------------
        if mode == 5:
            new_addr = (self.get_register(reg_name) - ptr_step) & 0xFFFF
            self.set_register(reg_name, new_addr)
            ea = self._mem_read_word(new_addr)
            val = read_ea(ea)
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 0, ea

        # ----------------- mode 6: X(R) / PC-rel -----------------
        if mode == 6:
            disp = self._mem_read_word((pc + 2) & 0xFFFF)
            base = (self.get_register(reg_name) if reg != 7 else (pc + 2)) & 0xFFFF
            ea = (base + disp) & 0xFFFF
            val = read_ea(ea)
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 1, ea

        # ----------------- mode 7: @X(R) / PC-rel deferred -----------------
        if mode == 7:
            disp = self._mem_read_word((pc + 2) & 0xFFFF)
            base = (self.get_register(reg_name) if reg != 7 else (pc + 2)) & 0xFFFF
            ptr = (base + disp) & 0xFFFF
            ea = self._mem_read_word(ptr)
            val = read_ea(ea)
            wb = (lambda v, a=ea: write_ea(a, v)) if as_dest else None
            return val, wb, 1, ea

        raise ValueError(f"Unknown addressing mode: {mode} for R{reg}")


