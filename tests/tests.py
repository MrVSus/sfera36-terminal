import sys
from pathlib import Path
# Путь на один уровень выше папки tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sys
from pathlib import Path
# Путь на один уровень выше папки tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.processor import CPU
from data.database import DatabaseManager

def run_script(script_lines):
    db = DatabaseManager()
    cpu = CPU(db_manager=db)

    for line in script_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # комментарии и пустые строки пропускаем

        # Чтобы поддержать формат "1000 / 005350" с пробелами
        line = line.replace(" / ", "/").replace(" G ", "G").replace(" /", "/")

        output = cpu.execute(line)
        if output:
            print(output)

# Пример сценария из лекции
script = """
    1000 / 005702
    1002 / 0 
    R2 / 2002 
    1000 G 
    RS/
"""
if __name__ == "__main__":
    run_script(script.strip().splitlines())
