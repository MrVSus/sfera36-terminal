import sqlite3
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or str(Path(__file__).parent.parent / 'data' / 'migrations' / 'db.db')
        self._ensure_db_exists()
        self.MIN_ADDR = 0o1000  # Минимальный адрес (1000 в восьмеричной)
        self.MAX_ADDR = 0o157777  # Максимальный адрес (157777 в восьмеричной)

    def _ensure_db_exists(self):
        """Создаёт таблицы с правильными ограничениями"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица для R0-R6 (обычные регистры)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS registers (
                reg_num INTEGER PRIMARY KEY CHECK(reg_num BETWEEN 0 AND 6),
                value INTEGER DEFAULT 0
            )
            ''')
            
            # Таблица для хранения состояния R7 (программный счётчик)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_counter (
                id INTEGER PRIMARY KEY CHECK(id = 0),
                value INTEGER DEFAULT 0
            )
            ''')
            
            # Инициализация регистров
            cursor.execute('SELECT COUNT(*) FROM registers')
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    'INSERT INTO registers (reg_num, value) VALUES (?, ?)',
                    [(i, 0) for i in range(7)]  # R0-R6
                )
                cursor.execute('INSERT OR IGNORE INTO program_counter (id, value) VALUES (0, 0)')
            
            conn.commit()

    def validate_address(self, address):
        """Проверяет, что адрес в допустимом диапазоне"""
        if not (self.MIN_ADDR <= address <= self.MAX_ADDR):
            raise ValueError(f"Адрес {oct(address)} вне допустимого диапазона "
                           f"{oct(self.MIN_ADDR)}-{oct(self.MAX_ADDR)}")

    def get_connection(self):
        """Возвращает соединение с БД"""
        return sqlite3.connect(self.db_path)

    def get_register_value(self, reg_num):
        """Читает значение регистра (1-8 для R0-R7)"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT Value FROM POH WHERE RegNum = ?',
                (reg_num,)
            )
            result = cursor.fetchone()
            return result[0] if result else 0

    def set_register_value(self, reg_num, value):
        """Устанавливает значение регистра"""
        with self.get_connection() as conn:
            conn.execute(
                'UPDATE POH SET Value = ? WHERE RegNum = ?',
                (value, reg_num)
            )
            conn.commit()

    def get_memory_value(self, address):
        """Читает значение из памяти"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT value FROM registers WHERE address = ?',
                (address,)
            )
            result = cursor.fetchone()
            return result[0] if result else '0'

    def set_memory_value(self, address, value):
        """Записывает значение в память"""
        with self.get_connection() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO registers (address, value) VALUES (?, ?)',
                (address, str(value))
            )
            conn.commit()