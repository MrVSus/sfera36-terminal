# core/command_parser.py
import re

class CommandParser:

    _re_mem_write = re.compile(r'^\s*([0-7]+)\s*/\s*([0-7]+)\s*$')
    _re_mem_read  = re.compile(r'^\s*([0-7]+)\s*/\s*$')
    _re_reg_write = re.compile(r'^\s*[Rr]([0-7])\s*/\s*([0-7]+)\s*$')
    _re_reg_read  = re.compile(r'^\s*[Rr]([0-7])\s*/\s*$')
    _re_exec_at   = re.compile(r'^\s*([0-7]+)\s*[Gg]\s*$')

    def parse(self, raw: str) -> dict:
        s = raw.strip()
        if s.upper() == 'QUIT' or s.upper() == 'Q':
            return {'type': 'QUIT'}
        m = self._re_mem_write.match(s)
        if m:
            return {'type': 'MEM_WRITE', 'addr': m.group(1), 'value': m.group(2)}
        m = self._re_reg_write.match(s)
        if m:
            return {'type': 'REG_WRITE', 'reg': f"R{m.group(1)}", 'value': m.group(2)}
        m = self._re_mem_read.match(s)
        if m:
            return {'type': 'MEM_READ', 'addr': m.group(1)}
        m = self._re_reg_read.match(s)
        if m:
            return {'type': 'REG_READ', 'reg': f"R{m.group(1)}"}
        m = self._re_exec_at.match(s)
        if m:
            return {'type': 'EXEC_AT', 'addr': m.group(1)}
        raise ValueError("Неизвестная команда")
