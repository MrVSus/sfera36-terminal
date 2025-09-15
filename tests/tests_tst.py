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

from core.command_parser import CommandParser

p = CommandParser()
for s in ["RS/", "RS /", "RS/0", "RS/ 0", "RS / 0"]:
    try:
        print(s, "->", p.parse(s))
    except Exception as e:
        print(s, "-> ERR:", e)

