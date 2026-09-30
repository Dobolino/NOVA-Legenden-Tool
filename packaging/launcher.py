"""Entry point for the frozen Windows program (PyInstaller)."""

import sys

from nova_legend.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
