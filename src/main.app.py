"""
gui/main_window.py  —  NetCheck Pro
------------------------------------
Interfaz completa en tkinter puro.
CERO dependencias externas: tkinter viene incluido en Python estandar.
Sin PyQt6, sin DLLs descargadas, sin bloqueos WDAC.

Arquitectura:
  - MainWindow : ventana principal con layout tipo dashboard
  - DiagnosticWorker : hilo background que ejecuta el diagnostico
  - Widgets custom : StatusPanel, MetricCard, DiagnosticPanel
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
import threading
import time
import datetime

from core.network import NetworkProfile, get_network_profile
from core.analyzer import NetworkMetrics, measure_all
from core.correlator import DiagnosticReport, Severity, run_diagnosis
from core.profiler  import SystemProfile, get_system_profile

# ── Paleta de colores ────────────────────────────────────────────
C = {
    "bg":        "#0D1117",
    "bg2":       "#161B22",
    "bg3":       "#1C2128",
    "bg4":       "#21262D",
    "ok":        "#3FB950",
    "warn":      "#D29922",
    "crit":      "#F85149",
    "unk":       "#8B949E",
    "accent":    "#58A6FF",
    "txt":       "#E6EDF3",
    "txt2":      "#8B949E",
    "txt3":      "#484F58",
    "border":    "#30363D",
}

SEV_COLOR = {
    Severity.OK:       C["ok"],
    Severity.WARNING:  C["warn"],
    Severity.CRITICAL: C["crit"],
    Severity.UNKNOWN:  C["unk"],
}

STATUS_COLOR = {
    "OK":          C["ok"],
    "INESTABLE":   C["warn"],
    "CAÍDO":       C["crit"],
    "DESCONOCIDO": C["unk"],
}


# ════════════════════════════════════════════════════════════════
# HILO DE DIAGNÓSTICO
# ════════════════════════════════════════════════════════════════

class DiagnosticWorker(threading.Thread):
    def __init__(self, callbacks: dict):
        super().__init__(daemon=True)
        self._cb = callbacks  # {"progress", "profile", "system", "metrics", "report", "error", "done"}

    def _emit(self, key, *args):
        fn = self._cb.get(key)
        if fn:
            fn(*args)

    def run(self):
        try:
            self._emit("progress", 10, "Detectando interfaz de red...")
            profile = get_network_profile()
            self._emit("profile", profile)

            self._emit("progress", 25, "Obteniendo perfil del sistema...")
            sys_profile = get_system_profile()
            self._emit("system", sys_profile)

            self._emit("progress", 45, "Midiendo latencia LAN y WAN...")
            metrics = measure_all(profile.gateway, profile.dns_servers)
            self._emit("metrics", metrics)

            self._emit("progress", 85, "Correlacionando resultados...")
            report = run_diagnosis(profile, metrics)
            self._emit("report", report)

            self._emit("progress", 100, "Diagnóstico completado.")
        except Exception as e:
            self._emit("error", str(e))
        finally:
            self._emit("done")


# ════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ════════════════════════════════════════════════════════════════

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NetCheck Pro — Diagnóstico de Red")
        self.root.configure(bg=C["bg"])
        self.root.minsize(960, 680)
        self.root.geometry("1040x720")
        self._center_window()

        self._profile  = None
        self._metrics  = None
        self._report   = None
        self._worker   = None
        self._running  = False

        self._build_ui()
        self.root.after(300, self._start_diagnostic)

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 1040, 720
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Construcción de UI ────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_progress()
        self._build_status_msg()
        self._build_scroll_area()
        self._build_footer()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C["bg2"], height=52)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        inner = tk.Frame(hdr, bg=C["bg2"])
        inner.pack(fill="both", expand=True, padx=20)

        tk.Label(inner, text="◈ NetCheck Pro", bg=C["bg2"], fg=C["accent"],
                 font=("Consolas", 14, "bold")).pack(side="left", pady=14)
        tk.Label(inner, text="  Diagnóstico inteligente de red", bg=C["bg2"], fg=C["txt3"],
                 font=("Segoe UI", 9)).pack(side="left", pady=14)

        self._btn_refresh = tk.Button(
            inner, text="↻  Nuevo diagnóstico",
            bg=C["bg4"], fg=C["txt"],
            font=("Consolas", 9),
            relief="flat", cursor="hand2",
            padx=12, pady=5,
            command=self._start_diagnostic
        )
        self._btn_refresh.pack(side="right", pady=10)
        # Separador inferior del header
        sep = tk.Frame(self.root, bg=C["border"], height=1)
        sep.pack(fill="x")

    def _build_progress(self):
        self._pbar_var = tk.DoubleVar(value=0)
        self._pbar = ttk.Progressbar(
            self.root, variable=self._pbar_var,
            maximum=100, mode="determinate"
        )
        self._pbar.pack(fill="x")
        sty = ttk.Style()
        sty.theme_use("default")
        sty.configure("TProgressbar", troughcolor=C["bg4"],
                      background=C["accent"], thickness=3)

    def _build_status_msg(self):
        self._status_var = tk.StringVar(value="  Iniciando diagnóstico automático...")
        lbl = tk.Label(self.root, textvariable=self._status_var,
                       bg=C["bg"], fg=C["txt3"],
                       font=("Consolas", 8), anchor="w")
        lbl.pack(fill="x", padx=16, pady=2)

    def _build_scroll_area(self):
        container = tk.Frame(self.root, bg=C["bg"])
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=C["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._scroll_frame = tk.Frame(canvas, bg=C["bg"])
        self._scroll_frame_id = canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw"
        )

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def on_canvas_resize(e):
            canvas.itemconfig(self._scroll_frame_id, width=e.width)

        self._scroll_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_canvas_resize)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._build_content(self._scroll_frame)

    def _build_content(self, parent):
        pad = {"padx": 20}

        # ── Fila 1: estado LAN / WAN / Score ─────────────────
        row1 = tk.Frame(parent, bg=C["bg"])
        row1.pack(fill="x", **pad, pady=(16, 0))

        self._lan_panel = StatusPanel(row1, "RED LOCAL (LAN)")
        self._lan_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._wan_panel = StatusPanel(row1, "INTERNET (WAN)")
        self._wan_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._score_card = MetricCard(row1, "CALIDAD")
        self._score_card.pack(side="left", fill="both", ipadx=10)

        # ── Fila 2: métricas ──────────────────────────────────
        row2 = tk.Frame(parent, bg=C["bg"])
        row2.pack(fill="x", **pad, pady=(12, 0))

        self._m_lat_lan = MetricCard(row2, "LATENCIA LAN")
        self._m_lat_lan.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._m_lat_wan = MetricCard(row2, "LATENCIA WAN")
        self._m_lat_wan.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._m_jitter = MetricCard(row2, "JITTER")
        self._m_jitter.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._m_loss = MetricCard(row2, "PÉRDIDA PKT")
        self._m_loss.pack(side="left", fill="both", expand=True, padx=(0, 6))

        self._m_devs = MetricCard(row2, "DISPOSITIVOS")
        self._m_devs.pack(side="left", fill="both", expand=True)

        # ── Fila 3: info de red ───────────────────────────────
        row3 = tk.Frame(parent, bg=C["bg3"],
                        highlightbackground=C["border"], highlightthickness=1)
        row3.pack(fill="x", **pad, pady=(12, 0))

        fields = [
            ("IP LOCAL",   "_i_ip"),
            ("GATEWAY",    "_i_gw"),
            ("DNS",        "_i_dns"),
            ("ADAPTADOR",  "_i_adapter"),
            ("TIPO",       "_i_type"),
        ]
        for label, attr in fields:
            col = tk.Frame(row3, bg=C["bg3"])
            col.pack(side="left", padx=20, pady=12)
            tk.Label(col, text=label, bg=C["bg3"], fg=C["txt2"],
                     font=("Consolas", 8)).pack(anchor="w")
            v = tk.Label(col, text="—", bg=C["bg3"], fg=C["txt"],
                         font=("Consolas", 11))
            v.pack(anchor="w")
            setattr(self, attr, v)

        # ── Fila 4: diagnóstico ───────────────────────────────
        self._diag_panel = DiagnosticPanel(parent)
        self._diag_panel.pack(fill="x", **pad, pady=(12, 20))

    def _build_footer(self):
        sep = tk.Frame(self.root, bg=C["border"], height=1)
        sep.pack(fill="x")
        foot = tk.Frame(self.root, bg=C["bg2"], height=26)
        foot.pack(fill="x")
        foot.pack_propagate(False)

        self._footer_left = tk.Label(
            foot, text="NetCheck Pro v1.0",
            bg=C["bg2"], fg=C["txt3"], font=("Consolas", 7)
        )
        self._footer_left.pack(side="left", padx=16)

        self._footer_right = tk.Label(
            foot, text="",
            bg=C["bg2"], fg=C["txt3"], font=("Consolas", 7)
        )
        self._footer_right.pack(side="right", padx=16)

    # ── Lógica de diagnóstico ─────────────────────────────────

    def _start_diagnostic(self):
        if self._running:
            return
        self._running = True
        self._reset_ui()
        self._btn_refresh.config(state="disabled", text="Analizando...")

        callbacks = {
            "progress": self._on_progress,
            "profile":  self._on_profile,
            "system":   self._on_system,
            "metrics":  self._on_metrics,
            "report":   self._on_report,
            "error":    self._on_error,
            "done":     self._on_done,
        }
        self._worker = DiagnosticWorker(callbacks)
        self._worker.start()

    def _reset_ui(self):
        self.root.after(0, lambda: self._pbar_var.set(0))
        self.root.after(0, lambda: self._status_var.set("  Iniciando diagnóstico..."))
        self.root.after(0, lambda: self._lan_panel.set_status("DESCONOCIDO"))
        self.root.after(0, lambda: self._wan_panel.set_status("DESCONOCIDO"))
        self.root.after(0, lambda: self._score_card.set_value("—", ""))
        for card in [self._m_lat_lan, self._m_lat_wan, self._m_jitter,
                     self._m_loss, self._m_devs]:
            self.root.after(0, lambda c=card: c.set_value("—", ""))
        self.root.after(0, lambda: self._diag_panel.set_primary(
            "Ejecutando análisis de red...", C["txt3"]))

    def _on_progress(self, pct, msg):
        self.root.after(0, lambda: self._pbar_var.set(pct))
        self.root.after(0, lambda: self._status_var.set(f"  {msg}"))

    def _on_profile(self, profile: NetworkProfile):
        self._profile = profile
        def update():
            self._i_ip.config(text=profile.local_ip)
            self._i_gw.config(text=profile.gateway)
            self._i_dns.config(text=profile.dns_servers[0] if profile.dns_servers else "—")
            adapter = profile.adapter_name
            if len(adapter) > 22:
                adapter = adapter[:20] + "…"
            self._i_adapter.config(text=adapter)
            tipo = f"WiFi ({profile.wifi_ssid})" if profile.is_wifi else "Ethernet"
            self._i_type.config(text=tipo)
            self._m_devs.set_value(str(profile.device_count), "en red", C["accent"])
        self.root.after(0, update)

    def _on_system(self, sys_profile: SystemProfile):
        def update():
            self._footer_left.config(
                text=f"NetCheck Pro v1.0 — {sys_profile.os_name}  |  Host: {sys_profile.hostname}"
            )
        self.root.after(0, update)

    def _on_metrics(self, metrics: NetworkMetrics):
        self._metrics = metrics
        def update():
            if metrics.lan and metrics.lan.reachable:
                c = self._lat_color(metrics.lan.avg_ms, is_lan=True)
                self._m_lat_lan.set_value(f"{metrics.lan.avg_ms:.1f}", "ms", c)
            if metrics.wan and metrics.wan.reachable:
                c = self._lat_color(metrics.wan.avg_ms, is_lan=False)
                self._m_lat_wan.set_value(f"{metrics.wan.avg_ms:.1f}", "ms", c)
                cj = self._jitter_color(metrics.wan.jitter_ms)
                self._m_jitter.set_value(f"{metrics.wan.jitter_ms:.1f}", "ms", cj)
                cl = C["ok"] if metrics.wan.loss_pct == 0 else (
                     C["warn"] if metrics.wan.loss_pct <= 5 else C["crit"])
                self._m_loss.set_value(f"{metrics.wan.loss_pct:.0f}", "%", cl)
        self.root.after(0, update)

    def _on_report(self, report: DiagnosticReport):
        self._report = report
        def update():
            self._lan_panel.set_status(report.lan_status)
            if self._metrics and self._metrics.lan and self._metrics.lan.reachable:
                self._lan_panel.set_latency(f"{self._metrics.lan.avg_ms:.1f} ms")
            self._wan_panel.set_status(report.wan_status)
            if self._metrics and self._metrics.wan and self._metrics.wan.reachable:
                self._wan_panel.set_latency(f"{self._metrics.wan.avg_ms:.1f} ms")

            sc = report.connection_quality_score
            sc_color = C["ok"] if sc >= 80 else (C["warn"] if sc >= 50 else C["crit"])
            self._score_card.set_value(str(sc), "/ 100", sc_color)

            sev_color = SEV_COLOR.get(report.overall_severity, C["txt"])
            self._diag_panel.set_primary(report.primary_finding, sev_color)
            self._diag_panel.set_recommendation(report.recommendation)
            self._diag_panel.set_findings(report.secondary_findings)

            now = datetime.datetime.now().strftime("%H:%M:%S")
            self._footer_right.config(text=f"Último análisis: {now}  ")
        self.root.after(0, update)

    def _on_error(self, msg):
        self.root.after(0, lambda: self._status_var.set(f"  ⚠ Error: {msg}"))
        self.root.after(0, lambda: self._diag_panel.set_primary(
            f"Error durante el diagnóstico: {msg}", C["crit"]))

    def _on_done(self):
        def update():
            self._running = False
            self._btn_refresh.config(state="normal", text="↻  Nuevo diagnóstico")
        self.root.after(0, update)

    # ── Helpers de color ─────────────────────────────────────

    def _lat_color(self, ms, is_lan):
        if is_lan:
            return C["ok"] if ms < 5 else (C["warn"] if ms < 20 else C["crit"])
        return C["ok"] if ms < 80 else (C["warn"] if ms < 150 else C["crit"])

    def _jitter_color(self, ms):
        return C["ok"] if ms < 5 else (C["warn"] if ms < 20 else C["crit"])

    def show(self):
        self.root.mainloop()


# ════════════════════════════════════════════════════════════════
# WIDGETS REUTILIZABLES
# ════════════════════════════════════════════════════════════════

class StatusPanel(tk.Frame):
    """Panel LAN o WAN con badge de estado y latencia."""

    def __init__(self, parent, label):
        super().__init__(parent,
                         bg=C["bg3"],
                         highlightbackground=C["border"],
                         highlightthickness=1)
        self.configure(height=88)

        inner = tk.Frame(self, bg=C["bg3"])
        inner.pack(fill="both", expand=True, padx=16, pady=10)

        tk.Label(inner, text=label, bg=C["bg3"], fg=C["txt2"],
                 font=("Consolas", 8)).pack(anchor="w")

        self._badge = tk.Label(inner, text="  DESCONOCIDO  ",
                               bg=C["bg4"], fg=C["unk"],
                               font=("Consolas", 9, "bold"),
                               padx=6, pady=2)
        self._badge.pack(anchor="w", pady=(4, 2))

        self._latency = tk.Label(inner, text="— ms",
                                 bg=C["bg3"], fg=C["txt"],
                                 font=("Consolas", 11, "bold"))
        self._latency.pack(anchor="w")

    def set_status(self, status: str):
        color = STATUS_COLOR.get(status, C["unk"])
        self._badge.config(text=f"  {status}  ", fg=color,
                           bg=_darken(color))

    def set_latency(self, text: str):
        self._latency.config(text=text)


class MetricCard(tk.Frame):
    """Tarjeta individual para una métrica numérica."""

    def __init__(self, parent, title):
        super().__init__(parent,
                         bg=C["bg3"],
                         highlightbackground=C["border"],
                         highlightthickness=1)
        self.configure(height=100)

        inner = tk.Frame(self, bg=C["bg3"])
        inner.pack(fill="both", expand=True, padx=14, pady=10)

        tk.Label(inner, text=title, bg=C["bg3"], fg=C["txt2"],
                 font=("Consolas", 7)).pack(anchor="w")

        self._value = tk.Label(inner, text="—",
                               bg=C["bg3"], fg=C["txt"],
                               font=("Consolas", 22, "bold"))
        self._value.pack(anchor="w")

        self._unit = tk.Label(inner, text="",
                              bg=C["bg3"], fg=C["txt3"],
                              font=("Consolas", 8))
        self._unit.pack(anchor="w")

    def set_value(self, value: str, unit: str = "", color: str = None):
        self._value.config(text=value, fg=color or C["txt"])
        self._unit.config(text=unit)


class DiagnosticPanel(tk.Frame):
    """Panel de diagnóstico inteligente con hallazgos."""

    def __init__(self, parent):
        super().__init__(parent,
                         bg=C["bg3"],
                         highlightbackground=C["border"],
                         highlightthickness=1)

        # Header
        hdr = tk.Frame(self, bg=C["bg3"])
        hdr.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(hdr, text="⬡", bg=C["bg3"], fg=C["accent"],
                 font=("Segoe UI", 12)).pack(side="left")
        tk.Label(hdr, text="  DIAGNÓSTICO INTELIGENTE", bg=C["bg3"], fg=C["txt2"],
                 font=("Consolas", 8)).pack(side="left")

        # Hallazgo principal
        self._primary = tk.Label(self, text="Ejecutando análisis...",
                                  bg=C["bg3"], fg=C["txt3"],
                                  font=("Segoe UI", 12, "bold"),
                                  wraplength=860, justify="left", anchor="w")
        self._primary.pack(fill="x", padx=18, pady=(0, 8))

        # Separador
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=18)

        # Recomendación
        rec_frame = tk.Frame(self, bg=C["bg3"])
        rec_frame.pack(fill="x", padx=18, pady=(8, 4))
        tk.Label(rec_frame, text="RECOMENDACIÓN", bg=C["bg3"], fg=C["txt2"],
                 font=("Consolas", 7)).pack(anchor="w")
        self._rec = tk.Label(rec_frame, text="",
                              bg=C["bg3"], fg=C["txt2"],
                              font=("Segoe UI", 9),
                              wraplength=860, justify="left", anchor="w")
        self._rec.pack(fill="x")

        # Contenedor de hallazgos secundarios
        self._findings_frame = tk.Frame(self, bg=C["bg3"])
        self._findings_frame.pack(fill="x", padx=18, pady=(6, 14))

    def set_primary(self, text: str, color: str):
        self._primary.config(text=text, fg=color)

    def set_recommendation(self, text: str):
        self._rec.config(text=text)

    def set_findings(self, findings):
        # Limpiar hallazgos anteriores
        for w in self._findings_frame.winfo_children():
            w.destroy()

        if not findings:
            return

        tk.Frame(self._findings_frame, bg=C["border"], height=1).pack(
            fill="x", pady=(0, 6))

        from core.correlator import Severity
        for f in findings[:5]:
            dot_color = SEV_COLOR.get(f.severity, C["unk"])
            row = tk.Frame(self._findings_frame, bg=C["bg3"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="●", bg=C["bg3"], fg=dot_color,
                     font=("Segoe UI", 7)).pack(side="left", padx=(0, 6))
            text = f"{f.title}: {f.detail}"
            tk.Label(row, text=text, bg=C["bg3"], fg=C["txt2"],
                     font=("Segoe UI", 9),
                     wraplength=840, justify="left", anchor="w").pack(
                         side="left", fill="x")


# ── Utilidad: oscurecer un color hex para el fondo del badge ──

def _darken(hex_color: str) -> str:
    """Devuelve una versión muy oscura del color para el bg del badge."""
    darken_map = {
        C["ok"]:   "#0d2b15",
        C["warn"]: "#2b200a",
        C["crit"]: "#2b0d0c",
        C["unk"]:  "#1c2128",
    }
    return darken_map.get(hex_color, C["bg4"])