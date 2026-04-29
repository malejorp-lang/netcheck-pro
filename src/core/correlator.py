"""
core/correlator.py
------------------
Motor de diagnóstico inteligente.
Correlaciona métricas LAN + WAN + perfil de red para producir
diagnósticos en lenguaje natural, clasificados por severidad y causa raíz.

Este módulo es el diferencial clave de NetCheck Pro:
no muestra datos crudos, sino interpretación accionable.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.analyzer import NetworkMetrics, classify_latency, classify_jitter, classify_loss
from core.network import NetworkProfile


class Severity(Enum):
    OK       = "ok"
    WARNING  = "warning"
    CRITICAL = "critical"
    UNKNOWN  = "unknown"


class RootCause(Enum):
    NONE         = "none"
    WIFI_QUALITY = "wifi_quality"
    LAN_CONGESTION = "lan_congestion"
    ISP_ISSUE    = "isp_issue"
    DNS_ISSUE    = "dns_issue"
    GATEWAY_DOWN = "gateway_down"
    NO_INTERNET  = "no_internet"
    HIGH_JITTER  = "high_jitter"
    PARTIAL_LOSS = "partial_loss"


@dataclass
class DiagnosticFinding:
    """Una observación individual con severidad y texto explicativo."""
    severity: Severity
    title: str
    detail: str
    cause: RootCause = RootCause.NONE


@dataclass
class DiagnosticReport:
    """Reporte completo de diagnóstico listo para renderizar en la UI."""
    overall_severity: Severity = Severity.UNKNOWN
    primary_finding: str = ""          # Frase principal (bold en UI)
    secondary_findings: list[DiagnosticFinding] = field(default_factory=list)
    recommendation: str = ""           # Acción sugerida al usuario
    lan_status: str = "DESCONOCIDO"
    wan_status: str = "DESCONOCIDO"
    connection_quality_score: int = 0  # 0-100


def run_diagnosis(profile: NetworkProfile, metrics: NetworkMetrics) -> DiagnosticReport:
    """
    Punto de entrada principal. Ejecuta todas las reglas de correlación
    y produce un DiagnosticReport consolidado.
    """
    report = DiagnosticReport()
    findings: list[DiagnosticFinding] = []

    # ─── 1. Evaluar estado LAN ───────────────────────────────────────────
    lan_severity = _evaluate_lan(profile, metrics, findings)
    report.lan_status = _severity_to_label(lan_severity)

    # ─── 2. Evaluar estado WAN ───────────────────────────────────────────
    wan_severity = _evaluate_wan(profile, metrics, findings)
    report.wan_status = _severity_to_label(wan_severity)

    # ─── 3. Correlación LAN vs WAN (diagnóstico de causa raíz) ──────────
    primary, recommendation = _correlate(
        lan_severity, wan_severity, profile, metrics, findings
    )

    # ─── 4. Severidad global (peor de LAN/WAN) ──────────────────────────
    severities = [lan_severity, wan_severity]
    if Severity.CRITICAL in severities:
        report.overall_severity = Severity.CRITICAL
    elif Severity.WARNING in severities:
        report.overall_severity = Severity.WARNING
    else:
        report.overall_severity = Severity.OK

    report.primary_finding = primary
    report.recommendation = recommendation
    report.secondary_findings = findings
    report.connection_quality_score = _compute_quality_score(metrics, lan_severity, wan_severity)

    return report


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS DE EVALUACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_lan(
    profile: NetworkProfile,
    metrics: NetworkMetrics,
    findings: list
) -> Severity:
    """Analiza el estado de la red local (ping al gateway)."""

    if not metrics.lan or not metrics.lan.reachable:
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Gateway inalcanzable",
            detail=f"No se pudo alcanzar el gateway {profile.gateway}. "
                   "Puede indicar problema en el router o configuración de red.",
            cause=RootCause.GATEWAY_DOWN
        ))
        return Severity.CRITICAL

    lan = metrics.lan
    lat_class = classify_latency(lan.avg_ms, is_lan=True)
    jit_class  = classify_jitter(lan.jitter_ms)
    loss_class = classify_loss(lan.loss_pct)

    # Jitter alto en LAN → señal WiFi o interferencia
    if jit_class == "critical" and profile.is_wifi:
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Alta variación de latencia en LAN",
            detail=f"Jitter de {lan.jitter_ms:.1f}ms detectado en conexión WiFi ({profile.wifi_ssid}). "
                   "Señal inestable, interferencia de canal o congestión inalámbrica.",
            cause=RootCause.WIFI_QUALITY
        ))
    elif jit_class == "warning" and profile.is_wifi:
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING,
            title="Variación de latencia moderada",
            detail=f"Jitter de {lan.jitter_ms:.1f}ms. La conexión WiFi muestra leve inestabilidad.",
            cause=RootCause.WIFI_QUALITY
        ))
    elif jit_class == "critical":
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING,
            title="Jitter alto en LAN cableada",
            detail=f"Jitter de {lan.jitter_ms:.1f}ms en conexión por cable. "
                   "Posible congestión de red o switch defectuoso.",
            cause=RootCause.LAN_CONGESTION
        ))

    # Latencia LAN elevada
    if lat_class == "critical":
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Latencia LAN crítica",
            detail=f"Latencia al gateway: {lan.avg_ms:.1f}ms (esperado < 5ms). "
                   "Router sobrecargado o congestionado.",
            cause=RootCause.LAN_CONGESTION
        ))
    elif lat_class == "warning":
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING,
            title="Latencia LAN elevada",
            detail=f"Latencia al gateway: {lan.avg_ms:.1f}ms. Levemente por encima de lo óptimo.",
            cause=RootCause.LAN_CONGESTION
        ))

    # Pérdida de paquetes
    if loss_class == "critical":
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Pérdida de paquetes severa en LAN",
            detail=f"{lan.loss_pct:.0f}% de paquetes perdidos hacia el gateway.",
            cause=RootCause.PARTIAL_LOSS
        ))
    elif loss_class == "warning":
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING,
            title="Pérdida de paquetes leve en LAN",
            detail=f"{lan.loss_pct:.0f}% de paquetes perdidos. La red puede ser inestable.",
            cause=RootCause.PARTIAL_LOSS
        ))

    # Señal WiFi débil
    if profile.is_wifi and profile.wifi_signal is not None:
        if profile.wifi_signal < -75:
            findings.append(DiagnosticFinding(
                severity=Severity.WARNING,
                title="Señal WiFi débil",
                detail=f"Señal: {profile.wifi_signal} dBm. "
                       "Acercarse al punto de acceso o usar banda 5GHz puede mejorar la estabilidad.",
                cause=RootCause.WIFI_QUALITY
            ))

    # Determinar severidad global LAN
    if any(f.severity == Severity.CRITICAL for f in findings if f.cause not in [RootCause.ISP_ISSUE, RootCause.NO_INTERNET]):
        return Severity.CRITICAL
    elif any(f.severity == Severity.WARNING for f in findings if f.cause not in [RootCause.ISP_ISSUE, RootCause.NO_INTERNET]):
        return Severity.WARNING
    return Severity.OK


def _evaluate_wan(
    profile: NetworkProfile,
    metrics: NetworkMetrics,
    findings: list
) -> Severity:
    """Analiza el estado de la conectividad a Internet."""

    if not metrics.wan or not metrics.wan.reachable:
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Sin conectividad a Internet",
            detail="No se pudo alcanzar ningún servidor externo (Google, Cloudflare, OpenDNS). "
                   "El dispositivo no tiene salida a Internet.",
            cause=RootCause.NO_INTERNET
        ))
        return Severity.CRITICAL

    wan = metrics.wan
    lat_class  = classify_latency(wan.avg_ms, is_lan=False)
    jit_class  = classify_jitter(wan.jitter_ms)
    loss_class = classify_loss(wan.loss_pct)

    if lat_class == "critical":
        findings.append(DiagnosticFinding(
            severity=Severity.CRITICAL,
            title="Latencia WAN crítica",
            detail=f"Latencia promedio a Internet: {wan.avg_ms:.1f}ms. "
                   "Posible congestión en el ISP o ruta de red deficiente.",
            cause=RootCause.ISP_ISSUE
        ))
    elif lat_class == "warning":
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING,
            title="Latencia WAN elevada",
            detail=f"Latencia a Internet: {wan.avg_ms:.1f}ms. "
                   "Por encima del rango óptimo (< 80ms).",
            cause=RootCause.ISP_ISSUE
        ))

    if jit_class in ["critical", "warning"]:
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING if jit_class == "warning" else Severity.CRITICAL,
            title="Inestabilidad en conexión WAN",
            detail=f"Jitter WAN: {wan.jitter_ms:.1f}ms. "
                   "La conexión a Internet presenta variaciones. "
                   "Puede afectar videollamadas y streaming.",
            cause=RootCause.ISP_ISSUE
        ))

    if loss_class != "ok":
        findings.append(DiagnosticFinding(
            severity=Severity.WARNING if loss_class == "warning" else Severity.CRITICAL,
            title="Pérdida de paquetes en WAN",
            detail=f"{wan.loss_pct:.0f}% pérdida hacia Internet. "
                   "Posible problema con el ISP o saturación de enlace.",
            cause=RootCause.ISP_ISSUE
        ))

    wan_findings = [f for f in findings if f.cause == RootCause.ISP_ISSUE]
    if any(f.severity == Severity.CRITICAL for f in wan_findings):
        return Severity.CRITICAL
    elif wan_findings:
        return Severity.WARNING
    return Severity.OK


def _correlate(
    lan_sev: Severity,
    wan_sev: Severity,
    profile: NetworkProfile,
    metrics: NetworkMetrics,
    findings: list
) -> tuple[str, str]:
    """
    Reglas de correlación LAN vs WAN para determinar causa raíz
    y recomendación principal. Retorna (primary_finding, recommendation).
    """

    lan_ok  = lan_sev == Severity.OK
    wan_ok  = wan_sev == Severity.OK
    lan_bad = lan_sev == Severity.CRITICAL
    wan_bad = wan_sev == Severity.CRITICAL

    # ── ESCENARIO 1: Todo OK ─────────────────────────────────────────────
    if lan_ok and wan_ok:
        return (
            "✓ Conexión estable y saludable",
            "No se requiere acción. Tu red opera en condiciones óptimas."
        )

    # ── ESCENARIO 2: LAN OK pero WAN malo → problema en ISP ─────────────
    if lan_ok and wan_bad:
        return (
            "Fallo en conectividad a Internet — ISP o equipo CPE",
            "La red local funciona correctamente. El problema está fuera de tu control local. "
            "Verifica el estado de tu ISP o reinicia el módem/ONT."
        )

    # ── ESCENARIO 3: LAN malo pero WAN ok → poco probable pero posible ──
    if lan_bad and wan_ok:
        return (
            "Problema en la red local — Router o switch interno",
            "Internet funciona pero la red interna tiene fallas. "
            "Revisa el router, switches y configuración DHCP."
        )

    # ── ESCENARIO 4: Ambos malos → problema desde LAN hacia afuera ──────
    if lan_bad and wan_bad:
        return (
            "Fallo completo de red — Sin LAN ni Internet",
            "Verifica conexión física al router, reinicia el equipo de red y "
            "contacta a tu ISP si el problema persiste."
        )

    # ── ESCENARIO 5: LAN con warning por WiFi + WAN degradado ───────────
    wifi_issue = any(f.cause == RootCause.WIFI_QUALITY for f in findings)
    if wifi_issue and wan_sev in [Severity.WARNING, Severity.CRITICAL]:
        return (
            "Inestabilidad WiFi afectando rendimiento general",
            "La señal inalámbrica débil puede estar degradando tanto LAN como WAN. "
            f"Considera acercarte al router o cambiar al canal 5GHz en {profile.wifi_ssid or 'tu red'}."
        )

    # ── ESCENARIO 6: Jitter alto en LAN (WiFi) pero WAN aceptable ───────
    if wifi_issue and wan_ok:
        return (
            "Alta variación de latencia en LAN → posible problema WiFi",
            "Tu conexión a Internet es estable pero la red WiFi local presenta interferencias. "
            "Cambia de canal inalámbrico o reduce la distancia al punto de acceso."
        )

    # ── ESCENARIO 7: WAN con warning pero LAN ok → congestión ISP ───────
    if lan_ok and wan_sev == Severity.WARNING:
        return (
            "Conexión a Internet degradada — Posible congestión en el ISP",
            "Tu red local está bien, pero Internet presenta latencia elevada. "
            "Puede ser congestión temporal del ISP o problema en la ruta de enrutamiento."
        )

    # ── FALLBACK ─────────────────────────────────────────────────────────
    return (
        "Red con anomalías detectadas — Revisar detalles",
        "Se detectaron condiciones de red por fuera del rango óptimo. "
        "Revisa los hallazgos detallados para identificar la causa raíz."
    )


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def _severity_to_label(s: Severity) -> str:
    return {
        Severity.OK:       "OK",
        Severity.WARNING:  "INESTABLE",
        Severity.CRITICAL: "CAÍDO",
        Severity.UNKNOWN:  "DESCONOCIDO"
    }.get(s, "DESCONOCIDO")


def _compute_quality_score(
    metrics: NetworkMetrics,
    lan_sev: Severity,
    wan_sev: Severity
) -> int:
    """
    Calcula un score de calidad 0-100 basado en latencia, jitter y pérdida.
    Usado para el indicador visual de calidad en el dashboard.
    """
    score = 100

    # Penalizar por severidad
    sev_penalties = {Severity.OK: 0, Severity.WARNING: 20, Severity.CRITICAL: 45, Severity.UNKNOWN: 30}
    score -= sev_penalties.get(lan_sev, 20)
    score -= sev_penalties.get(wan_sev, 20)

    # Penalizar por jitter WAN
    if metrics.wan and metrics.wan.reachable:
        if metrics.wan.jitter_ms > 20:
            score -= 10
        elif metrics.wan.jitter_ms > 10:
            score -= 5

    # Penalizar por pérdida de paquetes
    if metrics.wan and metrics.wan.loss_pct > 0:
        score -= min(int(metrics.wan.loss_pct * 2), 20)

    return max(0, min(100, score))
