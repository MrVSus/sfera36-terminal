import sys
from pathlib import Path
# Путь на один уровень выше папки tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.processor import CPU
from data.database import DatabaseManager

def run_script(lines):
    db = DatabaseManager(debug=True)
    cpu = CPU(db_manager=db, db_debug=True, debug=True)

    for line in lines:
        l = line.strip()
        if not l: continue
        # Normalise spacing
        l = l.replace(" / ", "/").replace(" /", "/").replace(" G ", "G").strip()
        print("> " + l)
        out = cpu.execute(l)
        if out:
            print(out)

    # дамп нескольких интересующих адресов/регистров
    print("DUMP R0-R3:", [db.get_register_value(i) for i in range(4)])
    print("DUMP mem 1776,2000,3000:", db.get_memory_value(0o1776), db.get_memory_value(0o2000), db.get_memory_value(0o3000))

if __name__ == "__main__":
    script = [
        "1350/105044",
        "1352/0",
        "R4/2002",
        "2000/13426",
        "1350G",
        "R7/",
        "R4/",
        "2000/"
    ]
    run_script(script)
