"""
entry.py
--------
Punto de entrada para PyInstaller.
Corregido para funcionar correctamente como .exe frozen.
"""

import sys
import os
import ctypes
import platform


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv[1:]),
        None, 1
    )
    sys.exit(0)


def main():
    if platform.system() != "Windows":
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Error", "NetCheck Pro solo es compatible con Windows.")
        r.destroy()
        sys.exit(1)

    if not is_admin():
        elevate()
        return

    # Importar todo explicitamente para PyInstaller
    import tkinter
    import tkinter.ttk
    import tkinter.messagebox
    import threading
    import subprocess
    import socket
    import statistics
    import re
    import time
    import datetime
    import concurrent.futures

    from core.network       import get_network_profile
    from core.analyzer      import measure_all
    from core.correlator    import run_diagnosis
    from core.profiler      import get_system_profile
    from gui.main_window_tk import MainWindow

    window = MainWindow()
    window.show()


if __name__ == "__main__":
    main()
