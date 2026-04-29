"""
entry.py
--------
Punto de entrada para PyInstaller.
Ejecutado por el .exe compilado en Windows.
Auto-eleva a administrador via UAC (necesario para comandos de red).
"""

import sys
import os
import ctypes
import platform

# Asegurar que src/ esté en el path
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
sys.path.insert(0, BASE_DIR)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate():
    """Re-lanza el .exe con privilegios de administrador via UAC."""
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
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Error", "NetCheck Pro solo es compatible con Windows.")
        r.destroy()
        sys.exit(1)

    # Elevar a administrador si es necesario
    if not is_admin():
        elevate()
        return

    # Lanzar la aplicación
    from main_app import main as run_app
    run_app()


if __name__ == "__main__":
    main()
