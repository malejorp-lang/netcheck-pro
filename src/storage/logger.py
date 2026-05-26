"""
storage/logger.py
-----------------
Logger profesional para NetCheck Pro.
Guarda eventos en AppData del usuario.
Niveles: INFO, WARNING, ERROR, CRITICAL
"""

import os, logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR  = os.path.join(os.environ.get("APPDATA", "C:\\Temp"), "NetCheckPro", "logs")
LOG_FILE = os.path.join(LOG_DIR, "netcheck.log")

_logger = None


def get_logger() -> logging.Logger:
    """Retorna el logger configurado. Lo crea si no existe."""
    global _logger
    if _logger:
        return _logger

    os.makedirs(LOG_DIR, exist_ok=True)

    _logger = logging.getLogger("NetCheckPro")
    _logger.setLevel(logging.DEBUG)

    # Handler de archivo rotativo (max 5MB, 3 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Formato: [2025-05-01 08:32:15] INFO - mensaje
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    return _logger


def log_info(msg: str):
    get_logger().info(msg)

def log_warning(msg: str):
    get_logger().warning(msg)

def log_error(msg: str):
    get_logger().error(msg)

def log_critical(msg: str):
    get_logger().critical(msg)

def log_diagnostic(health_score: int, lan_status: str, wan_status: str, finding: str):
    """Log especifico para cada diagnostico."""
    get_logger().info(
        f"DIAGNOSTIC | Score:{health_score}/100 | "
        f"LAN:{lan_status} | WAN:{wan_status} | {finding}"
    )

def log_alert(severity: str, title: str, detail: str):
    """Log especifico para alertas detectadas."""
    level = {
        "critical": logging.CRITICAL,
        "warning":  logging.WARNING,
        "info":     logging.INFO,
    }.get(severity, logging.INFO)
    get_logger().log(level, f"ALERT | [{severity.upper()}] {title}: {detail}")

def get_log_path() -> str:
    """Retorna la ruta del archivo de log."""
    return LOG_FILE
