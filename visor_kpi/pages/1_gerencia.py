"""
pages/1_gerencia.py — Vista Consolidada Gerencial
Ranking completo de vendedores + análisis por zona
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
from src.kpi_engine      import kpi_ventas_periodo, kpi_por_vendedor, kpi_evolucion_mensual
from components.kpi_card import render_kpi_card
from components.charts   import chart_barras_vendedores, chart_evolucion_ventas, chart_heatmap_ventas
from components.rankings import render_ranking_vendedores
from config import fmt_moneda, fmt_pct, COLORS

init_session_state()

if not check_data_available():
    st.error("No se encontró el archivo de datos. Ejecutá: `python data/mock/generate_mock_data.py`")
    st.stop()

filtros = render_sidebar_filters()
fecha_desde    = filtros["fecha_desde"]
fecha_hasta    = filtros["fecha_hasta"]
vendedores_sel = filtros["vendedores_sel"] or None
zonas_sel      = filtros["zonas_sel"]      or None
canales_sel    = filtros["canales_sel"]    or None

with st.spinner("Cargando vista gerencial..."):
    data     = load_data()
    df       = get_filtered_data(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    df_ant   = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    obj_df   = data["objetivos"]

st.markdown(
    f"""
    <h1 style="font-size:22px;font-weight:700;color:{COLORS['text_primary']};
               padding-bottom:12px;border-bottom:2px solid {COLORS['border']};margin-bottom:20px">
        🏢 Vista Gerencial — Equipo Comercial
    </h1>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    render_sin_datos()

kv    = kpi_ventas_periodo(df, df_ant, obj_df, fecha_desde, fecha_hasta)
kv_df = kpi_por_vendedor(df, obj_df, df_ant, fecha_desde, fecha_hasta)

# Evolución: siempre últimos 12 meses hasta el fin del período seleccionado
from dateutil.relativedelta import relativedelta
evo_desde = fecha_hasta.replace(day=1) - relativedelta(months=11)
df_evo    = get_filtered_data(evo_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
evo   = kpi_evolucion_mensual(df_evo, obj_df)

# ── KPI Row ───────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_kpi_card("Ventas totales", fmt_moneda(kv["importe_total"]),
                    delta_pct=kv.get("importe_vs_anterior"),
                    objetivo=fmt_moneda(kv.get("objetivo_total",0)),
                    cumplimiento=kv.get("cumplimiento_pct"), icon="💰")
with c2:
    render_kpi_card("Ticket Promedio", fmt_moneda(kv["ticket_promedio"]),
                    icon="🎫")
with c3:
    n_verde = len(kv_df[kv_df["label_semaforo"]=="success"]) if not kv_df.empty else 0
    render_kpi_card("Vendedores en verde", str(n_verde),
                    cumplimiento=n_verde/12 if n_verde else 0, icon="🟢")
with c4:
    render_kpi_card("Transacciones", fmt_moneda(kv["transacciones_count"]).replace("$",""),
                    icon="📋")

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráfico evolución + Barras vendedores ─────────────────────
col1, col2 = st.columns([3, 2])
with col1:
    fig = chart_evolucion_ventas(evo, mostrar_objetivo=True, title="Evolución mensual del equipo")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
with col2:
    if not kv_df.empty:
        fig_bar = chart_barras_vendedores(kv_df, title="Cumplimiento por Vendedor")
        st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

# ── Ranking completo ──────────────────────────────────────────
st.markdown(
    f"<div class='section-title' style='margin-top:16px'>📋 Ranking Completo de Vendedores</div>",
    unsafe_allow_html=True,
)
render_ranking_vendedores(kv_df)

# ── Heatmap de actividad ──────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
fig_heat = chart_heatmap_ventas(df, title="Actividad comercial del equipo")
st.plotly_chart(fig_heat, use_container_width=True, config={"displayModeBar": False})

# ── Análisis por zona ─────────────────────────────────────────
st.markdown(
    f"<div class='section-title' style='margin-top:8px'>🗺️ Análisis por Zona</div>",
    unsafe_allow_html=True,
)
if "zona_vendedor" in df.columns:
    zona_df = df.groupby("zona_vendedor")["importe_neto"].sum().reset_index()
    zona_df.columns = ["Zona", "Ventas"]
    zona_df["Ventas_fmt"] = zona_df["Ventas"].apply(fmt_moneda)
    zona_df["Part. %"] = (zona_df["Ventas"] / zona_df["Ventas"].sum() * 100).round(1).astype(str) + "%"
    st.dataframe(zona_df[["Zona", "Ventas_fmt", "Part. %"]], use_container_width=True, hide_index=True)
