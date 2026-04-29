"""
core/profiler.py
----------------
Información del sistema operativo y hardware de red.
Complementa el NetworkProfile con datos del entorno de ejecución.
Permite al correlator contextualizar mejor los diagnósticos.
"""

import platform
import socket
import os
import re
from dataclasses import dataclass
from typing import Optional

from core.network import _run_command


@dataclass
class SystemProfile:
    hostname: str = "N/A"
    os_name: str = "N/A"
    os_version: str = "N/A"
    python_version: str = "N/A"
    is_admin: bool = False
    firewall_active: Optional[bool] = None
    network_adapters: list[str] = None

    def __post_init__(self):
        if self.network_adapters is None:
            self.network_adapters = []


def get_system_profile() -> SystemProfile:
    profile = SystemProfile()

    try:
        profile.hostname = socket.gethostname()
        profile.os_name = platform.system()
        profile.os_version = platform.version()
        profile.python_version = platform.python_version()
        profile.is_admin = _check_admin()
        profile.firewall_active = _check_firewall()
        profile.network_adapters = _list_adapters()
    except Exception as e:
        print(f"[profiler] Error: {e}")

    return profile


def _check_admin() -> bool:
    """Verifica si la aplicación corre con privilegios de administrador."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return os.getuid() == 0 if hasattr(os, "getuid") else False


def _check_firewall() -> Optional[bool]:
    """
    Verifica si el Firewall de Windows está activo.
    Requiere 'netsh advfirewall show allprofiles'.
    """
    output = _run_command(["netsh", "advfirewall", "show", "allprofiles"])
    if not output:
        return None
    return "ON" in output.upper()


def _list_adapters() -> list[str]:
    """Lista adaptadores de red activos del sistema."""
    output = _run_command(["netsh", "interface", "show", "interface"])
    if not output:
        return []

    adapters = []
    for line in output.splitlines():
        if "Connected" in line or "Conectado" in line:
            parts = line.split()
            if len(parts) >= 4:
                adapters.append(" ".join(parts[3:]))
    return adapters
