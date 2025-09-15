import os
import sys
import PyInstaller.__main__

def main():
    if len(sys.argv) < 2:
        print("Usage: python build.py [win7|win10]")
        sys.exit(1)

    target = sys.argv[1].lower()
    if target == "win7":
        spec_file = "win7_spec.spec"
    elif target == "win10":
        spec_file = "win10_spec.spec"
    else:
        print("Unknown target. Use win7 or win10")
        sys.exit(1)

    # Путь до spec
    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), spec_file))
    print("[BUILD] Spec path:", spec_path)

    # Явно вызываем так же, как из командной строки
    args = [
        "pyinstaller",         # для имитации sys.argv[0]
        spec_path,
        "--clean",
        "--noconfirm"
    ]
    print("[BUILD] Running:", " ".join(args))

    PyInstaller.__main__.run(args[1:])  # передаем всё кроме "pyinstaller"

if __name__ == "__main__":
    main()
