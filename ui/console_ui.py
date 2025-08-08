from core.processor import CPU

class ConsoleTerminal:
    def __init__(self):
        self.cpu = CPU()
    def run(self):
        print("Терминал 'Сфера-36' (восьмеричная система)")
        print("Форматы команд:")
        print("  XXXX/YYYYY - запись/команда (005203 - COM R3)")
        print("  XXXX/      - чтение памяти/регистра")
        print("  Rn/        - чтение регистра (R0-R7)")
        print("  XXXXG[cond]- выполнение с адреса")
        print("  XXXX/0     - установка маркера остановки")
        print("  quit       - выход\n")

        while True:
            try:
                cmd = input("> ").strip()
                if not cmd:
                    continue
                    
                result = self.cpu.execute(cmd)
                
                if result == "QUIT":
                    break
                    
                if result:
                    print(result)
                
            except Exception as e:
                print(f"Ошибка: {e}")