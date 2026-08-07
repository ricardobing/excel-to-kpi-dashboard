"""
pages/2_vendedores.py — Vista individual por vendedor
El vendedor ve sus propios KPIs, ranking y cartera.
"""

import os, sys
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

css_path = os.path.join(BASE_DIR, "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from components.filters  import render_sidebar_filters, init_session_state, render_sin_datos
from src.data_loader     import load_data, get_filtered_data, get_filtered_data_periodo_anterior, check_data_available
from src.kpi_engine      import (
    kpi_ventas_periodo, kpi_por_vendedor, kpi_clientes, kpi_productos,
    kpi_evolucion_mensual,
)
from components.kpi_card import render_kpi_card
from components.charts   import (
    chart_evolucion_ventas, chart_gauge_cumplimiento, chart_pareto,
)
from components.rankings import (
    render_ranking_vendedores, render_ranking_clientes,
    render_ranking_productos, render_posicion_ranking,
)
from config import fmt_moneda, fmt_pct, fmt_numero, COLORS

init_session_state()

if not check_data_available():
    st.error("No se encontró el archivo de datos.")
    st.stop()

filtros = render_sidebar_filters(mostrar_vendedor=True)
fecha_desde    = filtros["fecha_desde"]
fecha_hasta    = filtros["fecha_hasta"]
zonas_sel      = filtros["zonas_sel"]  or None
canales_sel    = filtros["canales_sel"] or None

with st.spinner("Cargando datos..."):
    data     = load_data()
    obj_df   = data["objetivos"]
    vend_df  = data["vendedores"]
    cli_df   = data["clientes"]
    prod_df  = data["productos"]

# ── Selector de vendedor ──────────────────────────────────────
vend_activos = vend_df[vend_df["activo"] == True].copy()
opciones_v   = {f"{r['nombre_completo']} ({r['zona']})": r["id_vendedor"]
                for _, r in vend_activos.iterrows()}

selected_label = st.selectbox(
    "👤 Seleccionar vendedor",
    options = list(opciones_v.keys()),
    key     = "_sel_vendedor_page",
)
vendedor_id   = opciones_v[selected_label]
vendedor_info = vend_activos[vend_activos["id_vendedor"] == vendedor_id].iloc[0]

# ── Cargar datos filtrados para ese vendedor ──────────────────
df     = get_filtered_data(fecha_desde, fecha_hasta, [vendedor_id], zonas_sel, canales_sel)
df_ant = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, [vendedor_id], zonas_sel, canales_sel)
df_eq  = get_filtered_data(fecha_desde, fecha_hasta, None, zonas_sel, canales_sel)
df_eq_ant = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, None, zonas_sel, canales_sel)

# ── Header del vendedor ───────────────────────────────────────
perfil_color = {
    "estrella": COLORS["success"],
    "estable":  COLORS["primary_light"],
    "desarrollo": COLORS["warning"],
    "problematico": COLORS["danger"],
}.get(vendedor_info.get("perfil", ""), COLORS["primary_light"])

st.markdown(
    f"""
    <div style="background:{COLORS['bg_card']};border-radius:12px;padding:20px;
                display:flex;align-items:center;gap:20px;margin-bottom:20px;
                border:1px solid {COLORS['border']}">
        <div style="width:64px;height:64px;border-radius:50%;background:{perfil_color}22;
                    display:flex;align-items:center;justify-content:center;font-size:28px;
                    border:2px solid {perfil_color}">
            👤
        </div>
        <div>
            <div style="font-size:20px;font-weight:700;color:{COLORS['text_primary']}">
                {vendedor_info['nombre_completo']}
            </div>
            <div style="font-size:13px;color:{COLORS['text_secondary']};margin-top:2px">
                🗺️ {vendedor_info['zona']} · 
                📅 {int(vendedor_info.get('antiguedad_años', 0))} años de antigüedad · 
                <span style="color:{perfil_color};font-weight:600;text-transform:capitalize">
                    {vendedor_info.get('perfil', '—')}
                </span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    render_sin_datos()

# ── KPIs ──────────────────────────────────────────────────────
kv     = kpi_ventas_periodo(df, df_ant, obj_df, fecha_desde, fecha_hasta)
kv_all = kpi_por_vendedor(df_eq, obj_df, df_eq_ant, fecha_desde, fecha_hasta)
kcli   = kpi_clientes(df, cli_df, df_ant, fecha_hasta)
kp     = kpi_productos(df, df_ant)
# Evolución: últimos 6 meses hasta el fin del período seleccionado
from dateutil.relativedelta import relativedelta
evo_desde = fecha_hasta.replace(day=1) - relativedelta(months=5)
df_evo    = get_filtered_data(evo_desde, fecha_hasta, [vendedor_id], zonas_sel, canales_sel)
evo    = kpi_evolucion_mensual(df_evo, obj_df, vendedor_id, n_meses=6)

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_kpi_card("Ventas del período", fmt_moneda(kv["importe_total"]),
                    delta_pct=kv.get("importe_vs_anterior"),
                    objetivo=fmt_moneda(kv.get("objetivo_total",0)),
                    cumplimiento=kv.get("cumplimiento_pct"), icon="💰")
with c2:
    render_kpi_card("Cumplimiento", fmt_pct(kv.get("cumplimiento_pct",0)),
                    objetivo="100%", cumplimiento=kv.get("cumplimiento_pct"), icon="🎯")
with c3:
    render_kpi_card("Clientes visitados", fmt_numero(kv["clientes_unicos"]),
                    icon="👥")
with c4:
    render_kpi_card("Ticket Promedio", fmt_moneda(kv["ticket_promedio"]), icon="🎫")

st.markdown("<br>", unsafe_allow_html=True)

# ── Gauge + Evolución personal ────────────────────────────────
col_g, col_evo = st.columns([1, 2])

with col_g:
    fig_gauge = chart_gauge_cumplimiento(
        valor = kv.get("cumplimiento_pct") or 0,
        label = "Mi Cumplimiento",
    )
    st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

with col_evo:
    fig_evo = chart_evolucion_ventas(
        evo,
        mostrar_objetivo=True,
        title=f"Evolución personal — últimos 6 meses",
    )
    st.plotly_chart(fig_evo, use_container_width=True, config={"displayModeBar": False})

# ── Posición en el equipo ─────────────────────────────────────
col_pos, col_rank = st.columns([1, 3])

with col_pos:
    if not kv_all.empty:
        fila = kv_all[kv_all["id_vendedor"] == vendedor_id]
        if not fila.empty:
            rank_act = int(fila.iloc[0].get("ranking_actual", 1))
            rank_ant = int(fila.iloc[0].get("ranking_anterior", rank_act))
            render_posicion_ranking(rank_act, rank_ant, len(kv_all))
        else:
            st.info("Sin ranking disponible.")

with col_rank:
    st.markdown(
        f"<div style='font-size:13px;font-weight:600;color:{COLORS['text_secondary']};margin-bottom:8px'>"
        f"📋 Ranking del Equipo</div>",
        unsafe_allow_html=True,
    )
    render_ranking_vendedores(kv_all, max_rows=12)

st.markdown("<br>", unsafe_allow_html=True)

# ── Mis clientes + Pareto de productos ───────────────────────
col_cli, col_prod = st.columns(2)

with col_cli:
    st.markdown(
        f"<div class='section-title' style='font-size:14px'>🏪 Mis Clientes</div>",
        unsafe_allow_html=True,
    )
    render_ranking_clientes(kcli, top_n=15)

with col_prod:
    st.markdown(
        f"<div class='section-title' style='font-size:14px'>📦 Mis Top Productos</div>",
        unsafe_allow_html=True,
    )
    render_ranking_productos(kp, top_n=10)

st.markdown("<br>", unsafe_allow_html=True)

# ── Clientes en riesgo ────────────────────────────────────────
st.markdown(
    f"<div class='section-title' style='color:{COLORS['danger']}'>⚠️ Clientes en Riesgo</div>",
    unsafe_allow_html=True,
)
if not kcli.empty:
    en_riesgo = kcli[kcli["flag_en_riesgo"] == True].copy()
    if en_riesgo.empty:
        st.success("✅ No tenés clientes en riesgo en este período.")
    else:
        render_ranking_clientes(en_riesgo, top_n=20)
else:
    st.info("Sin datos de clientes.")
