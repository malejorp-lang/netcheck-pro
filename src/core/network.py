"""
core/network.py
---------------
Recolección de datos de red del sistema.
Usa comandos nativos de Windows (ipconfig, arp) y librerías estándar.
Compatible con Windows 11. Diseñado para ser importado por analyzer.py y correlator.py.
"""

import subprocess
import socket
import re
import platform
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NetworkProfile:
    """Snapshot completo del estado de red en un momento dado."""
    local_ip: str = "N/A"
    gateway: str = "N/A"
    dns_servers: list[str] = field(default_factory=list)
    mac_address: str = "N/A"
    adapter_name: str = "N/A"
    subnet_mask: str = "N/A"
    is_wifi: bool = False
    wifi_ssid: Optional[str] = None
    wifi_signal: Optional[int] = None  # dBm
    device_count: int = 0


def get_network_profile() -> NetworkProfile:
    """
    Punto de entrada principal. Detecta la interfaz activa y extrae
    todos los parámetros de red relevantes usando ipconfig y comandos del sistema.
    """
    profile = NetworkProfile()

    try:
        profile.local_ip = _get_local_ip()
        _enrich_with_ipconfig(profile)
        _detect_wifi(profile)
        profile.device_count = _count_arp_devices(profile.gateway)
    except Exception as e:
        # Fallo silencioso: el resto del perfil mantiene valores "N/A"
        print(f"[network] Error parcial en get_network_profile: {e}")

    return profile


def _get_local_ip() -> str:
    """
    Obtiene la IP local activa creando un socket UDP hacia 8.8.8.8.
    No envía tráfico real. Método más confiable que socket.gethostbyname().
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def _enrich_with_ipconfig(profile: NetworkProfile) -> None:
    """
    Parsea la salida de 'ipconfig /all' para extraer gateway, DNS,
    máscara de subred, dirección MAC y nombre del adaptador.
    Busca el bloque que corresponde a la IP local ya detectada.
    """
    output = _run_command(["ipconfig", "/all"])
    if not output:
        return

    blocks = re.split(r"\r?\n\r?\n", output)
    target_block = None

    for block in blocks:
        if profile.local_ip in block:
            target_block = block
            break

    if not target_block:
        # Fallback: buscar en toda la salida
        target_block = output

    # Adaptador
    adapter_match = re.search(r"^(.+?):$", target_block, re.MULTILINE)
    if adapter_match:
        profile.adapter_name = adapter_match.group(1).strip()

    # Gateway
    gw_match = re.search(
        r"(?:Default Gateway|Puerta de enlace predeterminada)[^\d]*(\d+\.\d+\.\d+\.\d+)",
        target_block, re.IGNORECASE
    )
    if gw_match:
        profile.gateway = gw_match.group(1)

    # DNS
    dns_matches = re.findall(
        r"(?:DNS Servers|Servidores DNS)[^\d]*((?:\d+\.\d+\.\d+\.\d+\s*)+)",
        target_block, re.IGNORECASE
    )
    if dns_matches:
        profile.dns_servers = dns_matches[0].split()

    # Máscara
    mask_match = re.search(
        r"(?:Subnet Mask|Máscara de subred)[^\d]*(\d+\.\d+\.\d+\.\d+)",
        target_block, re.IGNORECASE
    )
    if mask_match:
        profile.subnet_mask = mask_match.group(1)

    # MAC
    mac_match = re.search(
        r"(?:Physical Address|Dirección física)[^\w]*([\w-]{17})",
        target_block, re.IGNORECASE
    )
    if mac_match:
        profile.mac_address = mac_match.group(1).upper()


def _detect_wifi(profile: NetworkProfile) -> None:
    """
    Usa 'netsh wlan show interfaces' para detectar si la conexión es WiFi
    y obtener SSID y señal.
    """
    output = _run_command(["netsh", "wlan", "show", "interfaces"])
    if not output or "There is no wireless" in output:
        return

    ssid_match = re.search(r"SSID\s*:\s*(.+)", output)
    signal_match = re.search(r"Signal\s*:\s*(\d+)%", output)

    if ssid_match:
        profile.is_wifi = True
        profile.wifi_ssid = ssid_match.group(1).strip()

    if signal_match:
        # Convertir % a dBm aproximado: dBm = (% / 2) - 100
        pct = int(signal_match.group(1))
        profile.wifi_signal = (pct // 2) - 100


def _count_arp_devices(gateway: str) -> int:
    """
    Cuenta dispositivos activos en la LAN usando la tabla ARP.
    Solo incluye entradas 'dynamic' (respuestas reales de red).
    """
    if gateway == "N/A":
        return 0

    output = _run_command(["arp", "-a"])
    if not output:
        return 0

    dynamic_entries = [
        line for line in output.splitlines()
        if "dynamic" in line.lower()
    ]
    # +1 por el propio dispositivo
    return len(dynamic_entries) + 1


def _run_command(cmd: list[str], timeout: int = 8) -> Optional[str]:
    """
    Ejecuta un comando del sistema y retorna stdout como string.
    Maneja encoding para Windows (cp850 / utf-8 fallback).
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        )
        # Windows puede devolver cp850 o cp1252
        for encoding in ("utf-8", "cp850", "cp1252", "latin-1"):
            try:
                return result.stdout.decode(encoding)
            except UnicodeDecodeError:
                continue
        return result.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"[network] Error ejecutando {cmd}: {e}")
        return None
