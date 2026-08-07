"""
pages/3_clientes.py — Análisis de cartera de clientes
Pareto, scatter, tabla filtrable y detalle por cliente
"""

import os, sys
import streamlit as st
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

css_path = os.path.join(BASE_DIR, "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from components.filters  import render_sidebar_filters, init_session_state, render_sin_datos
from src.data_loader     import load_data, get_filtered_data, get_filtered_data_periodo_anterior, check_data_available
from src.kpi_engine      import kpi_cobertura_clientes, kpi_clientes, kpi_evolucion_mensual
from src.pareto          import get_concentracion_pareto
from components.kpi_card import render_kpi_card
from components.charts   import chart_pareto, chart_scatter_clientes, chart_evolucion_ventas
from components.rankings import render_ranking_clientes
from config import fmt_moneda, fmt_pct, fmt_numero, COLORS

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

with st.spinner("Analizando cartera de clientes..."):
    data   = load_data()
    df     = get_filtered_data(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    df_ant = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
    cli_df = data["clientes"]

st.markdown(
    f"""
    <h1 style="font-size:22px;font-weight:700;color:{COLORS['text_primary']};
               padding-bottom:12px;border-bottom:2px solid {COLORS['border']};margin-bottom:20px">
        🏪 Análisis de Cartera de Clientes
    </h1>
    """,
    unsafe_allow_html=True,
)

if df.empty:
    render_sin_datos()

kc   = kpi_cobertura_clientes(df, cli_df, df_ant)
kcli = kpi_clientes(df, cli_df, df_ant, fecha_hasta)

# ── KPI Row ───────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_kpi_card("Clientes activos", fmt_numero(kc["clientes_activos_periodo"]),
                    cumplimiento=kc["cobertura_pct"], icon="👥")
with c2:
    render_kpi_card("Cobertura", fmt_pct(kc["cobertura_pct"]),
                    cumplimiento=kc["cobertura_pct"], icon="📊")
with c3:
    render_kpi_card("Clientes nuevos", fmt_numero(kc["clientes_nuevos"]), icon="✨")
with c4:
    render_kpi_card("Clientes perdidos", fmt_numero(kc["clientes_perdidos"]),
                    cumplimiento=1 if kc["clientes_perdidos"] == 0 else 0.5, icon="⚠️")

st.markdown("<br>", unsafe_allow_html=True)

# ── Filtros adicionales ───────────────────────────────────────
with st.expander("🔍 Filtros adicionales de clientes", expanded=False):
    col_cat, col_can, col_est = st.columns(3)
    with col_cat:
        cat_filter = st.multiselect("Categoría Pareto", ["A", "B", "C"], default=[], key="_cat_filter")
    with col_can:
        canal_filter = st.multiselect("Canal", cli_df["canal"].unique().tolist(), default=[], key="_canal_filter")
    with col_est:
        estado_filter = st.selectbox("Estado", ["Todos", "Activos", "En riesgo", "Sin compra reciente"], key="_est_filter")

# Aplicar filtros adicionales
df_cli_filtrado = kcli.copy()
if cat_filter:
    df_cli_filtrado = df_cli_filtrado[df_cli_filtrado["categoria_pareto"].isin(cat_filter)]
if canal_filter:
    df_cli_filtrado = df_cli_filtrado[df_cli_filtrado["canal"].isin(canal_filter)]
if estado_filter == "En riesgo":
    df_cli_filtrado = df_cli_filtrado[df_cli_filtrado["flag_en_riesgo"] == True]
elif estado_filter == "Sin compra reciente":
    df_cli_filtrado = df_cli_filtrado[df_cli_filtrado["dias_desde_ultima_compra"] > 30]

# ── Pareto + Scatter ──────────────────────────────────────────
col_p, col_s = st.columns(2)

with col_p:
    fig_pareto = chart_pareto(
        df_cli_filtrado,
        titulo     = "Pareto de Clientes",
        col_nombre = "razon_social",
        col_valor  = "importe_total",
        top_n      = 30,
    )
    st.plotly_chart(fig_pareto, use_container_width=True, config={"displayModeBar": False})

with col_s:
    fig_scatter = chart_scatter_clientes(df_cli_filtrado)
    st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})

# ── Concentración Pareto ──────────────────────────────────────
if not kcli.empty:
    conc = get_concentracion_pareto(kcli, "importe_total")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric(
            "Clientes categoría A",
            f"{conc['n_entidades_A']} clientes",
            delta=f"{conc['pct_entidades_A']*100:.1f}% del total",
        )
    with col_b:
        st.metric(
            "% ventas categoría A",
            f"{conc['pct_ventas_A']*100:.1f}%",
            delta="objetivo ~80%",
        )
    with col_c:
        st.metric(
            "Índice Gini",
            f"{conc['indice_gini']:.3f}",
            help="0 = distribución perfecta, 1 = concentración total",
        )

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabla completa ────────────────────────────────────────────
st.markdown(
    f"<div class='section-title'>📋 Tabla Completa de Clientes</div>",
    unsafe_allow_html=True,
)
render_ranking_clientes(df_cli_filtrado, top_n=50)

st.markdown("<br>", unsafe_allow_html=True)

# ── Clientes en riesgo y oportunidades ───────────────────────
col_riesgo, col_opor = st.columns(2)

with col_riesgo:
    st.markdown(
        f"<div style='font-size:14px;font-weight:600;color:{COLORS['danger']};margin-bottom:12px'>"
        f"⚠️ Clientes en Riesgo</div>",
        unsafe_allow_html=True,
    )
    en_riesgo = kcli[kcli["flag_en_riesgo"] == True].copy()
    if en_riesgo.empty:
        st.success("✅ Sin clientes en riesgo detectados.")
    else:
        render_ranking_clientes(en_riesgo, top_n=10)

with col_opor:
    st.markdown(
        f"<div style='font-size:14px;font-weight:600;color:{COLORS['success']};margin-bottom:12px'>"
        f"🚀 Oportunidades de Crecimiento</div>",
        unsafe_allow_html=True,
    )
    if "vs_periodo_anterior" in kcli.columns:
        opor = kcli[
            (kcli["categoria_pareto"] == "B") &
            (kcli["vs_periodo_anterior"].fillna(0) > 0.20)
        ].sort_values("vs_periodo_anterior", ascending=False)
        if opor.empty:
            st.info("Sin oportunidades detectadas en este período.")
        else:
            render_ranking_clientes(opor, top_n=10)
    else:
        st.info("Seleccioná un período con datos anteriores para ver oportunidades.")

# ── Detalle de cliente individual ─────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<div class='section-title'>🔍 Detalle de Cliente</div>",
    unsafe_allow_html=True,
)

if not kcli.empty:
    clientes_opciones = kcli["razon_social"].tolist() if "razon_social" in kcli.columns else kcli["id_cliente"].tolist()
    cliente_sel = st.selectbox("Seleccionar cliente para ver detalle:", clientes_opciones, key="_cli_detalle")

    if cliente_sel:
        cli_row = kcli[kcli.get("razon_social", kcli["id_cliente"]) == cliente_sel]
        if "razon_social" in kcli.columns:
            cli_row = kcli[kcli["razon_social"] == cliente_sel]
        else:
            cli_row = kcli[kcli["id_cliente"] == cliente_sel]

        if not cli_row.empty:
            cli_id_sel = cli_row.iloc[0]["id_cliente"]
            df_cli_det = df[df["id_cliente"] == cli_id_sel].copy()

            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            with col_d1:
                st.metric("Importe total", fmt_moneda(cli_row.iloc[0].get("importe_total", 0)))
            with col_d2:
                st.metric("Frecuencia", f"{int(cli_row.iloc[0].get('frecuencia_compra', 0))} compras")
            with col_d3:
                st.metric("Categoría Pareto", cli_row.iloc[0].get("categoria_pareto", "—"))
            with col_d4:
                dias = cli_row.iloc[0].get("dias_desde_ultima_compra", 0)
                st.metric("Días sin compra", f"{int(dias)} días")

            # Evolución del cliente: últimos 6 meses hasta el fin del período
            if not df_cli_det.empty:
                from dateutil.relativedelta import relativedelta
                evo_desde = fecha_hasta.replace(day=1) - relativedelta(months=5)
                df_cli_evo = get_filtered_data(evo_desde, fecha_hasta, None, None, None)
                df_cli_evo = df_cli_evo[df_cli_evo["id_cliente"] == cli_id_sel]
                evo_cli = kpi_evolucion_mensual(df_cli_evo, n_meses=6)
                if not evo_cli.empty:
                    fig_cli = chart_evolucion_ventas(evo_cli, mostrar_objetivo=False,
                                                      title=f"Evolución de {cliente_sel}")
                    st.plotly_chart(fig_cli, use_container_width=True, config={"displayModeBar": False})
