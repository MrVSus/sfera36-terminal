from PySide2.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QLineEdit
)
from PySide2.QtGui import QFont, QTextCursor, QTextOption
from PySide2.QtCore import Qt


class TerminalPage(QWidget):
    def __init__(self, cpu, prompt="> ", parent=None):
        super().__init__(parent)
        self.cpu = cpu
        self.prompt = prompt
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

        # запоминаем последний контекст (ячейка или регистр)
        self.last_addr = None
        self.last_reg = None

        # применяем тему
        self.apply_theme()

        # заполняем пустыми строками
        self._fill_with_empty_lines()

    # ---------- обработка команд ----------
    def process_command(self):
        command = self.input_line.text().strip()
        if not command:
            # пустая строка → line feed
            self.line_feed()
            return

        # выводим команду в терминал (эха-ввод)
        self._append_command(f"> {command}")

        try:
            self.handle_command(command)
        except Exception as e:
            self._append_command(f"Ошибка: {e}")

        # добавляем приглашение для следующего ввода
        self._append_command(self.prompt)

        self.input_line.clear()


    def handle_command(self, command: str):
        cmd = command.strip().upper()

        # запись в память XXXX/VAL
        if "/" in cmd and cmd[0].isdigit() and not cmd.endswith("/"):
            addr_str, val_str = cmd.split("/")
            addr = int(addr_str, 8)
            val = int(val_str, 8)
            if addr > 0o157776:
                self._append_command("BUS ERROR")
                return
            self.cpu._mem_write_word(addr, val)
            self.last_addr = addr
            self.last_reg = None
            return

        # запись в регистр RX/VAL
        if cmd.startswith("R") and "/" in cmd and not cmd.endswith("/"):
            reg_str, val_str = cmd.split("/")
            val = int(val_str, 8)
            self.cpu.set_register(reg_str, val)
            self.last_reg = int(reg_str[1:])
            self.last_addr = None
            return

        # чтение регистра RX/
        if cmd.endswith("/") and cmd.startswith("R") and cmd[1:-1].isdigit():
            reg_name = cmd[:-1]
            value = self.cpu.get_register(reg_name)
            # сначала сам запрос
            # self._append_command(f"{reg_name}/")
            # потом результат
            self._append_command(f"{value:06o}")
            self.last_reg = int(reg_name[1:])
            self.last_addr = None
            return

        # чтение памяти XXXX/
        if cmd.endswith("/") and cmd[0].isdigit():
            addr = int(cmd[:-1], 8)
            if addr > 0o157776:
                self._append_command("BUS ERROR")
                return
            value = self.cpu._mem_read_word(addr)
            self._append_command(f"{value:06o}")
            self.last_addr = addr
            self.last_reg = None
            return

        # запуск XXXXG
        if cmd.endswith("G") and cmd[:-1].isdigit():
            addr = int(cmd[:-1], 8)
            if addr > 0o157776:
                self._append_command("BUS ERROR")
                return
            self.cpu._set_pc(addr)
            out = self.cpu._run_program()
            if out:
                self._append_command(out)
            self.last_addr = None
            self.last_reg = None
            return

        self._append_command("Неизвестная команда")

    # ---------- line feed ----------
    def line_feed(self):
        if self.last_addr is not None:
            next_addr = self.last_addr + 2
            if next_addr > 0o157776:
                self._append_command("BUS ERROR")
                return
            value = self.cpu._mem_read_word(next_addr)
            self._append_command(f"{next_addr:06o}/")
            self._append_command(f"{value:06o}")
            self.last_addr = next_addr
        elif self.last_reg is not None:
            next_reg = (self.last_reg + 1) % 8
            value = self.cpu.get_register(f"R{next_reg}")
            self._append_command(f"R{next_reg}/")
            self._append_command(f"{value:06o}")
            self.last_reg = next_reg
        else:
            self._append_command("")
        self._append_command(self.prompt)

    # ---------- вывод ----------
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
