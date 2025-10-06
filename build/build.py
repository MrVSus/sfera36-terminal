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

    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), spec_file))
    print("[BUILD] Spec path:", spec_path)

    args = [
        "pyinstaller",
        spec_path,
        "--clean",
        "--noconfirm"
    ]
    print("[BUILD] Running:", " ".join(args))

    PyInstaller.__main__.run(args[1:])

if __name__ == "__main__":
    main()
