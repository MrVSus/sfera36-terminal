# terminal_window.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QPushButton,
    QHBoxLayout, QLineEdit, QLabel
)
from PySide6.QtGui import QFont, QTextCursor, QTextOption
from PySide6.QtCore import Qt, QTimer, QEvent
import re


class TerminalPage(QWidget):
    def __init__(self, cpu, prompt="> ", parent=None):
        super().__init__(parent)
        self.cpu = cpu
        self.prompt = prompt
        self.dark_mode = True

        self.setFixedSize(800, 600)

        # layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Терминал (история) ---
        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Consolas", 12))
        self.terminal.setWordWrapMode(QTextOption.NoWrap)
        layout.addWidget(self.terminal)

        # --- Поле ввода: метка prompt + QLineEdit ---
        input_area = QHBoxLayout()
        self.prompt_label = QLabel(self.prompt.strip())
        self.prompt_label.setFont(QFont("Consolas", 12))
        self.prompt_label.setFixedWidth(18)
        self.prompt_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Consolas", 12))
        self.input_line.returnPressed.connect(self.process_command)
        self.input_line.installEventFilter(self)
        self.input_line.setPlaceholderText("input here")

        input_area.addWidget(self.prompt_label)
        input_area.addWidget(self.input_line, 1)
        layout.addLayout(input_area)

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

        # state
        self.history = []           # список строк (старые в начале, новые в конце)
        self.max_lines = 25
        self.last_addr = None
        self.last_reg = None

        # prefill: None или dict {type:'mem'|'reg'|'psw', 'text':..., 'addr':..., 'reg':...}
        self._prefill = None
        # вспомогательная переменная — текст команды без "> " последнего эха
        self._last_echo_cmd = None

        # локальные регулярки
        self._re_mem_write = re.compile(r'^\s*([0-7]+)\s*/\s*([0-7]+)\s*$')
        self._re_mem_read  = re.compile(r'^\s*([0-7]+)\s*/\s*$')
        self._re_reg_write = re.compile(r'^\s*[Rr]([0-7])\s*/\s*([0-7]+)\s*$')
        self._re_reg_read  = re.compile(r'^\s*[Rr]([0-7])\s*/\s*$')
        self._re_exec_at   = re.compile(r'^\s*([0-7]+)\s*[Gg]\s*$')
        self._re_psw_write = re.compile(r'^\s*[Rr][Ss]\s*/\s*([0-7]+)\s*$')
        self._re_psw_read  = re.compile(r'^\s*[Rr][Ss]\s*/\s*$', re.IGNORECASE)

        # apply theme and initial state
        self.apply_theme()
        self._fill_with_empty_lines()

        # focus & blinking prompt (color blink)
        self.input_line.setFocus()
        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_prompt)
        self._blink_timer.start(500)

    # ---------- визуал: мигание ">" (сменой цвета) ----------
    def _blink_prompt(self):
        self._blink_state = not self._blink_state
        if self.dark_mode:
            fg = "lime" if self._blink_state else "black"
            bg = "black"
        else:
            fg = "black" if self._blink_state else "white"
            bg = "white"
        # устанавливаем цвет и фон чтобы не было "серого" эффекта
        self.prompt_label.setStyleSheet(f"color:{fg}; background-color:{bg};")

    # ---------- утилиты для истории ----------
    def _trim_history(self):
        if len(self.history) > self.max_lines:
            self.history = self.history[-self.max_lines:]

    def _refresh_terminal(self):
        """Показываем историю так, чтобы последние строки были у нижней границы."""
        pad_lines = max(0, self.max_lines - len(self.history))
        buffer = [""] * pad_lines + self.history
        self.terminal.setPlainText("\n".join(buffer))
        cursor = self.terminal.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.terminal.setTextCursor(cursor)

    def _append_echo(self, cmd_text: str):
        """Добавляет эхо-команду > cmd_text в историю."""
        line = f"> {cmd_text}"
        # не добавляем, если она уже последний элемент (точь-в-точь)
        if self.history and self.history[-1].strip() == line.strip():
            # обновим _last_echo_cmd для дальнейшего inline
            self._last_echo_cmd = cmd_text
            return
        self.history.append(line)
        self._trim_history()
        self._last_echo_cmd = cmd_text
        self._refresh_terminal()

    def _append_line(self, text: str):
        """Добавляет новую независимую строку (результат программы и т.п.), без '>'."""
        if not text or text.strip() == "":
            return
        t = str(text).rstrip()
        # избегаем дублирования подряд одинаковых строк
        if self.history and self.history[-1].strip() == t.strip():
            return
        self.history.append(t)
        self._trim_history()
        self._refresh_terminal()

    def _append_inline(self, inline_part: str):
        """Дописать результат в ту же строку-эхо.
        inline_part должен начинаться с пробела, если нужен пробел между командой и результатом,
        или быть пустым, например " 000123" или " BUS ERROR"."""
        if not self.history:
            # если нет эха — просто добавить отдельную строку
            self.history.append(inline_part.strip())
            self._trim_history()
            self._refresh_terminal()
            return

        last = self.history[-1]
        # если последняя строка — эхо, формируем заново
        if last.startswith(">"):
            base = self._last_echo_cmd or last[2:].strip()
            # ensure inline_part begins with space
            if not inline_part.startswith(" "):
                inline_part = " " + inline_part
            new_line = f"> {base}{inline_part}"
            self.history[-1] = new_line
        else:
            # иначе добавляем отдельной строкой
            self.history.append(inline_part.strip())
        self._trim_history()
        self._refresh_terminal()

    def _replace_last_with_echo(self, text_without_prefix: str):
        """Заменяет последнюю строку (обычно эхо) на финальную строку с '>'."""
        if not text_without_prefix:
            return
        line = f"> {text_without_prefix.strip()}"
        if self.history:
            self.history[-1] = line
        else:
            self.history.append(line)
        self._trim_history()
        self._refresh_terminal()

    # ---------- обработка Enter ----------
    def process_command(self):
        raw = (self.input_line.text() or "")
        raw_stripped = raw.strip()

        # пустая строка — line feed
        if raw_stripped == "":
            self.line_feed()
            self.input_line.clear()
            self.input_line.setFocus()
            return

        # подправим числа в командной строке (заполнение нулями)
        formatted = self._pad_numbers(raw)

        # сначала добавляем эхо (строка '> ...'), затем в обработчиках будем дописывать/заменять
        self._append_echo(formatted)

        # если был prefill (мы ранее вставили "<addr>/<value> " в input)
        if self._prefill:
            self._handle_prefill(formatted)
            self.input_line.clear()
            self.input_line.setFocus()
            return

        # обычная команда
        try:
            self._handle_command_text(formatted)
        except ValueError:
            # синтаксическая/числовая ошибка -> показать рядом с командой
            self._append_inline(" ???")
        except Exception:
            self._append_inline(" ???")

        self.input_line.clear()
        self.input_line.setFocus()

    # ---------- обработка клавиш '/' и 'G' (instant) ----------
    def eventFilter(self, obj, event):
        if obj is self.input_line and event.type() == QEvent.KeyPress:
            k = event.text()
            # instant read on '/'
            if k == "/":
                cur = (self.input_line.text() or "").strip()
                # register read
                mreg = re.match(r'^[Rr]([0-7])$', cur)
                if mreg:
                    reg_idx = int(mreg.group(1))
                    val = self.cpu.get_register(f"R{reg_idx}")
                    pre = f"R{reg_idx}/{val:06o}"
                    self._prefill = {'type': 'reg', 'text': pre, 'reg': reg_idx}
                    self.input_line.setText(f"{pre} ")
                    self.input_line.setCursorPosition(len(self.input_line.text()))
                    return True
                # memory read
                if re.match(r'^[0-7]+$', cur):
                    try:
                        addr = int(cur, 8)
                    except Exception:
                        self._append_line("???")
                        self.input_line.clear()
                        return True
                    max_addr = int('157776', 8)
                    if addr > max_addr:
                        self._append_line("BUS ERROR")
                        self.input_line.clear()
                        return True
                    val = self.cpu._mem_read_word(addr)
                    pre = f"{addr:06o}/{val:06o}"
                    self._prefill = {'type': 'mem', 'text': pre, 'addr': addr}
                    self.input_line.setText(f"{pre} ")
                    self.input_line.setCursorPosition(len(self.input_line.text()))
                    return True
                # PSW
                if cur.upper() == "RS":
                    val = self.cpu.db.get_psw()
                    pre = f"RS/{val:03o}"
                    self._prefill = {'type': 'psw', 'text': pre}
                    self.input_line.setText(f"{pre} ")
                    self.input_line.setCursorPosition(len(self.input_line.text()))
                    return True
                # otherwise let the '/' be inserted
                return False

            # instant run on 'G' (without Enter)
            if k.upper() == "G":
                cur = (self.input_line.text() or "").strip()
                if re.match(r'^[0-7]+$', cur):
                    try:
                        addr = int(cur, 8)
                    except Exception:
                        self._append_line("???")
                        self.input_line.clear()
                        return True
                    max_addr = int('157776', 8)
                    if addr > max_addr:
                        self._append_line("BUS ERROR")
                        self.input_line.clear()
                        return True
                    # run immediately
                    self.cpu._set_pc(addr)
                    out = self.cpu._run_program()
                    r7 = self.cpu.get_register("R7")
                    # show echo+R7 inline (we didn't call process_command, so add echo here)
                    self._append_echo(f"{addr:06o}G {r7:06o}")
                    if out:
                        for line in out.splitlines():
                            self._append_line(line)
                    self.input_line.clear()
                    return True
                return False

        return super().eventFilter(obj, event)

    # ---------- prefill handling (Enter after prefill) ----------
    def _handle_prefill(self, formatted_text: str):
        pre = self._prefill
        if not pre:
            return

        # formatted_text содержит всё, что было в input при Enter (числа уже подправлены)
        # ищем хвост после pre['text']
        text = formatted_text
        if pre['text'] not in text:
            # если начало изменено — просто treat as read (no write)
            if pre['type'] == 'mem':
                self.last_addr = pre.get('addr')
                self.last_reg = None
            elif pre['type'] == 'reg':
                self.last_reg = pre.get('reg')
                self.last_addr = None
            self._prefill = None
            return

        # rest — часть после pre['text']
        idx = text.index(pre['text']) + len(pre['text'])
        rest = text[idx:].strip()

        # если нет нового значения — чтение (оставляем last)
        if rest == "":
            if pre['type'] == 'mem':
                self.last_addr = pre.get('addr')
                self.last_reg = None
            elif pre['type'] == 'reg':
                self.last_reg = pre.get('reg')
                self.last_addr = None
            self._prefill = None
            return

        # есть новое значение — пытаемся записать (восьмеричное)
        try:
            ival = int(rest, 8)
        except Exception:
            self._append_inline(" ???")
            self._prefill = None
            return

        if pre['type'] == 'mem':
            addr = pre['addr']
            old_word = self.cpu._mem_read_word(addr & ~1)
            if (addr & 1) == 0:
                self.cpu._mem_write_word(addr, ival)
            else:
                self.cpu._mem_write_byte(addr, ival & 0xFF)
            new_word = self.cpu._mem_read_word(addr & ~1)
            # заменяем последнюю эхо-строку на итоговую
            self._replace_last_with_echo(f"{addr:06o}/{old_word:06o} {new_word:06o}")
            self.last_addr = addr
            self.last_reg = None

        elif pre['type'] == 'reg':
            reg = pre['reg']
            old = self.cpu.get_register(f"R{reg}")
            self.cpu.set_register(f"R{reg}", ival)
            new = self.cpu.get_register(f"R{reg}")
            self._replace_last_with_echo(f"R{reg}/{old:06o} {new:06o}")
            self.last_reg = reg
            self.last_addr = None

        elif pre['type'] == 'psw':
            old = self.cpu.db.get_psw()
            self.cpu.db.set_psw(ival & 0xFF)
            new = self.cpu.db.get_psw()
            self._replace_last_with_echo(f"RS/{old:03o} {new:03o}")

        self._prefill = None

    # ---------- помощник: дополняем числа до 6 разрядов ----------
    def _pad_numbers(self, text: str) -> str:
        def pad(m):
            num = m.group(0)
            try:
                n = int(num, 8)
                return f"{n:06o}"
            except Exception:
                return num
        # только группы цифр (1..6) в восьмеричной
        return re.sub(r'\b[0-7]{1,6}\b', pad, text)

    # ---------- разбор и выполнение команд (Enter) ----------
    def _handle_command_text(self, raw: str):
        s = raw.strip()

        # REG_READ -> inline result
        m = self._re_reg_read.match(s)
        if m:
            reg = int(m.group(1))
            value = self.cpu.get_register(f"R{reg}")
            self._append_inline(f" {value:06o}")
            self.last_reg = reg
            self.last_addr = None
            return

        # MEM_READ -> inline result (word or byte)
        m = self._re_mem_read.match(s)
        if m:
            addr = int(m.group(1), 8)
            max_addr = int('157776', 8)
            if addr > max_addr:
                self._append_inline(" BUS ERROR")
                return
            if (addr & 1) == 0:
                v = self.cpu._mem_read_word(addr)
                self._append_inline(f" {v:06o}")
            else:
                v = self.cpu._mem_read_byte(addr)
                self._append_inline(f" {v:03o}")
            self.last_addr = addr
            self.last_reg = None
            return

        # EXEC_AT -> append R7 inline and program output as separate lines
        m = self._re_exec_at.match(s)
        if m:
            addr = int(m.group(1), 8)
            max_addr = int('157776', 8)
            if addr > max_addr:
                self._append_inline(" BUS ERROR")
                return
            self.cpu._set_pc(addr)
            out = self.cpu._run_program()
            r7 = self.cpu.get_register("R7")
            self._append_inline(f" {r7:06o}")
            if out:
                for line in out.splitlines():
                    self._append_line(line)
            self.last_addr = None
            self.last_reg = None
            return

        # PSW_READ
        if self._re_psw_read.match(s):
            val = self.cpu.db.get_psw()
            self._append_inline(f" {val:03o}")
            return

        # MEM_WRITE (full command) -> replace last echo with final result
        m = self._re_mem_write.match(s)
        if m:
            addr = int(m.group(1), 8)
            sval = m.group(2)
            try:
                ival = int(sval, 8)
            except Exception:
                self._append_inline(" ???")
                return
            max_addr = int('157776', 8)
            if addr > max_addr:
                self._replace_last_with_echo(f"{addr:06o} BUS ERROR")
                return
            old_word = self.cpu._mem_read_word(addr & ~1)
            if sval == '0':
                self.cpu._mem_write_word(addr & ~1, 0)
            else:
                if (addr & 1) == 0:
                    self.cpu._mem_write_word(addr, ival)
                else:
                    self.cpu._mem_write_byte(addr, ival & 0xFF)
            new_word = self.cpu._mem_read_word(addr & ~1)
            self._replace_last_with_echo(f"{addr:06o}/{old_word:06o} {new_word:06o}")
            self.last_addr = addr
            self.last_reg = None
            return

        # REG_WRITE
        m = self._re_reg_write.match(s)
        if m:
            reg = int(m.group(1))
            sval = m.group(2)
            try:
                ival = int(sval, 8)
            except Exception:
                self._append_inline(" ???")
                return
            old = self.cpu.get_register(f"R{reg}")
            self.cpu.set_register(f"R{reg}", ival)
            new = self.cpu.get_register(f"R{reg}")
            self._replace_last_with_echo(f"R{reg}/{old:06o} {new:06o}")
            self.last_reg = reg
            self.last_addr = None
            return

        # PSW_WRITE
        m = self._re_psw_write.match(s)
        if m:
            try:
                val = int(m.group(1), 8)
            except Exception:
                self._append_inline(" ???")
                return
            old = self.cpu.db.get_psw()
            self.cpu.db.set_psw(val & 0xFF)
            new = self.cpu.db.get_psw()
            self._replace_last_with_echo(f"RS/{old:03o} {new:03o}")
            return

        # Unknown
        self._append_inline(" Неизвестная команда")

    # ---------- line feed ----------
    def line_feed(self):
        if self.last_addr is not None:
            next_addr = (self.last_addr + 2) & 0xFFFF
            max_addr = int('157776', 8)
            if next_addr > max_addr:
                self._append_line("BUS ERROR")
                return
            v = self.cpu._mem_read_word(next_addr)
            self._append_line(f"{next_addr:06o}/ {v:06o}")
            self.last_addr = next_addr
            self.last_reg = None
            return

        if self.last_reg is not None:
            next_reg = (self.last_reg + 1) % 8
            v = self.cpu.get_register(f"R{next_reg}")
            self._append_line(f"R{next_reg}/ {v:06o}")
            self.last_reg = next_reg
            self.last_addr = None
            return

        # nothing to do
        return

    # ---------- начальное заполнение истории ----------
    def _fill_with_empty_lines(self):
        self.history = []

    # ---------- темы ----------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode if False else not self.dark_mode  # compatibility
        self.apply_theme()

    def apply_theme(self):
        if self.dark_mode:
            self.terminal.setStyleSheet("background-color:black; color:lime; border:none;")
            self.input_line.setStyleSheet("background-color:black; color:lime; border:none; padding:6px;")
            # prompt background must match terminal bg
            self.prompt_label.setStyleSheet("color:lime; background-color:black;")
        else:
            self.terminal.setStyleSheet("background-color:white; color:black; border:none;")
            self.input_line.setStyleSheet("background-color:white; color:black; border:none; padding:6px;")
            self.prompt_label.setStyleSheet("color:black; background-color:white;")
