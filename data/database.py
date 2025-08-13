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

    def _ensure_db_exists(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS POH (
                reg_num INTEGER PRIMARY KEY CHECK(reg_num BETWEEN 0 AND 7),
                value INTEGER DEFAULT 0
            )
            ''')
            cursor.execute('SELECT COUNT(*) FROM POH')
            if cursor.fetchone()[0] == 0:
                cursor.executemany('INSERT INTO POH (reg_num, value) VALUES (?, ?)', [(i, 0) for i in range(8)])

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS memory (
                address INTEGER PRIMARY KEY,
                value TEXT
            )
            ''')
            cursor.execute('SELECT COUNT(*) FROM memory')
            if cursor.fetchone()[0] == 0:
                mem_data = [(addr, '0') for addr in range(self.MIN_ADDR, self.MAX_ADDR + 1, 2)]
                cursor.executemany('INSERT INTO memory (address, value) VALUES (?, ?)', mem_data)
                conn.commit()

            # Нормализация уже существующих записей (попытка привести неоктальные строки в октальный вид)
            cursor.execute('SELECT address, value FROM memory')
            rows = cursor.fetchall()
            for addr, raw in rows:
                if raw is None:
                    new = '0'
                else:
                    s = str(raw).strip()
                    if s == '0':
                        new = '0'
                    elif all(ch in '01234567' for ch in s):
                        new = s.zfill(6)
                    else:
                        # попробуем трактовать как десятичное число и преобразовать в октальное
                        try:
                            intval = int(s)
                            new = '0' if intval == 0 else f"{intval & 0xFFFF:06o}"
                        except Exception:
                            new = s
                if new != str(raw):
                    cursor.execute('UPDATE memory SET value = ? WHERE address = ?', (new, addr))
            conn.commit()

    def validate_address(self, address):
        if not (self.MIN_ADDR <= address <= self.MAX_ADDR):
            raise ValueError(f"Адрес {oct(address)} вне допустимого диапазона {oct(self.MIN_ADDR)}-{oct(self.MAX_ADDR)}")

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    # POH R0..R7
    def get_register_value(self, reg_num):
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT value FROM POH WHERE reg_num = ?', (reg_num,))
            res = cursor.fetchone()
            return res[0] if res else 0

    def set_register_value(self, reg_num, value):
        with self.get_connection() as conn:
            conn.execute('UPDATE POH SET value = ? WHERE reg_num = ?', (int(value) & 0xFFFF, reg_num))
            conn.commit()
        if self.debug:
            print(f"[DB][REG] R{reg_num} <- {int(value) & 0xFFFF:o}")

    # Memory
    def get_memory_value(self, address):
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT value FROM memory WHERE address = ?', (address,))
            res = cursor.fetchone()
            return res[0] if res else '0'

    def set_memory_value(self, address, value):
        """
        value: int or string.
        Store normalized:
         - '0' for zero
         - otherwise 6-digit octal string '005131'
        """
        if isinstance(value, int):
            valstr = '0' if value == 0 else f"{value & 0xFFFF:06o}"
        else:
            s = str(value).strip()
            if s == '0':
                valstr = '0'
            elif all(ch in '01234567' for ch in s):
                valstr = s.zfill(6)
            else:
                try:
                    intval = int(s)
                    valstr = '0' if intval == 0 else f"{intval & 0xFFFF:06o}"
                except Exception:
                    valstr = s

        with self.get_connection() as conn:
            conn.execute('INSERT OR REPLACE INTO memory (address, value) VALUES (?, ?)', (address, valstr))
            conn.commit()

        if self.debug:
            print(f"[DB][MEM] {address:o} <- {valstr}")

    # Debug helper: dump several addresses
    def dump_addresses(self, addrs):
        out = []
        with self.get_connection() as conn:
            for a in addrs:
                cur = conn.execute('SELECT value FROM memory WHERE address = ?', (a,))
                row = cur.fetchone()
                raw = row[0] if row else None
                try:
                    intval = int(raw, 8) if raw and raw != '0' else 0
                except Exception:
                    intval = None
                out.append((a, raw, intval))
        return out
