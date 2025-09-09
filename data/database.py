# data/database.py
import sqlite3
from pathlib import Path
from typing import Tuple, Optional


class DatabaseManager:
    MIN_ADDR = 0o1000

    def __init__(self, db_path: Optional[str] = None, debug: bool = False):
        default = str(Path(__file__).parent.parent / 'data' / 'migrations' / 'db.db')
        self.db_path = db_path or default
        self.debug = debug

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        need_init = not Path(self.db_path).exists()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self._ensure_schema()
        self._ensure_registers()
        self._ensure_lowpage()

        if need_init and self.debug:
            print("[DatabaseManager] created DB at", self.db_path)

    def _ensure_schema(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_bytes(
                addr_even INTEGER PRIMARY KEY,
                hi TEXT NOT NULL CHECK(length(hi)=8),
                lo TEXT NOT NULL CHECK(length(lo)=8)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registers(
                reg INTEGER PRIMARY KEY CHECK(reg BETWEEN 0 AND 7),
                value INTEGER NOT NULL CHECK(value BETWEEN 0 AND 65535)
            );
        """)
        self.conn.commit()

    def _ensure_registers(self):
        cur = self.conn.cursor()
        for r in range(8):
            cur.execute(
                "INSERT INTO registers(reg, value) VALUES(?, ?) "
                "ON CONFLICT(reg) DO UPDATE SET value=COALESCE(registers.value, excluded.value);",
                (r, 0)
            )
        self.conn.commit()

    def _ensure_lowpage(self):
        base = int(self.MIN_ADDR)
        end = base + int(0o1777)
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM memory_bytes WHERE addr_even BETWEEN ? AND ? LIMIT 1;", (base, end))
        if cur.fetchone() is None:
            rows = []
            a = base & ~1
            while a <= end:
                rows.append((a, '00000000', '00000000'))
                a += 2
            cur.executemany("INSERT OR IGNORE INTO memory_bytes(addr_even, hi, lo) VALUES(?, ?, ?);", rows)
            self.conn.commit()
            if self.debug:
                print(f"[DatabaseManager] Initialized lowpage {base:o}..{end:o}")

    # helpers
    @staticmethod
    def _to_bin8(v: int) -> str:
        return f"{v & 0xFF:08b}"

    @staticmethod
    def _from_bin8(s: str) -> int:
        return int(s, 2) & 0xFF

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
            raise ValueError("Address out of range")

    # registers
    def get_register_value(self, reg_num: int) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM registers WHERE reg=?;", (int(reg_num),))
        r = cur.fetchone()
        return int(r['value']) & 0xFFFF if r else 0

    def set_register_value(self, reg_num: int, value: int):
        v = int(value) & 0xFFFF
        self.conn.execute(
            "INSERT INTO registers(reg, value) VALUES(?, ?) "
            "ON CONFLICT(reg) DO UPDATE SET value=excluded.value;",
            (int(reg_num), v)
        )
        self.conn.commit()

    # low-level memory
    def _ensure_row(self, addr_even: int):
        a = int(addr_even) & ~1
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM memory_bytes WHERE addr_even=?;", (a,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO memory_bytes(addr_even, hi, lo) VALUES(?, '00000000', '00000000');", (a,))
            self.conn.commit()

    def get_memory_bytes(self, addr_even: int) -> Tuple[int, int]:
        a = int(addr_even) & ~1
        self.validate_address(a)
        cur = self.conn.cursor()
        cur.execute("SELECT hi, lo FROM memory_bytes WHERE addr_even=?;", (a,))
        row = cur.fetchone()
        if row is None:
            return 0, 0
        return self._from_bin8(row['hi']), self._from_bin8(row['lo'])

    def set_memory_bytes(self, addr_even: int, hi: int, lo: int):
        a = int(addr_even) & ~1
        self.validate_address(a)
        self._ensure_row(a)
        self.conn.execute(
            "UPDATE memory_bytes SET hi=?, lo=? WHERE addr_even=?;",
            (self._to_bin8(int(hi) & 0xFF), self._to_bin8(int(lo) & 0xFF), a)
        )
        self.conn.commit()

    def get_word(self, addr_even: int) -> int:
        hi, lo = self.get_memory_bytes(addr_even)
        return ((hi << 8) | lo) & 0xFFFF

    def set_word(self, addr_even: int, value: int):
        hi = (int(value) >> 8) & 0xFF
        lo = int(value) & 0xFF
        self.set_memory_bytes(addr_even, hi, lo)

    def get_byte(self, addr: int) -> int:
        a = int(addr) & 0xFFFF
        base = a & ~1
        hi, lo = self.get_memory_bytes(base)
        return hi if (a & 1) else lo

    def set_byte(self, addr: int, value: int):
        a = int(addr) & 0xFFFF
        base = a & ~1
        hi, lo = self.get_memory_bytes(base)
        if a & 1:
            hi = int(value) & 0xFF
        else:
            lo = int(value) & 0xFF
        self.set_memory_bytes(base, hi, lo)

    # compatibility
    def get_memory_value(self, addr_even: int) -> str:
        return self._oct6(self.get_word(addr_even))

    def set_memory_value(self, addr_even: int, sval: str):
        v = self._parse_oct6(sval)
        self.set_word(addr_even, v)
