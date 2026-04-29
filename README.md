[README.md](https://github.com/user-attachments/files/27220286/README.md)
# NetCheck Pro

**Diagnóstico inteligente de redes LAN/WAN para Windows**

[![Build](https://github.com/malejorp-lang/netcheck-pro/actions/workflows/build.yml/badge.svg)](https://github.com/malejorp-lang/netcheck-pro/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/malejorp-lang/netcheck-pro)](https://github.com/malejorp-lang/netcheck-pro/releases/latest)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## Descarga

👉 **[Descargar NetCheckPro.exe](https://github.com/malejorp-lang/netcheck-pro/releases/latest)**

No requiere instalación. No requiere Python. Doble clic y listo.

---

## ¿Qué hace?

NetCheck Pro analiza automáticamente tu red al abrirse y muestra:

| Métrica | Descripción |
|---|---|
| IP Local | Dirección IP del equipo en la red |
| Gateway | Router/puerta de enlace detectada |
| DNS activo | Servidor DNS en uso |
| Estado LAN | OK / Inestable / Caído |
| Estado WAN | Conectividad a Internet |
| Latencia LAN | Tiempo de respuesta al gateway |
| Latencia WAN | Tiempo de respuesta a Internet |
| Jitter | Variación de latencia (estabilidad) |
| Dispositivos | Equipos activos en la red local |

### Diagnóstico inteligente

La aplicación no solo muestra datos — los **interpreta**:

- `Alta variación de latencia en LAN → posible problema WiFi`
- `LAN OK pero WAN caída → problema en el ISP o CPE`
- `Jitter alto + WiFi → interferencia de canal inalámbrico`

---

## Instalación

### Opción A — .exe directo (recomendado)
1. Descarga `NetCheckPro.exe` desde [Releases](https://github.com/malejorp-lang/netcheck-pro/releases/latest)
2. Doble clic para ejecutar
3. Acepta el UAC (requiere admin para comandos de red)

### Opción B — Desde código fuente
```bash
git clone https://github.com/malejorp-lang/netcheck-pro.git
cd netcheck-pro/src
python main_app.py
```
Requiere Python 3.10+ con tkinter.

---

## Arquitectura

```
src/
├── entry.py              # Punto de entrada del .exe (auto-elevación UAC)
├── main_app.py           # Inicialización de la aplicación
├── core/
│   ├── network.py        # Detección de red (IP, gateway, DNS, WiFi, ARP)
│   ├── analyzer.py       # Medición (latencia, jitter, pérdida de paquetes)
│   ├── correlator.py     # Motor de diagnóstico inteligente
│   └── profiler.py       # Perfil del sistema
└── gui/
    └── main_window_tk.py # Dashboard (tkinter puro, sin dependencias)
```

---

## Compatibilidad

| Entorno | Soporte |
|---|---|
| Windows 11 | ✅ Completo |
| Windows 10 | ✅ Completo |
| Equipos corporativos | ✅ Sin scripts externos |
| Dominios con GPO | ✅ .exe firmable |
| Python de Microsoft Store | N/A (el .exe no necesita Python) |

---

## Roadmap

- [ ] Historial de métricas (SQLite)
- [ ] Gráficos de latencia en tiempo real
- [ ] Alertas de Windows cuando la red se degrada
- [ ] Exportar reporte a PDF
- [ ] Instalador MSI para Program Files
- [ ] Firma de código (certificado EV)
- [ ] Distribución en Microsoft Store

---

## Licencia

MIT © 2025 malejorp-lang
