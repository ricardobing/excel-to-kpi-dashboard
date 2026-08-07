"""
components/filters.py
=====================
Sidebar global de filtros. Usa st.session_state para persistencia.
"""

import streamlit as st
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COLORS, ZONAS, CANALES, get_periodos


def get_hoy_datos() -> tuple[date, date, date]:
    """(fecha_min_datos, fecha_max_datos, hoy_ref).

    hoy_ref es el 'hoy' del negocio: la última fecha con ventas. Todos los
    períodos se anclan ahí para que el dashboard nunca abra en un rango vacío
    (el dataset de demo es histórico y date.today() puede caer fuera de él).
    """
    try:
        from src.data_loader import get_rango_datos
        fecha_min, fecha_max = get_rango_datos()
    except Exception:
        hoy = date.today()
        return hoy.replace(month=1, day=1), hoy, hoy
    return fecha_min, fecha_max, min(date.today(), fecha_max)


def init_session_state() -> None:
    """Inicializa el estado global de filtros si no existe."""
    _, _, hoy = get_hoy_datos()
    primer_dia_mes = hoy.replace(day=1)

    defaults = {
        "periodo_sel":       "Este mes",
        "fecha_desde":       primer_dia_mes,
        "fecha_hasta":       hoy,
        "vendedores_sel":    [],
        "zonas_sel":         [],
        "canales_sel":       [],
        "alertas_revisadas": set(),
        "data_loaded":       False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_sidebar_filters(mostrar_vendedor: bool = True) -> dict:
    """
    Renderiza el sidebar de filtros y retorna dict con valores seleccionados.
    """
    init_session_state()
    fecha_min_datos, fecha_max_datos, hoy_datos = get_hoy_datos()

    with st.sidebar:
        # ── Logo / Título ──────────────────────────────────────
        st.markdown(
            f"""
            <div style="text-align:center; padding: 20px 0 10px 0;">
                <div style="font-size:28px; font-weight:700; color:{COLORS['text_primary']};">
                    📊 Visor KPI
                </div>
                <div style="font-size:11px; color:{COLORS['text_secondary']}; 
                            letter-spacing:2px; text-transform:uppercase; margin-top:2px;">
                    Performance Comercial
                </div>
            </div>
            <hr style="border-color:{COLORS['border']}; margin: 0 0 16px 0;">
            """,
            unsafe_allow_html=True,
        )

        # ── Selector de período ────────────────────────────────
        st.markdown(
            f"<div style='font-size:11px;color:{COLORS['text_secondary']};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:6px'>📅 Período</div>",
            unsafe_allow_html=True,
        )

        periodos = get_periodos(hoy_datos)
        opciones = list(periodos.keys())
        idx_actual = opciones.index(st.session_state["periodo_sel"]) \
                     if st.session_state["periodo_sel"] in opciones else 0

        periodo_sel = st.selectbox(
            label     = "período",
            options   = opciones,
            index     = idx_actual,
            label_visibility = "collapsed",
            key       = "_periodo_widget",
        )
        st.session_state["periodo_sel"] = periodo_sel

        if periodo_sel == "Personalizado":
            # valores previos acotados al rango con datos
            desde_ini = min(max(st.session_state["fecha_desde"], fecha_min_datos), fecha_max_datos)
            hasta_ini = min(max(st.session_state["fecha_hasta"], fecha_min_datos), fecha_max_datos)
            col_d, col_h = st.columns(2)
            with col_d:
                fecha_desde = st.date_input(
                    "Desde",
                    value     = desde_ini,
                    min_value = fecha_min_datos,
                    max_value = fecha_max_datos,
                    key       = "_fecha_desde",
                )
            with col_h:
                fecha_hasta = st.date_input(
                    "Hasta",
                    value     = hasta_ini,
                    min_value = fecha_min_datos,
                    max_value = fecha_max_datos,
                    key       = "_fecha_hasta",
                )
            if fecha_desde > fecha_hasta:
                fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        else:
            rango = periodos[periodo_sel]
            fecha_desde, fecha_hasta = rango
            # nunca salir del rango con datos
            fecha_desde = max(fecha_desde, fecha_min_datos)
            fecha_hasta = min(fecha_hasta, fecha_max_datos)

        st.session_state["fecha_desde"] = fecha_desde
        st.session_state["fecha_hasta"] = fecha_hasta

        st.markdown(
            f"<div style='font-size:11px;color:{COLORS['text_secondary']};margin-top:2px'>"
            f"{fecha_desde.strftime('%d/%m/%Y')} — {fecha_hasta.strftime('%d/%m/%Y')}"
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Filtro de zona ─────────────────────────────────────
        st.markdown(
            f"<div style='font-size:11px;color:{COLORS['text_secondary']};text-transform:uppercase;"
            f"letter-spacing:1px;margin-bottom:6px'>🗺️ Zona</div>",
            unsafe_allow_html=True,
        )
        zonas_sel = st.multiselect(
            label    = "zona",
            options  = ZONAS,
            default  = st.session_state["zonas_sel"],
            placeholder = "Todas las zonas",
            label_visibility = "collapsed",
            key      = "_zonas_widget",
        )
        st.session_state["zonas_sel"] = zonas_sel

        # ── Filtro de vendedor ─────────────────────────────────
        if mostrar_vendedor:
            st.markdown(
                f"<div style='font-size:11px;color:{COLORS['text_secondary']};text-transform:uppercase;"
                f"letter-spacing:1px;margin-top:12px;margin-bottom:6px'>👤 Vendedor</div>",
                unsafe_allow_html=True,
            )

            # Cargar lista de vendedores dinámicamente
            try:
                from src.data_loader import get_lista_vendedores
                vendedores_lista = get_lista_vendedores()
                opciones_vend = {
                    f"{v['nombre_completo']} ({v['zona']})": v["id_vendedor"]
                    for v in vendedores_lista
                }
                if zonas_sel:
                    opciones_vend = {
                        k: v for k, v in opciones_vend.items()
                        if any(z in k for z in zonas_sel)
                    }
            except Exception:
                opciones_vend = {}

            vend_labels_sel = st.multiselect(
                label    = "vendedor",
                options  = list(opciones_vend.keys()),
                default  = [],
                placeholder = "Todos los vendedores",
                label_visibility = "collapsed",
                key      = "_vend_widget",
            )
            vendedores_sel = [opciones_vend[l] for l in vend_labels_sel if l in opciones_vend]
            st.session_state["vendedores_sel"] = vendedores_sel
        else:
            vendedores_sel = st.session_state.get("vendedores_sel", [])

        # ── Filtro de canal ────────────────────────────────────
        st.markdown(
            f"<div style='font-size:11px;color:{COLORS['text_secondary']};text-transform:uppercase;"
            f"letter-spacing:1px;margin-top:12px;margin-bottom:6px'>🏪 Canal</div>",
            unsafe_allow_html=True,
        )
        canales_sel = st.multiselect(
            label    = "canal",
            options  = CANALES,
            default  = st.session_state["canales_sel"],
            placeholder = "Todos los canales",
            label_visibility = "collapsed",
            key      = "_canales_widget",
        )
        st.session_state["canales_sel"] = canales_sel

        # ── Botón limpiar filtros ──────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Limpiar filtros", use_container_width=True):
            st.session_state["periodo_sel"]    = "Este mes"
            st.session_state["fecha_desde"]    = hoy_datos.replace(day=1)
            st.session_state["fecha_hasta"]    = hoy_datos
            st.session_state["zonas_sel"]      = []
            st.session_state["vendedores_sel"] = []
            st.session_state["canales_sel"]    = []
            st.rerun()

        # ── Indicador de última actualización ─────────────────
        st.markdown(
            f"""
            <hr style="border-color:{COLORS['border']}; margin: 16px 0 8px 0;">
            <div style='font-size:10px;color:{COLORS['text_secondary']};text-align:center'>
                Datos actualizados al<br>
                <strong style='color:{COLORS['text_primary']}'>
                {fecha_max_datos.strftime('%d/%m/%Y')}
                </strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return {
        "fecha_desde":    fecha_desde,
        "fecha_hasta":    fecha_hasta,
        "vendedores_sel": vendedores_sel,
        "zonas_sel":      zonas_sel,
        "canales_sel":    canales_sel,
        "periodo_sel":    periodo_sel,
    }


def render_sin_datos() -> None:
    """Aviso amigable cuando los filtros no devuelven datos, con botón de rescate
    que vuelve al último mes con ventas. Llamar en lugar de st.warning + st.stop."""
    _, fecha_max, hoy_datos = get_hoy_datos()
    st.warning(
        "⚠️ **No hay ventas en el período o filtros seleccionados.** "
        f"El dataset de demo llega hasta el **{fecha_max.strftime('%d/%m/%Y')}**."
    )
    if st.button("📅 Ver el último mes con datos", type="primary"):
        st.session_state["periodo_sel"]    = "Este mes"
        st.session_state["fecha_desde"]    = hoy_datos.replace(day=1)
        st.session_state["fecha_hasta"]    = hoy_datos
        st.session_state["zonas_sel"]      = []
        st.session_state["vendedores_sel"] = []
        st.session_state["canales_sel"]    = []
        st.rerun()
    st.stop()
