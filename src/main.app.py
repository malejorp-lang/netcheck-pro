"""
main_app.py
-----------
Punto de entrada de NetCheck Pro.
Usa exclusivamente tkinter — incluido en Python estandar.
Sin PyQt6, sin DLLs externas, sin bloqueos WDAC/AppLocker.
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from gui.main_window_tk import MainWindow


def main():
    window = MainWindow()
    window.show()


if __name__ == "__main__":
    main()
