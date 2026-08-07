"""
config.py — Configuración global del Visor KPI Comercial
Colores, constantes, funciones de formato, rutas y temas Plotly.
"""

import os
from datetime import date
from dateutil.relativedelta import relativedelta

# ─── COLORES ──────────────────────────────────────────────────────────────────
COLORS = {
    # Primarios
    "primary":        "#1B3A6B",
    "primary_light":  "#2E5FA3",
    "accent":         "#00C49F",

    # Semáforo de performance
    "success":        "#00C49F",
    "warning":        "#FFB347",
    "danger":         "#E84855",

    # Neutros
    "bg_dark":        "#0F1923",
    "bg_card":        "#1A2535",
    "bg_card_hover":  "#243044",
    "text_primary":   "#F0F4F8",
    "text_secondary": "#8899AA",
    "border":         "#2D3F55",

    # Gráficos (secuencia para series múltiples)
    "chart_seq": [
        "#2E5FA3", "#00C49F", "#FFB347",
        "#E84855", "#9B59B6", "#3498DB",
        "#1ABC9C", "#F39C12"
    ],
}

# ─── UMBRALES DE PERFORMANCE ──────────────────────────────────────────────────
THRESHOLDS = {
    "cumplimiento_ok":      1.00,   # 100% → verde
    "cumplimiento_warning": 0.80,   # 80%  → naranja
    # debajo de 0.80 → rojo

    "caida_critica":       -0.20,   # -20% vs período anterior = alerta
    "crecimiento_notable":  0.15,   # +15% vs período anterior = destacar

    "pareto_acumulado":     0.80,   # 80% del volumen = clientes A
    "pareto_B":             0.95,   # 80-95% = clientes B, >95% = C
}

# ─── RUTAS ────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "raw", "mock_data.xlsx")

# ─── CONSTANTES DE NEGOCIO ────────────────────────────────────────────────────
ZONAS   = ["GBA Norte", "GBA Sur", "Interior"]
CANALES = ["Canal Tradicional", "Supermercadismo", "Mayorista", "HoReCa"]

EMPRESA = {
    "nombre":    "Distribuidora Del Sur S.A.",
    "periodo_inicio": date(2023, 1, 1),
    "periodo_fin":    date(2026, 3, 31),
}

# ─── FORMATEO DE NÚMEROS ──────────────────────────────────────────────────────

def fmt_moneda(valor: float) -> str:
    """Ej: $1.284.500 (estilo argentino, sin decimales si >1000)"""
    if valor is None:
        return "$0"
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "$0"
    signo = "-" if valor < 0 else ""
    abs_val = abs(valor)
    if abs_val >= 1_000:
        s = f"{abs_val:,.0f}".replace(",", ".")
    else:
        s = f"{abs_val:.2f}".replace(".", ",")
    return f"{signo}${s}"


def fmt_pct(valor: float, decimales: int = 1) -> str:
    """Ej: 84.2%"""
    if valor is None:
        return "—"
    try:
        return f"{float(valor) * 100:.{decimales}f}%"
    except (TypeError, ValueError):
        return "—"


def fmt_numero(valor: float) -> str:
    """Ej: 1.284 (separador de miles)"""
    if valor is None:
        return "0"
    try:
        return f"{float(valor):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def fmt_delta(valor: float) -> str:
    """Ej: ▲ +8.2% o ▼ -3.1%"""
    if valor is None:
        return "—"
    try:
        pct = float(valor) * 100
    except (TypeError, ValueError):
        return "—"
    if pct > 0.05:
        return f"▲ +{pct:.1f}%"
    elif pct < -0.05:
        return f"▼ {pct:.1f}%"
    return "— 0.0%"


def fmt_delta_html(valor: float) -> str:
    """Delta con color HTML. Verde si positivo, rojo si negativo."""
    if valor is None:
        return "<span style='color:#8899AA'>—</span>"
    try:
        pct = float(valor) * 100
    except (TypeError, ValueError):
        return "<span style='color:#8899AA'>—</span>"
    if pct > 0.05:
        return f"<span style='color:#00C49F'>▲ +{pct:.1f}%</span>"
    elif pct < -0.05:
        return f"<span style='color:#E84855'>▼ {pct:.1f}%</span>"
    return "<span style='color:#8899AA'>— 0.0%</span>"


# ─── SEMÁFORO ─────────────────────────────────────────────────────────────────

def get_color_semaforo(cumplimiento: float) -> str:
    """Retorna color hex según nivel de cumplimiento."""
    if cumplimiento is None:
        return COLORS["danger"]
    try:
        c = float(cumplimiento)
    except (TypeError, ValueError):
        return COLORS["danger"]
    if c >= THRESHOLDS["cumplimiento_ok"]:
        return COLORS["success"]
    elif c >= THRESHOLDS["cumplimiento_warning"]:
        return COLORS["warning"]
    return COLORS["danger"]


def get_label_semaforo(cumplimiento: float) -> str:
    """Retorna 'success' | 'warning' | 'danger'."""
    if cumplimiento is None:
        return "danger"
    try:
        c = float(cumplimiento)
    except (TypeError, ValueError):
        return "danger"
    if c >= THRESHOLDS["cumplimiento_ok"]:
        return "success"
    elif c >= THRESHOLDS["cumplimiento_warning"]:
        return "warning"
    return "danger"


def get_emoji_semaforo(cumplimiento: float) -> str:
    label = get_label_semaforo(cumplimiento)
    return {"success": "🟢", "warning": "🟡", "danger": "🔴"}.get(label, "⚪")


# ─── PERÍODOS PREDEFINIDOS ─────────────────────────────────────────────────────

def get_periodos(referencia: date | None = None) -> dict:
    """Períodos predefinidos relativos a `referencia` (por defecto, hoy).

    La app pasa como referencia la última fecha CON DATOS: si el dataset es
    histórico, 'Este mes' es el último mes con ventas y nunca un rango vacío.
    """
    hoy = referencia or date.today()
    primer_dia_mes = hoy.replace(day=1)
    ultimo_dia_mes_ant = primer_dia_mes - relativedelta(days=1)
    primer_dia_mes_ant = ultimo_dia_mes_ant.replace(day=1)
    return {
        "Este mes":         (primer_dia_mes, hoy),
        "Mes anterior":     (primer_dia_mes_ant, ultimo_dia_mes_ant),
        "Último trimestre": (hoy - relativedelta(months=3), hoy),
        "Este año":         (hoy.replace(month=1, day=1), hoy),
        "Año anterior":     (date(hoy.year - 1, 1, 1), date(hoy.year - 1, 12, 31)),
        "Personalizado":    None,
    }


def get_periodo_anterior(fecha_desde: date, fecha_hasta: date):
    """Calcula el período anterior equivalente en duración."""
    duracion = (fecha_hasta - fecha_desde).days + 1
    nueva_hasta = fecha_desde - relativedelta(days=1)
    nueva_desde = nueva_hasta - relativedelta(days=duracion - 1)
    return nueva_desde, nueva_hasta


# ─── PLOTLY THEME ─────────────────────────────────────────────────────────────
PLOTLY_THEME = {
    "paper_bgcolor": COLORS["bg_card"],
    "plot_bgcolor":  COLORS["bg_card"],
    "font":          {"color": COLORS["text_primary"], "family": "Inter, sans-serif", "size": 12},
    "margin":        dict(l=20, r=20, t=40, b=20),
}
