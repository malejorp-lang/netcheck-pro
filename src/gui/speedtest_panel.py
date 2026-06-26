"""
gui/speedtest_panel.py
----------------------
Sección "Veloce – Test de Velocidad" dentro del dashboard de NetCheck Pro.
Muestra el estado del servidor embebido y la URL para acceso desde el dominio.
"""
import tkinter as tk
import webbrowser

from core import web_server

C = {
    "bg":     "#0D1117",
    "bg2":    "#161B22",
    "bg3":    "#1C2128",
    "bg4":    "#21262D",
    "ok":     "#3FB950",
    "warn":   "#D29922",
    "crit":   "#F85149",
    "accent": "#58A6FF",
    "txt":    "#E6EDF3",
    "txt2":   "#8B949E",
    "txt3":   "#484F58",
    "border": "#30363D",
    "cyan":   "#00f2fe",
    "pink":   "#f35588",
}


class SpeedTestPanel(tk.Frame):
    """Card del test de velocidad para el dashboard principal."""

    def __init__(self, parent):
        super().__init__(
            parent,
            bg=C["bg3"],
            highlightbackground=C["border"],
            highlightthickness=1,
        )
        self._build_ui()
        self._refresh_status()

    # ── Construcción de UI ────────────────────────────────────

    def _build_ui(self):
        # Encabezado
        hdr = tk.Frame(self, bg=C["bg3"])
        hdr.pack(fill="x", padx=18, pady=(14, 0))

        tk.Label(
            hdr, text="⚡", bg=C["bg3"], fg=C["cyan"],
            font=("Segoe UI", 13),
        ).pack(side="left")
        tk.Label(
            hdr, text="  VELOCE — TEST DE VELOCIDAD", bg=C["bg3"], fg=C["txt2"],
            font=("Consolas", 8),
        ).pack(side="left")

        self._status_lbl = tk.Label(
            hdr, text="  INICIANDO  ",
            bg=C["bg4"], fg=C["warn"],
            font=("Consolas", 8, "bold"),
            padx=6, pady=2,
        )
        self._status_lbl.pack(side="right")

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=18, pady=(10, 0))

        # Cuerpo: métricas del último test + panel de URL
        body = tk.Frame(self, bg=C["bg3"])
        body.pack(fill="x", padx=18, pady=(12, 0))

        metrics_frame = tk.Frame(body, bg=C["bg3"])
        metrics_frame.pack(side="left", fill="both", expand=True)

        self._m_down = self._metric_col(metrics_frame, "DESCARGA", C["cyan"],  "Mbps")
        self._m_up   = self._metric_col(metrics_frame, "SUBIDA",   C["pink"],  "Mbps")
        self._m_ping = self._metric_col(metrics_frame, "PING",     C["accent"], "ms")

        # Panel derecho con URL de acceso
        url_frame = tk.Frame(
            body, bg=C["bg4"],
            highlightbackground=C["border"], highlightthickness=1,
        )
        url_frame.pack(side="right", padx=(12, 0), pady=4, ipadx=14, ipady=8)

        tk.Label(
            url_frame, text="ACCESO DESDE LA RED",
            bg=C["bg4"], fg=C["txt3"], font=("Consolas", 7),
        ).pack(anchor="w", padx=12, pady=(8, 0))

        self._url_lbl = tk.Label(
            url_frame, text="Calculando…",
            bg=C["bg4"], fg=C["accent"],
            font=("Consolas", 11, "bold"), cursor="hand2",
        )
        self._url_lbl.pack(anchor="w", padx=12)
        self._url_lbl.bind("<Button-1>", lambda e: self._open_browser())

        btn_row = tk.Frame(url_frame, bg=C["bg4"])
        btn_row.pack(padx=12, pady=(8, 8), anchor="w")

        self._btn_open = tk.Button(
            btn_row, text="Abrir en navegador",
            bg=C["accent"], fg="#0d1117",
            font=("Consolas", 8, "bold"),
            relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=self._open_browser,
        )
        self._btn_open.pack(side="left", padx=(0, 6))

        self._btn_copy = tk.Button(
            btn_row, text="Copiar URL",
            bg=C["bg3"], fg=C["txt2"],
            font=("Consolas", 8),
            relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=self._copy_url,
        )
        self._btn_copy.pack(side="left")

        # Nota de dominio
        tk.Label(
            self,
            text=(
                "Comparte la URL con cualquier equipo del dominio para realizar "
                "el test de velocidad desde su navegador."
            ),
            bg=C["bg3"], fg=C["txt3"],
            font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(8, 14))

    def _metric_col(self, parent, title: str, color: str, unit: str) -> tk.Label:
        col = tk.Frame(parent, bg=C["bg3"])
        col.pack(side="left", padx=(0, 24))
        tk.Label(col, text=title, bg=C["bg3"], fg=C["txt3"],
                 font=("Consolas", 7)).pack(anchor="w")
        lbl = tk.Label(col, text="—",
                       bg=C["bg3"], fg=color,
                       font=("Consolas", 20, "bold"))
        lbl.pack(anchor="w")
        tk.Label(col, text=unit, bg=C["bg3"], fg=C["txt3"],
                 font=("Consolas", 7)).pack(anchor="w")
        return lbl

    # ── Acciones ──────────────────────────────────────────────

    def _refresh_status(self):
        if web_server.is_running():
            self._status_lbl.config(text="  EN LÍNEA  ", fg=C["ok"], bg="#0d2b15")
            self._url_lbl.config(text=web_server.get_server_url())
        else:
            self._status_lbl.config(text="  SIN SERVICIO  ", fg=C["warn"], bg=C["bg4"])
            self._url_lbl.config(text="No disponible")

    def _open_browser(self):
        webbrowser.open(web_server.get_localhost_url())

    def _copy_url(self):
        url = web_server.get_server_url()
        self.clipboard_clear()
        self.clipboard_append(url)
        self._btn_copy.config(text="¡Copiado!")
        self.after(2000, lambda: self._btn_copy.config(text="Copiar URL"))

    # ── API pública ───────────────────────────────────────────

    def notify_server_ready(self):
        """Llamar tras confirmar que el servidor arrancó."""
        self._refresh_status()

    def update_last_result(self, download: float, upload: float, ping: float):
        """Actualizar métricas cuando el usuario completa un test en el navegador."""
        self._m_down.config(text=f"{download:.1f}")
        self._m_up.config(text=f"{upload:.1f}")
        self._m_ping.config(text=f"{ping:.0f}")
