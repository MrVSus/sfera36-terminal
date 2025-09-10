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

    spec_path = os.path.join(os.path.dirname(__file__), spec_file)
    PyInstaller.__main__.run([
        spec_path,
        "--noconfirm",
        "--clean"
    ])

if __name__ == "__main__":
    main()
