"""Entry point for the .exe (PyInstaller can't start inside a package)."""
import sys

from wva.__main__ import main

if __name__ == "__main__":
    sys.exit(main() or 0)
