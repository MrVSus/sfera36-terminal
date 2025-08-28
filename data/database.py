# data/database.py
import sqlite3
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path=None, debug=False):
        self.db_path = db_path or str(Path(__file__).parent.parent / 'data' / 'migrations' / 'db.db')
        self.MIN_ADDR = 0o1000
        self.MAX_ADDR = 0o157777
        self.debug = debug
        self._ensure_db_exists()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def _ensure_db_exists(self):
        with self.get_connection() as conn:
            cur = conn.cursor()

            # POH: R0..R7 (value как INTEGER)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS POH (
                reg_num INTEGER PRIMARY KEY CHECK(reg_num BETWEEN 0 AND 7),
                value INTEGER DEFAULT 0
            )
            ''')
            cur.execute('SELECT COUNT(*) FROM POH')
            if cur.fetchone()[0] == 0:
                cur.executemany('INSERT INTO POH (reg_num, value) VALUES (?, ?)', [(i, 0) for i in range(8)])

            # memory: address -> value (TEXT, 6-digit octal or '000000' or '0' for stop)
            cur.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                address INTEGER PRIMARY KEY,
                value TEXT
            )
            ''')
            cur.execute('SELECT COUNT(*) FROM memory')
            if cur.fetchone()[0] == 0:
                # инициализируем диапазон (заполнять большой диапазон может быть долго — можно оптимизировать)
                mem_data = [(addr, "000000") for addr in range(self.MIN_ADDR, self.MAX_ADDR + 1)]
                cur.executemany('INSERT INTO memory (address, value) VALUES (?, ?)', mem_data)
            conn.commit()

    # --- registers (POH) ---
    def get_register_value(self, reg_num):
        with self.get_connection() as conn:
            cur = conn.execute('SELECT value FROM POH WHERE reg_num = ?', (reg_num,))
            row = cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def set_register_value(self, reg_num, value):
        v = int(value) & 0xFFFF
        with self.get_connection() as conn:
            conn.execute('UPDATE POH SET value = ? WHERE reg_num = ?', (v, reg_num))
            conn.commit()
        if self.debug:
            print(f"[DB][REG] R{reg_num} <- {oct(v)} (dec={v})")

    # --- memory ---
    def validate_address(self, address):
        if not (self.MIN_ADDR <= address <= self.MAX_ADDR):
            raise ValueError(f"Адрес {oct(address)} вне допустимого диапазона {oct(self.MIN_ADDR)}-{oct(self.MAX_ADDR)}")

    def get_memory_value(self, address):
        self.validate_address(address)
        with self.get_connection() as conn:
            cur = conn.execute('SELECT value FROM memory WHERE address = ?', (address,))
            row = cur.fetchone()
            if not row or row[0] is None:
                return "000000"
            s = str(row[0]).strip()
            # нормализуем: если '0' — возвращаем '0' (маркер), иначе 6-digit octal
            if s == '0':
                return '0'
            # если в базе хранится число-строка, гарантируем 6-digit
            if all(ch in '01234567' for ch in s):
                return s.zfill(6)
            # если там неожиданно десятичное число — попытаемся привести
            try:
                iv = int(s)
                return f"{iv & 0xFFFF:06o}"
            except Exception:
                return "000000"

    def set_memory_value(self, address, value):
        self.validate_address(address)
        # value может быть int либо oct-string либо '0'
        if isinstance(value, int):
            sval = f"{value & 0xFFFF:06o}"
        else:
            s = str(value).strip()
            if s == '0':
                sval = '0'
            elif all(ch in '01234567' for ch in s):
                sval = s.zfill(6)
            else:
                # пробуем int как decimal fallback
                try:
                    iv = int(s)
                    sval = f"{iv & 0xFFFF:06o}"
                except Exception:
                    sval = '000000'
        with self.get_connection() as conn:
            conn.execute('UPDATE memory SET value = ? WHERE address = ?', (sval, address))
            conn.commit()
        if self.debug:
            print(f"[DB][MEM] {oct(address)} <- {sval}")
