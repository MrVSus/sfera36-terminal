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
            if right == '':
                return {'type': 'REG_READ', 'reg': left}
            return {'type': 'MEM_OP', 'addr': left, 'value': right}
        
        return {'type': 'UNKNOWN', 'raw': raw}