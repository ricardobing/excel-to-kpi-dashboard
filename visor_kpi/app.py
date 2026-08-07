"""
app.py — Entry point principal del Visor KPI Comercial
Página: Resumen Ejecutivo (vista gerencial de alto nivel)
"""

import os
import sys
import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta

# ── Path setup ────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Configuración de página (DEBE IR ANTES de cualquier st.) ──
st.set_page_config(
    page_title          = "Visor KPI Comercial",
    page_icon           = "📊",
    layout              = "wide",
    initial_sidebar_state = "expanded",
)

# ── Cargar CSS global ─────────────────────────────────────────
css_path = os.path.join(BASE_DIR, "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Imports del proyecto ──────────────────────────────────────
from components.filters import render_sidebar_filters, init_session_state, render_sin_datos
from src.data_loader    import load_data, get_filtered_data, get_filtered_data_periodo_anterior, check_data_available
from src.kpi_engine     import (
    kpi_ventas_periodo, kpi_margen, kpi_cobertura_clientes,
    kpi_por_vendedor, kpi_clientes, kpi_productos, kpi_evolucion_mensual,
    generar_insight_ejecutivo,
)
from src.alerts_engine  import get_alertas_activas
from components.kpi_card   import render_kpi_card
from components.charts     import (
    chart_evolucion_ventas, chart_barras_vendedores,
    chart_gauge_cumplimiento, chart_donut_canales,
)
from components.rankings   import render_ranking_vendedores, render_ranking_clientes, render_ranking_productos
from config import fmt_moneda, fmt_pct, fmt_numero, COLORS

# ── Init session state ────────────────────────────────────────
init_session_state()

# ── Verificar datos ───────────────────────────────────────────
if not check_data_available():
    st.error(
        "⚠️ **No se encontró el archivo de datos.**\n\n"
        "Ejecutá el siguiente comando para generar los datos mock:\n\n"
        "```bash\npython data/mock/generate_mock_data.py\n```"
    )
    st.stop()

# ── Filtros sidebar ───────────────────────────────────────────
filtros = render_sidebar_filters()
fecha_desde    = filtros["fecha_desde"]
fecha_hasta    = filtros["fecha_hasta"]
vendedores_sel = filtros["vendedores_sel"] or None
zonas_sel      = filtros["zonas_sel"]      or None
canales_sel    = filtros["canales_sel"]    or None

# ── Cargar datos ──────────────────────────────────────────────
with st.spinner("Calculando indicadores..."):
    try:
        data       = load_data()
        df         = get_filtered_data(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
        df_ant     = get_filtered_data_periodo_anterior(fecha_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
        clientes_df  = data["clientes"]
        productos_df = data["productos"]
        objetivos_df = data["objetivos"]
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        st.stop()

# ── Header ────────────────────────────────────────────────────
st.markdown(
    f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                padding-bottom:16px;border-bottom:2px solid {COLORS['border']};margin-bottom:24px">
        <div>
            <h1 style="margin:0;font-size:24px;font-weight:700;color:{COLORS['text_primary']}">
                📊 Resumen Ejecutivo
            </h1>
            <div style="color:{COLORS['text_secondary']};font-size:13px;margin-top:2px">
                Distribuidora Del Sur S.A. · 
                {fecha_desde.strftime('%d/%m/%Y')} al {fecha_hasta.strftime('%d/%m/%Y')}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Manejar DataFrame vacío ───────────────────────────────────
if df.empty:
    render_sin_datos()

# ── Calcular KPIs ─────────────────────────────────────────────
kv    = kpi_ventas_periodo(df, df_ant, objetivos_df, fecha_desde, fecha_hasta)
km    = kpi_margen(df, df_ant)
kc    = kpi_cobertura_clientes(df, clientes_df, df_ant)
kv_df = kpi_por_vendedor(df, objetivos_df, df_ant, fecha_desde, fecha_hasta)
kp_df = kpi_productos(df, df_ant)
kcli  = kpi_clientes(df, clientes_df, df_ant, fecha_hasta)
# La evolución siempre muestra los últimos 12 meses hasta el fin del período
# seleccionado (con un solo mes filtrado, el gráfico quedaba con un punto).
evo_desde = fecha_hasta.replace(day=1) - relativedelta(months=11)
df_evo    = get_filtered_data(evo_desde, fecha_hasta, vendedores_sel, zonas_sel, canales_sel)
evo   = kpi_evolucion_mensual(df_evo, objetivos_df)
alertas = get_alertas_activas(df, df_ant, clientes_df, productos_df, objetivos_df, fecha_hasta)

# ══════════════════════════════════════════════════════════════
# ROW 1 — KPI Cards principales
# ══════════════════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4)

with c1:
    render_kpi_card(
        label        = "Ventas del Período",
        value        = fmt_moneda(kv["importe_total"]),
        delta_pct    = kv.get("importe_vs_anterior"),
        objetivo     = fmt_moneda(kv.get("objetivo_total", 0)),
        cumplimiento = kv.get("cumplimiento_pct"),
        icon         = "💰",
    )

with c2:
    render_kpi_card(
        label        = "Cumplimiento Equipo",
        value        = fmt_pct(kv.get("cumplimiento_pct", 0)),
        delta_pct    = None,
        objetivo     = "100%",
        cumplimiento = kv.get("cumplimiento_pct"),
        icon         = "🎯",
    )

with c3:
    render_kpi_card(
        label        = "Margen Bruto",
        value        = fmt_moneda(km["margen_bruto_total"]),
        delta_pct    = km.get("margen_vs_anterior"),
        objetivo     = None,
        cumplimiento = None,
        icon         = "📈",
    )

with c4:
    render_kpi_card(
        label        = "Cobertura de Clientes",
        value        = fmt_pct(kc["cobertura_pct"]),
        delta_pct    = None,
        objetivo     = None,
        cumplimiento = kc["cobertura_pct"],
        icon         = "👥",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ROW 2 — Gauge + Evolución de ventas
# ══════════════════════════════════════════════════════════════
col_gauge, col_evo = st.columns([1, 2])

with col_gauge:
    st.markdown(
        f"<div style='font-size:13px;font-weight:600;color:{COLORS['text_secondary']};"
        f"text-transform:uppercase;letter-spacing:1px;margin-bottom:8px'>Cumplimiento del Equipo</div>",
        unsafe_allow_html=True,
    )
    fig_gauge = chart_gauge_cumplimiento(
        valor = kv.get("cumplimiento_pct") or 0,
        label = "Cumplimiento General",
    )
    st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

    # Sub-KPIs debajo del gauge
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("🟢 En verde",  f"{len(kv_df[kv_df['label_semaforo']=='success']) if not kv_df.empty else 0}")
    with col_b:
        st.metric("🟡 En naranja", f"{len(kv_df[kv_df['label_semaforo']=='warning']) if not kv_df.empty else 0}")
    with col_c:
        st.metric("🔴 En rojo",   f"{len(kv_df[kv_df['label_semaforo']=='danger'])  if not kv_df.empty else 0}")

with col_evo:
    fig_evo = chart_evolucion_ventas(evo, mostrar_objetivo=True)
    st.plotly_chart(fig_evo, use_container_width=True, config={"displayModeBar": False})

# ══════════════════════════════════════════════════════════════
# INSIGHT AUTOMÁTICO
# ══════════════════════════════════════════════════════════════
insight = generar_insight_ejecutivo(kv, kv_df, alertas)
st.markdown(
    f'<div class="insight-box">{insight}</div>',
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════════════════════
# ROW 3 — Rankings Top 5
# ══════════════════════════════════════════════════════════════
col_rv, col_rc, col_rp = st.columns(3)

with col_rv:
    st.markdown(
        f"<div class='section-title' style='font-size:15px'>🏆 Top Vendedores</div>",
        unsafe_allow_html=True,
    )
    if not kv_df.empty:
        render_ranking_vendedores(kv_df.head(5))
    else:
        st.info("Sin datos de vendedores.")

with col_rc:
    st.markdown(
        f"<div class='section-title' style='font-size:15px'>🏪 Top Clientes</div>",
        unsafe_allow_html=True,
    )
    if not kcli.empty:
        render_ranking_clientes(kcli.head(5))
    else:
        st.info("Sin datos de clientes.")

with col_rp:
    st.markdown(
        f"<div class='section-title' style='font-size:15px'>📦 Top Productos</div>",
        unsafe_allow_html=True,
    )
    if not kp_df.empty:
        render_ranking_productos(kp_df.head(5))
    else:
        st.info("Sin datos de productos.")

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ROW 4 — Alertas y métricas de cartera
# ══════════════════════════════════════════════════════════════
col_alerta, col_metricas = st.columns([3, 2])

with col_alerta:
    st.markdown(
        f"<div class='section-title' style='font-size:15px'>🚨 Alertas Activas</div>",
        unsafe_allow_html=True,
    )

    if alertas.empty:
        st.success("✅ Sin alertas activas en este período.")
    else:
        # Resumen rápido
        n_alta  = len(alertas[alertas["severidad"] == "alta"])
        n_media = len(alertas[alertas["severidad"] == "media"])
        n_info  = len(alertas[alertas["severidad"].isin(["baja", "info"])])

        c_a, c_m, c_i = st.columns(3)
        c_a.metric("🔴 Críticas",    n_alta)
        c_m.metric("🟡 Medias",      n_media)
        c_i.metric("🔵 Informativas", n_info)

        st.markdown("<br>", unsafe_allow_html=True)

        # Mostrar primeras 4 alertas
        for _, alerta in alertas.head(4).iterrows():
            ico = {"alta": "🔴", "media": "🟡", "baja": "🔵", "info": "🟢"}.get(alerta["severidad"], "⚪")
            sev_class = alerta["severidad"]
            sev_color = {"alta": COLORS["danger"], "media": COLORS["warning"],
                         "baja": COLORS["primary_light"], "info": COLORS["success"]}.get(sev_class, COLORS["border"])

            st.markdown(
                f"""
                <div class="alert-card {sev_class}">
                    <div class="alert-title">{ico} {alerta['nombre']}</div>
                    <div class="alert-detail">
                        <strong>{alerta['entidad_nombre']}</strong> — {alerta['descripcion_detalle']}
                    </div>
                    <div class="alert-action">💡 {alerta['accion_sugerida']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if len(alertas) > 4:
            st.markdown(
                f"<div style='color:{COLORS['text_secondary']};font-size:12px;text-align:center'>"
                f"+ {len(alertas) - 4} alertas más → ver Centro de Alertas</div>",
                unsafe_allow_html=True,
            )

with col_metricas:
    st.markdown(
        f"<div class='section-title' style='font-size:15px'>📊 Estado de Cartera</div>",
        unsafe_allow_html=True,
    )

    # Gráfico de distribución por canal
    fig_donut = chart_donut_canales(df)
    st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

    # Métricas de clientes
    col_x, col_y = st.columns(2)
    with col_x:
        st.metric("Clientes activos",    kc["clientes_activos_periodo"],
                  delta=f"+{kc['clientes_nuevos']} nuevos")
    with col_y:
        st.metric("Clientes en riesgo",
                  len(kcli[kcli["flag_en_riesgo"] == True]) if not kcli.empty else 0,
                  delta=f"-{kc['clientes_perdidos']} perdidos",
                  delta_color="inverse")
