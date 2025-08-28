from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QLineEdit
)
from PySide6.QtGui import QFont, QTextCursor, QTextOption, QKeyEvent
from PySide6.QtCore import Qt


class TerminalPage(QWidget):
    def __init__(self, cpu, parent=None):
        super().__init__(parent)
        self.cpu = cpu
        self.dark_mode = True

        # фиксированный размер окна
        self.setFixedSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # убираем внешние отступы
        layout.setSpacing(0)                   # убираем расстояния между элементами

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

        # стили: убираем верхнюю границу, чтобы "слилось"
        self.input_line.setStyleSheet("""
            QLineEdit {
                border: none;
            }
        """)

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

        # подключение кнопки смены темы
        self.btn_theme.clicked.connect(self.toggle_theme)

        # история команд
        self.history = []
        self.max_lines = 25

        # тёмная тема по умолчанию
        self.apply_theme()

        # заполняем пустыми строками для "старта снизу"
        self._fill_with_empty_lines()

    # ---------- обработка команд ----------
    def process_command(self):
        command = self.input_line.text().strip()
        if not command:
            return

        # показываем команду в терминале
        self._append_command(f"> {command}")

        # отправляем в CPU (результат не отображаем, как ты просил)
        try:
            self.cpu.execute(command)
        except Exception:
            pass

        self.input_line.clear()

    def _append_command(self, text: str):
        self.history.append(text)

        # ограничение по строкам
        while len(self.history) < self.max_lines:
            self.history.insert(0, "")

        if len(self.history) > self.max_lines:
            self.history = self.history[-self.max_lines:]

        self.terminal.setPlainText("\n".join(self.history))

        # курсор в конец
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
            self.terminal.setStyleSheet("background-color: black; color: lime;")
            self.input_line.setStyleSheet("background-color: black; color: lime;")
        else:
            self.terminal.setStyleSheet("background-color: white; color: black;")
            self.input_line.setStyleSheet("background-color: white; color: black;")
