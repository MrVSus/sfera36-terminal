import sys
from pathlib import Path
# Путь на один уровень выше папки tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.database import DatabaseManager
from core.processor import CPU

def octs(s): return int(s, 8)

def setup_cpu():
    db = DatabaseManager(db_path=":memory:", debug=False)
    cpu = CPU(db_manager=db, db_debug=False, debug=True)
    return cpu

def run_scenario():
    cpu = setup_cpu()
    # initialize memory & registers (addresses in octal strings)
    cpu.execute("1000 / 112142")   # instruction word
    cpu.execute("1002 / 0")        # halt marker
    cpu.execute("R1 / 2002")
    cpu.execute("2003 / 005177")
    cpu.execute("R2 / 3003")
    cpu.execute("3002 / 055177")
    # run
    out = cpu.execute("1000 G")
    print("Run output:")
    print(out)
    print("After run:")
    print("R1:", cpu.execute("R1 /"))
    print("2002:", cpu.execute("2002 /"))
    print("2003:", cpu.execute("2003 /"))
    print("R2:", cpu.execute("R2 /"))
    print("3002:", cpu.execute("3002 /"))
    print("3003:", cpu.execute("3003 /"))

if __name__ == "__main__":
    run_scenario()
