import sys
from pathlib import Path
from ui.console_ui import ConsoleTerminal
# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))


def main():
    terminal = ConsoleTerminal()
    terminal.run()

if __name__ == "__main__":
    main()