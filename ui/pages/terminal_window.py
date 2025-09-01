from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QLineEdit
)
from PySide6.QtGui import QFont, QTextCursor, QTextOption
from PySide6.QtCore import Qt


class TerminalPage(QWidget):
    def __init__(self, cpu, parent=None):
        super().__init__(parent)
        self.cpu = cpu
        self.dark_mode = True

        # фиксированный размер окна
        self.setFixedSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Терминал (история) ---
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 12))
        self.terminal.setWordWrapMode(QTextOption.NoWrap)
        layout.addWidget(self.terminal)

        # --- Поле ввода ---
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Consolas", 12))
        self.input_line.returnPressed.connect(self.process_command)

        layout.addWidget(self.input_line)

        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        self.btn_show_manip = QPushButton("Показать манипулятор")
        self.btn_show_flags = QPushButton("Показать слово состояния процессора")
        self.btn_theme = QPushButton("Сменить тему")
        btn_layout.addWidget(self.btn_show_manip)
        btn_layout.addWidget(self.btn_show_flags)
        btn_layout.addWidget(self.btn_theme)
        layout.addLayout(btn_layout)

        self.btn_theme.clicked.connect(self.toggle_theme)

        # история
        self.history = []
        self.max_lines = 25

        # применяем тему
        self.apply_theme()

        # заполняем пустыми строками
        self._fill_with_empty_lines()

    # ---------- обработка команд ----------
    def process_command(self):
        command = self.input_line.text().strip()
        if not command:
            return

        # выводим команду в терминал
        self._append_command(f"> {command}")

        try:
            self.handle_command(command)
        except Exception:
            pass

        self.input_line.clear()

    def handle_command(self, command: str):
        cmd = command.strip().upper()

        # запись в память XXXX/VAL
        if "/" in cmd and cmd[0].isdigit() and not cmd.endswith("/"):
            addr_str, val_str = cmd.split("/")
            addr = int(addr_str, 8)
            val = int(val_str, 8)
            self.cpu._mem_write_word(addr, val)
            return

        # запись в регистр RX/VAL
        if cmd.startswith("R") and "/" in cmd and not cmd.endswith("/"):
            reg_str, val_str = cmd.split("/")
            val = int(val_str, 8)
            self.cpu.set_register(reg_str, val)
            return

        # чтение регистра RX/
        if cmd.endswith("/") and cmd.startswith("R") and cmd[1:-1].isdigit():
            reg_name = cmd[:-1]
            value = self.cpu.get_register(reg_name)
            self._append_command(f"{value:06o}")
            return

        # чтение памяти XXXX/
        if cmd.endswith("/") and cmd[0].isdigit():
            addr = int(cmd[:-1], 8)
            value = self.cpu._mem_read_word(addr)
            self._append_command(f"{value:06o}")
            return

        # запуск XXXXG
        if cmd.endswith("G") and cmd[:-1].isdigit():
            addr = int(cmd[:-1], 8)
            self.cpu._set_pc(addr)
            self.cpu._run_program()
            return


    def _append_command(self, text: str):
        self.history.append(text)

        while len(self.history) < self.max_lines:
            self.history.insert(0, "")

        if len(self.history) > self.max_lines:
            self.history = self.history[-self.max_lines:]

        self.terminal.setPlainText("\n".join(self.history))

        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)

    def _fill_with_empty_lines(self):
        self.history = [""] * self.max_lines
        self.terminal.setPlainText("\n".join(self.history))
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)

    # ---------- темы ----------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.terminal.setStyleSheet("background-color: black; color: lime; border:none; margin:0; padding:0;")
            self.input_line.setStyleSheet("background-color: black; color: lime; border:none; margin:0; padding:0;")
        else:
            self.terminal.setStyleSheet("background-color: white; color: black; border:none; margin:0; padding:0;")
            self.input_line.setStyleSheet("background-color: white; color: black; border:none; margin:0; padding:0;")
