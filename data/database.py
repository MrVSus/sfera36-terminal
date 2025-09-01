# data/database.py
import os
import sqlite3
from pathlib import Path


class DatabaseManager:
    """
    SQLite-реализация памяти, где слово хранится как 2 байта:
      memory_bytes(addr_even INTEGER PRIMARY KEY, hi TEXT(8), lo TEXT(8))
    Совместимый API:
      - get_memory_value(addr_even) -> 'xxxxxx' (6-digit octal string)
      - set_memory_value(addr_even, 'xxxxxx')
    Низкоуровневые:
      - get_word(addr_even) / set_word(addr_even, val)
      - get_byte(addr) / set_byte(addr, val)
    """

    MIN_ADDR = 0o1000  # окно низкой страницы (как в CPU)

    def __init__(self, db_path: str | None = None, debug: bool = False):
        # default path (как ты указывал ранее)
        default_path = str(Path(__file__).parent.parent / 'data' / 'migrations' / 'db.db')
        self.db_path = db_path or default_path
        self.debug = debug

        # ensure folder exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        need_init = not Path(self.db_path).exists()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._ensure_schema()

        # ensure registers 0..7 exist
        self._ensure_registers()

        # initialize lowpage window with zero words if absent
        # (this avoids missing rows for common student scenarios)
        self._ensure_lowpage_initialized()

        if need_init and self.debug:
            print(f"[DatabaseManager] Initialized new DB at {self.db_path}")

    # ---------------- schema ----------------
    def _ensure_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_bytes(
                addr_even INTEGER PRIMARY KEY,
                hi TEXT NOT NULL CHECK(length(hi)=8),
                lo TEXT NOT NULL CHECK(length(lo)=8)
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS registers(
                reg INTEGER PRIMARY KEY CHECK(reg BETWEEN 0 AND 7),
                value INTEGER NOT NULL CHECK(value BETWEEN 0 AND 65535)
            );
            """
        )
        self.conn.commit()

    # ---------------- helpers ----------------
    @staticmethod
    def _to_bin8(v: int) -> str:
        return f"{v & 0xFF:08b}"

    @staticmethod
    def _from_bin8(b: str) -> int:
        return int(b, 2) & 0xFF

    @staticmethod
    def _oct6(v: int) -> str:
        return f"{v & 0xFFFF:06o}"

    @staticmethod
    def _parse_oct6(s: str) -> int:
        ss = (s or "").strip()
        if ss == "" or ss == "0":
            return 0
        return int(ss, 8) & 0xFFFF

    def validate_address(self, addr: int):
        a = int(addr) & 0xFFFF
        if not (0 <= a <= 0xFFFF):
            raise ValueError(f"Адрес вне диапазона 16 бит: {addr}")

    # ---------------- registers ----------------
    def _ensure_registers(self):
        cur = self.conn.cursor()
        # insert missing registers 0..7 with zero
        for r in range(8):
            cur.execute(
                "INSERT INTO registers(reg, value) VALUES(?, ?) "
                "ON CONFLICT(reg) DO UPDATE SET value=COALESCE(value, excluded.value);",
                (r, 0),
            )
        self.conn.commit()

    def get_register_value(self, reg_num: int) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM registers WHERE reg=?;", (int(reg_num),))
        row = cur.fetchone()
        return int(row[0]) & 0xFFFF if row else 0

    def set_register_value(self, reg_num: int, value: int):
        v = int(value) & 0xFFFF
        self.conn.execute(
            "INSERT INTO registers(reg, value) VALUES(?, ?) "
            "ON CONFLICT(reg) DO UPDATE SET value=excluded.value;",
            (int(reg_num), v),
        )
        self.conn.commit()

    # ---------------- low-level memory (words/bytes) ----------------
    def _ensure_row(self, addr_even: int):
        a = int(addr_even) & ~1
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM memory_bytes WHERE addr_even=?;", (a,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO memory_bytes(addr_even, hi, lo) VALUES(?, '00000000', '00000000');",
                (a,),
            )
            self.conn.commit()

        # ---------------- low-level memory (words/bytes) ----------------
    def get_word(self, addr_even: int) -> int:
        """Читает слово (16 бит) по чётному адресу."""
        a = int(addr_even) & ~1
        self.validate_address(a)
        cur = self.conn.cursor()
        cur.execute("SELECT hi, lo FROM memory_bytes WHERE addr_even=?;", (a,))
        row = cur.fetchone()
        if row is None:
            return 0
        hi_b, lo_b = row
        hi = self._from_bin8(hi_b)
        lo = self._from_bin8(lo_b)
        return ((hi << 8) | lo) & 0xFFFF

    def set_word(self, addr_even: int, value: int):
        """Записывает слово (16 бит) по чётному адресу."""
        a = int(addr_even) & ~1
        self.validate_address(a)
        v = int(value) & 0xFFFF
        hi = (v >> 8) & 0xFF
        lo = v & 0xFF
        self._ensure_row(a)
        self.conn.execute(
            "UPDATE memory_bytes SET hi=?, lo=? WHERE addr_even=?;",
            (self._to_bin8(hi), self._to_bin8(lo), a),
        )
        self.conn.commit()

    def get_byte(self, addr: int) -> int:
        """Читает байт (8 бит) по любому адресу."""
        a = int(addr) & 0xFFFF
        self.validate_address(a)
        base = a & ~1
        cur = self.conn.cursor()
        cur.execute("SELECT hi, lo FROM memory_bytes WHERE addr_even=?;", (base,))
        row = cur.fetchone()
        if row is None:
            return 0
        hi_b, lo_b = row
        if a & 1:  # нечётный → старший байт
            return self._from_bin8(hi_b)
        else:      # чётный → младший байт
            return self._from_bin8(lo_b)

    def set_byte(self, addr: int, value: int):
        """Записывает байт (8 бит) по любому адресу."""
        a = int(addr) & 0xFFFF
        self.validate_address(a)
        v = int(value) & 0xFF
        base = a & ~1
        self._ensure_row(base)
        if a & 1:  # нечётный → старший байт
            self.conn.execute(
                "UPDATE memory_bytes SET hi=? WHERE addr_even=?;",
                (self._to_bin8(v), base),
            )
        else:      # чётный → младший байт
            self.conn.execute(
                "UPDATE memory_bytes SET lo=? WHERE addr_even=?;",
                (self._to_bin8(v), base),
            )
        self.conn.commit()


    # ---------------- compatibility layer (old API) ----------------
    def get_memory_value(self, addr_even: int) -> str:
        """
        Возвращает шестизначную октальную строку слова по чётному адресу.
        Если строки нет — возвращает '000000' (без специального '0'-маркер).
        """
        w = self.get_word(addr_even)
        return self._oct6(w)

    def set_memory_value(self, addr_even: int, sval: str):
        """
        Записывает слово по адресу в виде октальной строки (например '005177' или '0').
        При '0' записывается нулевое слово.
        """
        v = self._parse_oct6(sval)
        self.set_word(addr_even, v)

    # ---------------- initialize lowpage ----------------
    def _ensure_lowpage_initialized(self):
        """
        Создаём нулевые строки для окна низкой страницы:
        [MIN_ADDR .. MIN_ADDR+0o1777] (по словам, т.е. чётные адреса с шагом 2).
        Это предотвращает отсутствие строк и ложные HALT.
        """
        base = int(self.MIN_ADDR)
        end = base + int(0o1777)
        cur = self.conn.cursor()
        # проверим, есть ли хоть одна запись в этом диапазоне
        cur.execute("SELECT 1 FROM memory_bytes WHERE addr_even BETWEEN ? AND ? LIMIT 1;", (base, end))
        if cur.fetchone() is None:
            # вставляем строки по шагу 2 (чётные адреса)
            rows = []
            a = base & ~1
            while a <= end:
                rows.append((a, '00000000', '00000000'))
                a += 2
            cur.executemany("INSERT INTO memory_bytes(addr_even, hi, lo) VALUES(?, ?, ?);", rows)
            self.conn.commit()
            if self.debug:
                print(f"[DatabaseManager] Initialized lowpage rows {base:o}..{end:o}")
