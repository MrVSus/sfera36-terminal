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

script = """
     
1000  / 112142 
1002 / 0 
R1 / 2001    
2000 / 005177  
R2 / 3003 
3002 / 055177  
1000 G  
R1 / 
2000 /  
R2 /     
3002 / 
"""

if __name__ == "__main__":
    run_script(script.strip().splitlines())