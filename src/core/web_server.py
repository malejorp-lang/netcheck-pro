"""
core/web_server.py
------------------
Servidor HTTP embebido que sirve la interfaz Veloce.
Se enlaza a 0.0.0.0 para que cualquier equipo del dominio pueda acceder
apuntando su navegador a http://<IP-del-servidor>:7890
"""
import http.server
import os
import socket
import sys
import threading
from typing import Optional

WEB_PORT = 7890

_httpd: Optional[http.server.HTTPServer] = None
_server_thread: Optional[threading.Thread] = None


def _get_web_dir() -> str:
    """Resuelve la ruta a los archivos web, compatible con PyInstaller."""
    if getattr(sys, "frozen", False):
        # Ejecutando como .exe compilado — los archivos están en _MEIPASS/web
        return os.path.join(sys._MEIPASS, "web")
    # Ejecutando desde código fuente
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def get_local_ip() -> str:
    """Devuelve la IP LAN del equipo (el mismo truco que usa network.py)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def get_server_url() -> str:
    """URL accesible desde la red del dominio."""
    return f"http://{get_local_ip()}:{WEB_PORT}"


def get_localhost_url() -> str:
    """URL local para abrir en el mismo equipo."""
    return f"http://localhost:{WEB_PORT}"


def start(port: int = WEB_PORT) -> bool:
    """
    Inicia el servidor en un hilo daemon.
    Devuelve True si arrancó correctamente, False si el puerto está ocupado
    o los archivos web no existen.
    """
    global _httpd, _server_thread

    if _httpd is not None:
        return True  # ya está corriendo

    web_dir = _get_web_dir()
    if not os.path.isdir(web_dir):
        return False

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)

        def log_message(self, fmt, *args):
            pass  # silenciar logs en producción

    try:
        _httpd = http.server.HTTPServer(("0.0.0.0", port), _Handler)
    except OSError:
        return False

    _server_thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
    _server_thread.start()
    return True


def stop() -> None:
    global _httpd
    if _httpd:
        _httpd.shutdown()
        _httpd = None


def is_running() -> bool:
    return _httpd is not None
