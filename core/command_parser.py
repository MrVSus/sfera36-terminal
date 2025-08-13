class CommandParser:
    def parse(self, raw: str):
        raw = raw.strip().upper()
        if not raw:
            raise ValueError("Пустая команда")

        if raw == 'QUIT':
            return {'type': 'QUIT'}

        if 'G' in raw:
            addr = raw.split('G')[0]
            return {'type': 'EXEC_AT', 'addr': addr}

        if '/' in raw:
            left, right = raw.split('/')

            # Запись/чтение регистра R0-R7
            if left.startswith('R') and left[1:].isdigit():
                reg_name = left
                if right == '':
                    return {'type': 'REG_READ', 'reg': reg_name}
                else:
                    return {'type': 'REG_WRITE', 'reg': reg_name, 'value': right}

            # Запись/чтение памяти по адресу
            if left.isdigit() or all(c in '01234567' for c in left):  # восьмеричное
                if right == '':
                    return {'type': 'MEM_READ', 'addr': left}
                else:
                    return {'type': 'MEM_WRITE', 'addr': left, 'value': right}

        return {'type': 'UNKNOWN', 'raw': raw}
