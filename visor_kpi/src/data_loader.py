"""
src/data_loader.py
==================
Lectura, parsing y filtrado del archivo Excel mock.
Cachea con @st.cache_data para performance.
"""

import os
import sys
import pandas as pd
import streamlit as st
from datetime import date

# Asegurar que se puede importar config desde cualquier directorio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_PATH


# ═══════════════════════════════════════════════════════════════
# CARGA PRINCIPAL
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def load_data() -> dict[str, pd.DataFrame]:
    """
    Lee el Excel y retorna dict con DataFrames parseados.
    Keys: ventas, vendedores, clientes, productos, objetivos
    """
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"No se encontró el archivo de datos: {DATA_PATH}\n"
            "Ejecutá primero: python data/mock/generate_mock_data.py"
        )

    xl = pd.ExcelFile(DATA_PATH)

    # ── Ventas ─────────────────────────────────────────────────
    ventas = xl.parse("Ventas")
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    ventas["año"]   = ventas["fecha"].dt.year
    ventas["mes"]   = ventas["fecha"].dt.month
    ventas["periodo"] = ventas["fecha"].dt.to_period("M")
    for col in ["importe_neto", "importe_bruto", "cantidad", "precio_unitario", "descuento_pct"]:
        if col in ventas.columns:
            ventas[col] = pd.to_numeric(ventas[col], errors="coerce").fillna(0)

    # ── Vendedores ─────────────────────────────────────────────
    vendedores = xl.parse("Vendedores")
    for col in ["objetivo_mensual_base", "antiguedad_años"]:
        if col in vendedores.columns:
            vendedores[col] = pd.to_numeric(vendedores[col], errors="coerce")
    vendedores["activo"] = vendedores["activo"].astype(bool)

    # ── Clientes ───────────────────────────────────────────────
    clientes = xl.parse("Clientes")
    clientes["fecha_alta"] = pd.to_datetime(clientes["fecha_alta"])
    clientes["activo"]     = clientes["activo"].astype(bool)
    for col in ["objetivo_mensual_cliente"]:
        if col in clientes.columns:
            clientes[col] = pd.to_numeric(clientes[col], errors="coerce")

    # ── Productos ──────────────────────────────────────────────
    productos = xl.parse("Productos")
    for col in ["precio_unitario", "costo_unitario"]:
        if col in productos.columns:
            productos[col] = pd.to_numeric(productos[col], errors="coerce")
    productos["activo"] = productos["activo"].astype(bool)

    # ── Objetivos ──────────────────────────────────────────────
    objetivos = xl.parse("Objetivos")
    objetivos["objetivo"] = pd.to_numeric(objetivos["objetivo"], errors="coerce").fillna(0)
    if "periodo" in objetivos.columns:
        objetivos["periodo"] = pd.to_datetime(objetivos["periodo"])
    else:
        objetivos["periodo"] = pd.to_datetime(
            objetivos[["año", "mes"]].assign(day=1)
        )

    return {
        "ventas":     ventas,
        "vendedores": vendedores,
        "clientes":   clientes,
        "productos":  productos,
        "objetivos":  objetivos,
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_master_df() -> pd.DataFrame:
    """
    DataFrame maestro con todos los joins aplicados.
    Incluye nombre de vendedor, razón social de cliente, 
    categoría de producto, etc.
    """
    data = load_data()
    ventas     = data["ventas"]
    vendedores = data["vendedores"][["id_vendedor", "nombre_completo", "zona", "perfil"]].copy()
    clientes   = data["clientes"][["id_cliente", "razon_social", "canal", "zona",
                                    "id_vendedor_asignado", "activo"]].copy()
    productos  = data["productos"][["id_producto", "descripcion", "categoria",
                                     "precio_unitario", "costo_unitario"]].copy()

    vendedores = vendedores.rename(columns={
        "nombre_completo": "nombre_vendedor",
        "zona": "zona_vendedor",
    })
    clientes = clientes.rename(columns={
        "zona": "zona_cliente",
        "activo": "cliente_activo",
    })
    productos = productos.rename(columns={
        "precio_unitario": "precio_catalogo",
        "costo_unitario":  "costo_catalogo",
    })

    df = ventas.merge(vendedores, on="id_vendedor", how="left")
    df = df.merge(clientes,   on="id_cliente",  how="left")
    df = df.merge(productos,  on="id_producto", how="left")

    # Margen por transacción
    df["margen_neto"] = df["importe_neto"] - (df["costo_catalogo"] / df["precio_catalogo"] * df["importe_neto"])
    df["margen_pct"]  = (df["margen_neto"] / df["importe_neto"]).clip(0, 1)

    return df


# ═══════════════════════════════════════════════════════════════
# FILTRADO
# ═══════════════════════════════════════════════════════════════

def get_filtered_data(
    fecha_desde: date,
    fecha_hasta: date,
    vendedores: list[str] | None = None,
    zonas: list[str] | None      = None,
    canales: list[str] | None    = None,
) -> pd.DataFrame:
    """
    Retorna el DataFrame maestro filtrado por los parámetros dados.
    Todos los filtros son opcionales (None = sin filtro).
    """
    df = get_master_df()

    # Filtro de fechas
    df = df[
        (df["fecha"].dt.date >= fecha_desde) &
        (df["fecha"].dt.date <= fecha_hasta)
    ]

    # Filtro de vendedores
    if vendedores:
        df = df[df["id_vendedor"].isin(vendedores)]

    # Filtro de zonas
    if zonas:
        df = df[df["zona_vendedor"].isin(zonas)]

    # Filtro de canales
    if canales:
        df = df[df["canal"].isin(canales)]

    return df.copy()


def get_filtered_data_periodo_anterior(
    fecha_desde: date,
    fecha_hasta: date,
    vendedores: list[str] | None = None,
    zonas: list[str] | None      = None,
    canales: list[str] | None    = None,
) -> pd.DataFrame:
    """
    Retorna datos del período anterior equivalente en duración.
    """
    from config import get_periodo_anterior
    nueva_desde, nueva_hasta = get_periodo_anterior(fecha_desde, fecha_hasta)
    return get_filtered_data(nueva_desde, nueva_hasta, vendedores, zonas, canales)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def get_rango_datos() -> tuple[date, date]:
    """Rango real de fechas con ventas (min, max). Los filtros de la app se anclan
    a este rango: el dataset de demo es histórico y 'hoy' puede caer fuera de él."""
    data = load_data()
    fechas = data["ventas"]["fecha"]
    return fechas.min().date(), fechas.max().date()


def get_lista_vendedores() -> list[dict]:
    """Retorna lista de vendedores activos para filtros."""
    data = load_data()
    df = data["vendedores"][data["vendedores"]["activo"]]
    return df[["id_vendedor", "nombre_completo", "zona"]].to_dict("records")


def get_lista_zonas() -> list[str]:
    data = load_data()
    return sorted(data["vendedores"]["zona"].unique().tolist())


def get_lista_canales() -> list[str]:
    data = load_data()
    return sorted(data["clientes"]["canal"].unique().tolist())


def check_data_available() -> bool:
    """Verifica si el archivo de datos existe."""
    return os.path.exists(DATA_PATH)
