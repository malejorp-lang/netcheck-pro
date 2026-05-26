"""
storage/database.py
-------------------
Base de datos SQLite local para NetCheck Pro.
Guarda historial de diagnosticos, baseline, rachas y logros.
Se crea automaticamente en AppData del usuario.
"""

import sqlite3, os, json
from datetime import datetime, date

# Intentar AppData primero, si falla usar carpeta del ejecutable
try:
    _base = os.environ.get("APPDATA", "")
    if not _base:
        raise ValueError("Sin APPDATA")
    DB_DIR = os.path.join(_base, "NetCheckPro")
    os.makedirs(DB_DIR, exist_ok=True)
    # Verificar que tenemos permisos de escritura
    _test = os.path.join(DB_DIR, ".test")
    open(_test, "w").close()
    os.remove(_test)
except Exception:
    # Fallback: carpeta junto al ejecutable
    DB_DIR = os.path.join(
        os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, "frozen", False) else __file__
        )), "data"
    )

DB_PATH = os.path.join(DB_DIR, "netcheck.db")


def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    """Crea todas las tablas si no existen. Ejecutar al iniciar la app."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT NOT NULL,
            local_ip        TEXT, gateway TEXT, dns_primary TEXT,
            connection_type TEXT, adapter_name TEXT,
            latency_lan_ms  REAL, latency_wan_ms REAL,
            jitter_ms       REAL, packet_loss_pct REAL,
            download_mbps   REAL, upload_mbps REAL,
            lan_reachable   INTEGER, wan_reachable INTEGER,
            wifi_ssid       TEXT, wifi_signal_dbm INTEGER,
            wifi_channel    INTEGER, wifi_band TEXT,
            health_score    INTEGER, lan_status TEXT, wan_status TEXT,
            primary_finding TEXT, recommendation TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS baseline (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            calculated_at       TEXT NOT NULL,
            avg_latency_lan_ms  REAL, avg_latency_wan_ms REAL,
            avg_jitter_ms       REAL, avg_packet_loss_pct REAL,
            avg_download_mbps   REAL, avg_upload_mbps REAL,
            avg_health_score    REAL, samples_count INTEGER
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS streaks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT NOT NULL UNIQUE,
            ran_diagnostic  INTEGER DEFAULT 0,
            health_score    INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            achievement_id  TEXT NOT NULL UNIQUE,
            unlocked_at     TEXT NOT NULL,
            notified        INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# ─── SNAPSHOTS ────────────────────────────────────────────────────

def save_snapshot(data: dict) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO snapshots (
            timestamp, local_ip, gateway, dns_primary,
            connection_type, adapter_name,
            latency_lan_ms, latency_wan_ms, jitter_ms,
            packet_loss_pct, download_mbps, upload_mbps,
            lan_reachable, wan_reachable,
            wifi_ssid, wifi_signal_dbm, wifi_channel, wifi_band,
            health_score, lan_status, wan_status,
            primary_finding, recommendation
        ) VALUES (
            :timestamp, :local_ip, :gateway, :dns_primary,
            :connection_type, :adapter_name,
            :latency_lan_ms, :latency_wan_ms, :jitter_ms,
            :packet_loss_pct, :download_mbps, :upload_mbps,
            :lan_reachable, :wan_reachable,
            :wifi_ssid, :wifi_signal_dbm, :wifi_channel, :wifi_band,
            :health_score, :lan_status, :wan_status,
            :primary_finding, :recommendation
        )
    """, data)
    snapshot_id = c.lastrowid
    conn.commit()
    conn.close()
    return snapshot_id


def get_snapshots(limit: int = 50) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_snapshots_last_days(days: int = 7) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM snapshots
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp ASC
    """, (f"-{days} days",))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_snapshot_count() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM snapshots")
    count = c.fetchone()[0]
    conn.close()
    return count


# ─── BASELINE ─────────────────────────────────────────────────────

def calculate_and_save_baseline() -> dict:
    """Calcula baseline promediando los ultimos 10 snapshots."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT
            AVG(latency_lan_ms)  as avg_lat_lan,
            AVG(latency_wan_ms)  as avg_lat_wan,
            AVG(jitter_ms)       as avg_jitter,
            AVG(packet_loss_pct) as avg_loss,
            AVG(download_mbps)   as avg_download,
            AVG(upload_mbps)     as avg_upload,
            AVG(health_score)    as avg_score,
            COUNT(*)             as total
        FROM (SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 10)
    """)
    row = c.fetchone()
    if not row or row["total"] < 3:
        conn.close()
        return {}

    baseline = {
        "calculated_at":       datetime.now().isoformat(),
        "avg_latency_lan_ms":  round(row["avg_lat_lan"]  or 0, 2),
        "avg_latency_wan_ms":  round(row["avg_lat_wan"]  or 0, 2),
        "avg_jitter_ms":       round(row["avg_jitter"]   or 0, 2),
        "avg_packet_loss_pct": round(row["avg_loss"]     or 0, 2),
        "avg_download_mbps":   round(row["avg_download"] or 0, 2),
        "avg_upload_mbps":     round(row["avg_upload"]   or 0, 2),
        "avg_health_score":    round(row["avg_score"]    or 0, 2),
        "samples_count":       row["total"],
    }

    c.execute("""
        INSERT INTO baseline (
            calculated_at, avg_latency_lan_ms, avg_latency_wan_ms,
            avg_jitter_ms, avg_packet_loss_pct,
            avg_download_mbps, avg_upload_mbps,
            avg_health_score, samples_count
        ) VALUES (
            :calculated_at, :avg_latency_lan_ms, :avg_latency_wan_ms,
            :avg_jitter_ms, :avg_packet_loss_pct,
            :avg_download_mbps, :avg_upload_mbps,
            :avg_health_score, :samples_count
        )
    """, baseline)
    conn.commit()
    conn.close()
    return baseline


def get_latest_baseline() -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM baseline ORDER BY calculated_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


# ─── STREAKS ──────────────────────────────────────────────────────

def register_daily_diagnostic(health_score: int):
    """Registra que hoy se hizo un diagnostico."""
    today = date.today().isoformat()
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO streaks (date, ran_diagnostic, health_score)
        VALUES (?, 1, ?)
        ON CONFLICT(date) DO UPDATE SET
            ran_diagnostic = 1,
            health_score = MAX(health_score, excluded.health_score)
    """, (today, health_score))
    conn.commit()
    conn.close()


def get_current_streak() -> int:
    """Calcula dias consecutivos con diagnostico hasta hoy."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT date FROM streaks WHERE ran_diagnostic=1 ORDER BY date DESC")
    rows = [r["date"] for r in c.fetchall()]
    conn.close()

    if not rows:
        return 0

    streak = 0
    check = date.today()
    for ds in rows:
        d = date.fromisoformat(ds)
        if d == check:
            streak += 1
            check = date.fromordinal(check.toordinal() - 1)
        elif d == date.fromordinal(check.toordinal() - 1):
            streak += 1
            check = date.fromordinal(d.toordinal() - 1)
        else:
            break
    return streak


def get_streak_history(days: int = 30) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT date, ran_diagnostic, health_score FROM streaks
        ORDER BY date DESC LIMIT ?
    """, (days,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── ACHIEVEMENTS ─────────────────────────────────────────────────

def unlock_achievement(achievement_id: str) -> bool:
    """
    Desbloquea un logro.
    Retorna True si es nuevo, False si ya existia.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM achievements WHERE achievement_id=?", (achievement_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute("""
        INSERT INTO achievements (achievement_id, unlocked_at, notified)
        VALUES (?, ?, 0)
    """, (achievement_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True


def get_unlocked_achievements() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT achievement_id, unlocked_at FROM achievements")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_pending_notifications() -> list:
    """Logros desbloqueados que aun no se mostraron al usuario."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT achievement_id FROM achievements WHERE notified=0")
    rows = [r["achievement_id"] for r in c.fetchall()]
    conn.close()
    return rows


def mark_achievement_notified(achievement_id: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE achievements SET notified=1 WHERE achievement_id=?", (achievement_id,))
    conn.commit()
    conn.close()


# ─── CONFIG ───────────────────────────────────────────────────────

def get_config(key: str, default=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        try: return json.loads(row["value"])
        except: return row["value"]
    return default


def set_config(key: str, value):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO config (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, json.dumps(value)))
    conn.commit()
    conn.close()
