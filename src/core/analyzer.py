"""
core/analyzer.py
----------------
Motor de medición: latencia, jitter, pérdida de paquetes.
Ejecuta pings concurrentes a LAN (gateway) y WAN (servidores externos).
Calcula estadísticas rigurosas para alimentar al correlator.
"""

import re
import time
import platform
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from core.network import _run_command


# Objetivos WAN con fallback en cascada
WAN_TARGETS = [
    ("8.8.8.8",     "Google DNS"),
    ("1.1.1.1",     "Cloudflare"),
    ("208.67.222.222", "OpenDNS"),
]

PING_COUNT = 10          # paquetes por sesión
PING_TIMEOUT_MS = 2000   # ms, timeout por paquete


@dataclass
class PingResult:
    """Resultado estadístico de una sesión de ping."""
    target: str
    target_label: str = ""
    sent: int = 0
    received: int = 0
    loss_pct: float = 0.0
    min_ms: float = 0.0
    avg_ms: float = 0.0
    max_ms: float = 0.0
    jitter_ms: float = 0.0      # desviación estándar de RTTs
    samples: list[float] = field(default_factory=list)
    reachable: bool = False
    error: Optional[str] = None


@dataclass
class NetworkMetrics:
    """Métricas completas LAN + WAN."""
    lan: Optional[PingResult] = None
    wan: Optional[PingResult] = None
    wan_label: str = ""
    dns_reachable: bool = False
    dns_latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


def measure_all(gateway: str, dns_servers: list[str]) -> NetworkMetrics:
    """
    Punto de entrada principal del analyzer.
    Ejecuta mediciones LAN y WAN en paralelo para minimizar tiempo total.
    """
    metrics = NetworkMetrics()

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}

        if gateway and gateway != "N/A":
            futures["lan"] = executor.submit(ping_host, gateway, "Gateway LAN", PING_COUNT)

        # WAN: intentar primer objetivo disponible
        futures["wan"] = executor.submit(_ping_wan_with_fallback)

        if dns_servers:
            futures["dns"] = executor.submit(_check_dns_latency, dns_servers[0])

        for key, future in futures.items():
            try:
                result = future.result(timeout=30)
                if key == "lan":
                    metrics.lan = result
                elif key == "wan":
                    metrics.wan, metrics.wan_label = result
                elif key == "dns":
                    metrics.dns_reachable, metrics.dns_latency_ms = result
            except Exception as e:
                print(f"[analyzer] Error en medición '{key}': {e}")

    return metrics


def ping_host(target: str, label: str = "", count: int = PING_COUNT) -> PingResult:
    """
    Ejecuta ping nativo de Windows y parsea RTTs individuales.
    Calcula min/avg/max/jitter con precisión estadística.
    """
    result = PingResult(target=target, target_label=label, sent=count)

    cmd = [
        "ping",
        "-n", str(count),
        "-w", str(PING_TIMEOUT_MS),
        target
    ]

    output = _run_command(cmd, timeout=count * 3 + 5)
    if not output:
        result.error = "Sin respuesta del sistema"
        result.loss_pct = 100.0
        return result

    # Extraer RTTs individuales (ms)
    rtt_pattern = re.compile(r"(?:time|tiempo)[=<](\d+)ms", re.IGNORECASE)
    rtts = [float(m.group(1)) for m in rtt_pattern.finditer(output)]

    # Paquetes perdidos
    loss_match = re.search(r"(\d+)%\s+(?:loss|perdido)", output, re.IGNORECASE)
    if loss_match:
        result.loss_pct = float(loss_match.group(1))

    result.received = len(rtts)
    result.samples = rtts

    if rtts:
        result.reachable = True
        result.min_ms = min(rtts)
        result.max_ms = max(rtts)
        result.avg_ms = statistics.mean(rtts)
        result.jitter_ms = statistics.stdev(rtts) if len(rtts) > 1 else 0.0
    else:
        result.reachable = False
        result.loss_pct = 100.0
        result.error = _parse_ping_error(output)

    return result


def _ping_wan_with_fallback() -> tuple[PingResult, str]:
    """
    Intenta cada objetivo WAN en orden hasta obtener respuesta.
    Retorna el primer resultado exitoso o el último intento fallido.
    """
    last_result = None
    last_label = ""

    for ip, label in WAN_TARGETS:
        result = ping_host(ip, label, count=PING_COUNT)
        last_result = result
        last_label = label
        if result.reachable:
            return result, label

    return last_result, last_label


def _check_dns_latency(dns_server: str) -> tuple[bool, float]:
    """
    Mide latencia DNS resolviendo un dominio conocido.
    Usa socket.getaddrinfo con servidor explícito (no disponible en Python puro),
    por lo que hacemos un ping rápido al servidor DNS como proxy de latencia.
    """
    result = ping_host(dns_server, "DNS", count=4)
    return result.reachable, result.avg_ms


def _parse_ping_error(output: str) -> str:
    """Extrae mensaje de error legible de la salida del ping."""
    if "unreachable" in output.lower() or "inaccesible" in output.lower():
        return "Host inaccesible"
    if "timed out" in output.lower() or "tiempo agotado" in output.lower():
        return "Tiempo de espera agotado"
    if "could not find host" in output.lower() or "no se puede" in output.lower():
        return "Host no encontrado"
    return "Sin respuesta"


def classify_latency(avg_ms: float, is_lan: bool) -> str:
    """
    Clasifica latencia en: 'ok', 'warning', 'critical'.
    Umbrales diferenciados para LAN (esperada < 5ms) y WAN (< 80ms).
    """
    if is_lan:
        if avg_ms < 5:
            return "ok"
        elif avg_ms < 20:
            return "warning"
        else:
            return "critical"
    else:
        if avg_ms < 80:
            return "ok"
        elif avg_ms < 150:
            return "warning"
        else:
            return "critical"


def classify_jitter(jitter_ms: float) -> str:
    """Clasifica jitter: < 5ms ok, < 20ms warning, >= 20ms critical."""
    if jitter_ms < 5:
        return "ok"
    elif jitter_ms < 20:
        return "warning"
    else:
        return "critical"


def classify_loss(loss_pct: float) -> str:
    """Clasifica pérdida de paquetes."""
    if loss_pct == 0:
        return "ok"
    elif loss_pct <= 5:
        return "warning"
    else:
        return "critical"
