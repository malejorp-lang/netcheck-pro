"""
storage/achievements_def.py
---------------------------
Definicion de todos los logros de NetCheck Pro.
Cada logro tiene: id, titulo, descripcion, icono, condicion.
"""

ACHIEVEMENTS = [
    {
        "id":          "first_steps",
        "title":       "Primeros pasos",
        "description": "Ejecutaste tu primer diagnostico",
        "icon":        "🚀",
        "secret":      False,
    },
    {
        "id":          "early_adopter",
        "title":       "Early Adopter",
        "description": "Uno de los primeros usuarios de NetCheck Pro",
        "icon":        "⭐",
        "secret":      False,
    },
    {
        "id":          "diagnostic_10",
        "title":       "Diagnosticador",
        "description": "Ejecutaste 10 diagnosticos",
        "icon":        "🔍",
        "secret":      False,
    },
    {
        "id":          "diagnostic_50",
        "title":       "Diagnostic Pro",
        "description": "Ejecutaste 50 diagnosticos",
        "icon":        "🏆",
        "secret":      False,
    },
    {
        "id":          "diagnostic_100",
        "title":       "Power User",
        "description": "Ejecutaste 100 diagnosticos",
        "icon":        "💪",
        "secret":      False,
    },
    {
        "id":          "streak_7",
        "title":       "Early Bird",
        "description": "7 dias consecutivos con diagnostico",
        "icon":        "🔥",
        "secret":      False,
    },
    {
        "id":          "streak_30",
        "title":       "Constante",
        "description": "30 dias consecutivos con diagnostico",
        "icon":        "🔥🔥",
        "secret":      False,
    },
    {
        "id":          "streak_100",
        "title":       "Iron Connection",
        "description": "100 dias consecutivos con diagnostico",
        "icon":        "🏅",
        "secret":      False,
    },
    {
        "id":          "perfect_score",
        "title":       "Red Perfecta",
        "description": "Obtuviste un Health Score de 100/100",
        "icon":        "💯",
        "secret":      False,
    },
    {
        "id":          "speed_demon",
        "title":       "Speed Demon",
        "description": "Velocidad de descarga mayor a 500 Mbps",
        "icon":        "⚡",
        "secret":      False,
    },
    {
        "id":          "stable_master",
        "title":       "Stable Master",
        "description": "Jitter menor a 5ms por 30 dias consecutivos",
        "icon":        "📊",
        "secret":      False,
    },
    {
        "id":          "wifi_wizard",
        "title":       "WiFi Wizard",
        "description": "Detectaste y usaste banda 5GHz",
        "icon":        "📡",
        "secret":      False,
    },
    {
        "id":          "problem_solver",
        "title":       "Problem Solver",
        "description": "Usaste el wizard de problemas 10 veces",
        "icon":        "🛠️",
        "secret":      False,
    },
    {
        "id":          "night_owl",
        "title":       "Night Owl",
        "description": "Ejecutaste un diagnostico despues de medianoche",
        "icon":        "🦉",
        "secret":      True,
    },
    {
        "id":          "founding_member",
        "title":       "Founding Member",
        "description": "Usuario beta de NetCheck Pro",
        "icon":        "👑",
        "secret":      False,
    },
]

ACHIEVEMENTS_BY_ID = {a["id"]: a for a in ACHIEVEMENTS}


def get_achievement(achievement_id: str) -> dict:
    """Retorna la definicion de un logro por su ID."""
    return ACHIEVEMENTS_BY_ID.get(achievement_id, {})


def check_achievements(snapshot_count: int, streak: int,
                       health_score: int, download_mbps: float,
                       jitter_ms: float, wifi_band: str,
                       hour: int, wizard_uses: int) -> list:
    """
    Verifica que logros deben desbloquearse segun las metricas actuales.
    Retorna lista de IDs de logros a desbloquear.
    """
    to_unlock = []

    # Basados en cantidad de diagnosticos
    if snapshot_count >= 1:   to_unlock.append("first_steps")
    if snapshot_count >= 1:   to_unlock.append("early_adopter")
    if snapshot_count >= 10:  to_unlock.append("diagnostic_10")
    if snapshot_count >= 50:  to_unlock.append("diagnostic_50")
    if snapshot_count >= 100: to_unlock.append("diagnostic_100")

    # Basados en rachas
    if streak >= 7:   to_unlock.append("streak_7")
    if streak >= 30:  to_unlock.append("streak_30")
    if streak >= 100: to_unlock.append("streak_100")

    # Basados en metricas
    if health_score >= 100:   to_unlock.append("perfect_score")
    if download_mbps >= 500:  to_unlock.append("speed_demon")
    if jitter_ms < 5 and streak >= 30: to_unlock.append("stable_master")
    if wifi_band == "5GHz":   to_unlock.append("wifi_wizard")
    if hour >= 0 and hour < 5: to_unlock.append("night_owl")
    if wizard_uses >= 10:     to_unlock.append("problem_solver")

    return to_unlock
