"""
pages/4_productos.py — Análisis de Productos
Treemap, Pareto, ranking y productos sin movimiento
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
from src.kpi_engine      import kpi_productos
from components.kpi_card import render_kpi_card
from components.charts   import chart_treemap_productos, chart_pareto
from components.rankings import render_ranking_productos
from config import fmt_moneda, fmt_pct, fmt_numero, COLORS
from datetime import timedelta
import pandas as pd

init_session_state()

if not check_data_available():
    st.error("No se encontró el archivo de datos.")
    st.stop()

filtros = render_sidebar_filters()
fecha_desde    = filtros["fecha_desde"]
fecha_hasta    = filtros["fecha_hasta"]
vendedores_sel = filtros["vendedores_sel"] or None
zonas_sel      = filtros["zonas_sel"]      or None
canales_sel    = filtros["canales_sel"]    or None

with st.spinner("Analizando productos..."):
    data    = load_data()
    df      = get_filtered_data(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    df_ant  = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    prod_df = data["productos"]

st.markdown(
    f"""
    <h1 style="font-size:22px;font-weight:700;color:{COLORS['text_primary']};
               padding-bottom:12px;border-bottom:2px solid {COLORS['border']};margin-bottom:20px">
        📦 Análisis de Productos
    </h1>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    render_sin_datos()

kp = kpi_productos(df, df_ant)

# ── KPI Row ───────────────────────────────────────────────────
n_activos    = prod_df[prod_df["activo"] == True]["id_producto"].nunique()
n_cats       = prod_df["categoria"].nunique() if "categoria" in prod_df.columns else 0
n_sin_movim  = 0
if not kp.empty and "dias_sin_venta" not in kp.columns:
    # Calcular productos sin movimiento en últimos 60 días
    ultimo_venta = df.groupby("id_producto")["fecha"].max()
    corte_60     = pd.Timestamp(fecha_hasta) - pd.Timedelta(days=60)
    prod_activos = prod_df[prod_df["activo"] == True]["id_producto"].tolist()
    n_sin_movim  = sum(
        1 for p in prod_activos
        if p not in ultimo_venta.index or ultimo_venta[p] < corte_60
    )

ticket_prom_prod = kp["importe_total"].mean() if not kp.empty else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_kpi_card("SKUs activos", fmt_numero(n_activos), icon="📦")
with c2:
    render_kpi_card("Categorías", str(n_cats), icon="🏷️")
with c3:
    render_kpi_card("Sin movimiento (60d)", str(n_sin_movim),
                    cumplimiento=1 if n_sin_movim == 0 else 0.5, icon="⚠️")
with c4:
    render_kpi_card("Venta prom. por SKU", fmt_moneda(ticket_prom_prod), icon="📈")

st.markdown("<br>", unsafe_allow_html=True)

# ── Treemap + Pareto ──────────────────────────────────────────
col_tree, col_pareto = st.columns(2)

with col_tree:
    fig_tree = chart_treemap_productos(kp, title="Productos por Categoría — Tamaño = Ventas")
    st.plotly_chart(fig_tree, use_container_width=True, config={"displayModeBar": False})

with col_pareto:
    fig_pareto_prod = chart_pareto(
        kp,
        titulo     = "Pareto de Productos",
        col_nombre = "descripcion",
        col_valor  = "importe_total",
        top_n      = 30,
    )
    st.plotly_chart(fig_pareto_prod, use_container_width=True, config={"displayModeBar": False})

# ── Filtro por categoría ──────────────────────────────────────
if not kp.empty and "categoria" in kp.columns:
    cats_disponibles = sorted(kp["categoria"].unique().tolist())
    cat_sel = st.multiselect(
        "🏷️ Filtrar por categoría:",
        cats_disponibles,
        default=[],
        key="_cat_prod_filter",
    )
    kp_filtrado = kp[kp["categoria"].isin(cat_sel)] if cat_sel else kp.copy()
else:
    kp_filtrado = kp.copy()

# ── Tabla de productos ────────────────────────────────────────
st.markdown(
    f"<div class='section-title' style='margin-top:8px'>📋 Ranking de Productos</div>",
    unsafe_allow_html=True,
)
render_ranking_productos(kp_filtrado, top_n=60)

st.markdown("<br>", unsafe_allow_html=True)

# ── Productos sin movimiento y con mayor crecimiento ─────────
col_sin, col_crec = st.columns(2)

with col_sin:
    st.markdown(
        f"<div style='font-size:14px;font-weight:600;color:{COLORS['danger']};margin-bottom:12px'>"
        f"🛑 Productos sin Movimiento (60 días)</div>",
        unsafe_allow_html=True,
    )
    if not kp.empty:
        ultimo_venta = df.groupby("id_producto")["fecha"].max().reset_index()
        ultimo_venta.columns = ["id_producto", "ultima_venta"]
        kp_sin = kp.merge(ultimo_venta, on="id_producto", how="left")
        corte_60 = pd.Timestamp(fecha_hasta) - pd.Timedelta(days=60)
        sin_mov  = kp_sin[kp_sin["ultima_venta"] < corte_60].copy()
        if sin_mov.empty:
            st.success("✅ Todos los productos tienen movimiento reciente.")
        else:
            render_ranking_productos(sin_mov, top_n=15)

with col_crec:
    st.markdown(
        f"<div style='font-size:14px;font-weight:600;color:{COLORS['success']};margin-bottom:12px'>"
        f"🚀 Productos con Mayor Crecimiento</div>",
        unsafe_allow_html=True,
    )
    if not kp.empty and "vs_periodo_anterior" in kp.columns:
        crec = kp[kp["vs_periodo_anterior"].fillna(0) > 0.10].sort_values(
            "vs_periodo_anterior", ascending=False
        ).head(15)
        if crec.empty:
            st.info("Sin crecimiento significativo en este período.")
        else:
            render_ranking_productos(crec, top_n=15)
    else:
        st.info("Seleccioná un período con datos anteriores para ver crecimiento.")
