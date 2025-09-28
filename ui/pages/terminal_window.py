from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QLineEdit
)
from PySide6.QtGui import QFont, QTextCursor, QTextOption


class TerminalPage(QWidget):
    def __init__(self, cpu, prompt="> ", parent=None):
        super().__init__(parent)
        self.cpu = cpu
        self.prompt = prompt
        self.dark_mode = True

        self.setFixedSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Терминал ---
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

        self.history = []
        self.max_lines = 25
        self.last_addr = None
        self.last_reg = None

        self.apply_theme()
        self._fill_with_empty_lines()

    # ---------- обработка команд ----------
    def process_command(self):
        command = self.input_line.text().strip()
        if not command:
            self.line_feed()
            return

        # показываем ввод
        self._append_line(f"> {command}")

        try:
            self.handle_command(command)
        except ValueError:
            # ошибка преобразования числа в восьмеричную
            self._append_line("???")
        except Exception:
            self._append_line("???")

        # приглашение на новой строке
        self._append_line(self.prompt)
        self.input_line.clear()

    def handle_command(self, command: str):
        cmd = command.strip().upper()

        # запись в память XXXX/VAL
        if "/" in cmd and cmd[0].isdigit() and not cmd.endswith("/"):
            try:
                addr_str, val_str = cmd.split("/")
                addr = int(addr_str, 8)
                val = int(val_str, 8)
            except Exception:
                self._append_line("???")
                return

            if addr > 0o157776:
                self._append_line("BUS ERROR")
                return
            old = self.cpu._mem_read_word(addr)
            self.cpu._mem_write_word(addr, val)
            self._append_line(f"{addr:06o}/{old:06o} {val:06o}")
            self.last_addr = addr
            self.last_reg = None
            return

        # запись в регистр RX/VAL
        if cmd.startswith("R") and "/" in cmd and not cmd.endswith("/"):
            try:
                reg_str, val_str = cmd.split("/")
                val = int(val_str, 8)
            except Exception:
                self._append_line("???")
                return

            old = self.cpu.get_register(reg_str)
            self.cpu.set_register(reg_str, val)
            self._append_line(f"{reg_str}/{old:06o} {val:06o}")
            self.last_reg = int(reg_str[1:])
            self.last_addr = None
            return

        # чтение регистра RX/
        if cmd.endswith("/") and cmd.startswith("R") and cmd[1:-1].isdigit():
            reg_name = cmd[:-1]
            value = self.cpu.get_register(reg_name)
            self._append_inline(f" {value:06o}")  # теперь в той же строке
            self.last_reg = int(reg_name[1:])
            self.last_addr = None
            return

        # чтение памяти XXXX/
        if cmd.endswith("/") and cmd[0].isdigit():
            try:
                addr = int(cmd[:-1], 8)
            except Exception:
                self._append_inline(" ???")
                return
            if addr > 0o157776:
                self._append_inline(" BUS ERROR")
                return
            value = self.cpu._mem_read_word(addr)
            self._append_inline(f" {value:06o}")  # теперь в той же строке
            self.last_addr = addr
            self.last_reg = None
            return

        # запуск XXXXG
        if cmd.endswith("G") and cmd[:-1].isdigit():
            try:
                addr = int(cmd[:-1], 8)
            except Exception:
                self._append_inline(" ???")
                return
            if addr > 0o157776:
                self._append_inline(" BUS ERROR")
                return
            self.cpu._set_pc(addr)
            self.cpu._run_program()
            r7 = self.cpu.get_register("R7")
            self._append_inline(f" {r7:06o}")  # теперь в той же строке
            self.last_addr = None
            self.last_reg = None
            return

        # чтение ССП
        if cmd == "RS/":
            value = self.cpu.db.get_psw()
            self._append_inline(f" {value:03o}")
            return

        self._append_line("Неизвестная команда")

    # ---------- line feed ----------
    def line_feed(self):
        if self.last_addr is not None:
            next_addr = self.last_addr + 2
            if next_addr > 0o157776:
                self._append_line("BUS ERROR")
                return
            value = self.cpu._mem_read_word(next_addr)
            self._append_line(f"{next_addr:06o}/ {value:06o}")
            self.last_addr = next_addr
        elif self.last_reg is not None:
            next_reg = (self.last_reg + 1) % 8
            value = self.cpu.get_register(f"R{next_reg}")
            self._append_line(f"R{next_reg}/ {value:06o}")
            self.last_reg = next_reg
        else:
            self._append_line("")

    # ---------- вывод ----------
    def _append_line(self, text: str):
        if text is None:
            return
        self.history.append(text)
        while len(self.history) > self.max_lines:
            self.history.pop(0)
        self._refresh_terminal()

    def _append_inline(self, text: str):
        """Дописывание к последней строке (например, результат после '> команда')"""
        if not self.history:
            self.history.append(text)
        else:
            self.history[-1] += text
        self._refresh_terminal()

    def _refresh_terminal(self):
        self.terminal.setPlainText("\n".join(self.history))
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)

    def _fill_with_empty_lines(self):
        self.history = ["" for _ in range(self.max_lines)]
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
