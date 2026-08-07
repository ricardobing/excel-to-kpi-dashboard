"""
src/kpi_engine.py
=================
Motor central de cálculo de KPIs.
Todas las funciones reciben un DataFrame ya filtrado
y retornan dicts o DataFrames listos para visualización.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta

from src.pareto import calcular_pareto


# ═══════════════════════════════════════════════════════════════
# KPIs GERENCIALES
# ═══════════════════════════════════════════════════════════════

def kpi_ventas_periodo(
    df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
    objetivos_df: pd.DataFrame | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> dict:
    """
    KPIs agregados de ventas para el período.

    Returns dict con:
        importe_total, importe_vs_anterior, objetivo_total,
        cumplimiento_pct, transacciones_count, ticket_promedio
    """
    importe_total = float(df["importe_neto"].sum()) if not df.empty else 0.0
    n_transacciones = len(df)
    clientes_unicos = df["id_cliente"].nunique() if not df.empty else 0
    ticket_prom = (importe_total / clientes_unicos) if clientes_unicos > 0 else 0.0

    # Objetivo del período
    objetivo_total = 0.0
    if objetivos_df is not None and not objetivos_df.empty and fecha_desde and fecha_hasta:
        mask = (
            (objetivos_df["periodo"] >= pd.Timestamp(fecha_desde)) &
            (objetivos_df["periodo"] <= pd.Timestamp(fecha_hasta))
        )
        objetivo_total = float(objetivos_df[mask]["objetivo"].sum())

    cumplimiento = importe_total / objetivo_total if objetivo_total > 0 else None

    # Delta vs anterior
    importe_vs_ant = None
    if df_anterior is not None and not df_anterior.empty:
        imp_ant = float(df_anterior["importe_neto"].sum())
        if imp_ant > 0:
            importe_vs_ant = (importe_total - imp_ant) / imp_ant

    return {
        "importe_total":       importe_total,
        "importe_vs_anterior": importe_vs_ant,
        "objetivo_total":      objetivo_total,
        "cumplimiento_pct":    cumplimiento,
        "transacciones_count": n_transacciones,
        "ticket_promedio":     ticket_prom,
        "clientes_unicos":     clientes_unicos,
    }


def kpi_margen(
    df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
) -> dict:
    """
    KPIs de margen bruto.
    """
    if df.empty or "margen_neto" not in df.columns:
        return {"margen_bruto_total": 0, "margen_pct_promedio": 0, "margen_vs_anterior": None}

    margen_total = float(df["margen_neto"].sum())
    importe_total = float(df["importe_neto"].sum())
    margen_pct = margen_total / importe_total if importe_total > 0 else 0.0

    margen_vs_ant = None
    if df_anterior is not None and not df_anterior.empty and "margen_neto" in df_anterior.columns:
        margen_ant = float(df_anterior["margen_neto"].sum())
        if margen_ant > 0:
            margen_vs_ant = (margen_total - margen_ant) / margen_ant

    return {
        "margen_bruto_total":   margen_total,
        "margen_pct_promedio":  margen_pct,
        "margen_vs_anterior":   margen_vs_ant,
    }


def kpi_cobertura_clientes(
    df: pd.DataFrame,
    clientes_df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
) -> dict:
    """
    KPIs de cobertura y estado de la cartera de clientes.
    """
    clientes_activos_total = clientes_df[clientes_df["activo"] == True]["id_cliente"].tolist()
    n_total = len(clientes_activos_total)

    # Clientes que compraron en este período
    compraron = set(df["id_cliente"].unique()) if not df.empty else set()
    n_activos_periodo = len(compraron & set(clientes_activos_total))
    cobertura = n_activos_periodo / n_total if n_total > 0 else 0.0

    # Clientes que compraron en anterior pero no en este
    compraron_anterior = set()
    if df_anterior is not None and not df_anterior.empty:
        compraron_anterior = set(df_anterior["id_cliente"].unique())

    n_perdidos    = len(compraron_anterior - compraron)
    n_recuperados = len(compraron & compraron_anterior - (compraron_anterior & set(clientes_activos_total)))

    # Clientes nuevos = primera compra en el período
    if not df.empty and "id_cliente" in clientes_df.columns:
        todos_anteriores = set()
        if df_anterior is not None and not df_anterior.empty:
            todos_anteriores = set(df_anterior["id_cliente"].unique())
        n_nuevos = len(compraron - todos_anteriores)
    else:
        n_nuevos = 0

    return {
        "clientes_activos_periodo": n_activos_periodo,
        "clientes_total":           n_total,
        "cobertura_pct":            cobertura,
        "clientes_perdidos":        n_perdidos,
        "clientes_nuevos":          n_nuevos,
        "clientes_recuperados":     n_recuperados,
    }


# ═══════════════════════════════════════════════════════════════
# KPIs POR VENDEDOR
# ═══════════════════════════════════════════════════════════════

def kpi_por_vendedor(
    df: pd.DataFrame,
    objetivos_df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
) -> pd.DataFrame:
    """
    DataFrame con una fila por vendedor y todos los KPIs.
    """
    if df.empty:
        return pd.DataFrame()

    # Ventas actuales por vendedor
    grp = df.groupby("id_vendedor").agg(
        importe_total    = ("importe_neto", "sum"),
        transacciones    = ("id_venta",     "count"),
        clientes_únicos  = ("id_cliente",   "nunique"),
    ).reset_index()

    # Nombre del vendedor
    if "nombre_vendedor" in df.columns:
        nombres = df.drop_duplicates("id_vendedor")[["id_vendedor", "nombre_vendedor", "zona_vendedor", "perfil"]]
        grp = grp.merge(nombres, on="id_vendedor", how="left")

    # Objetivo del período
    obj_periodo = _get_objetivo_periodo(objetivos_df, fecha_desde, fecha_hasta)
    grp = grp.merge(obj_periodo, on="id_vendedor", how="left")
    grp["objetivo"] = grp["objetivo"].fillna(0)
    grp["cumplimiento_pct"] = grp.apply(
        lambda r: r["importe_total"] / r["objetivo"] if r["objetivo"] > 0 else None, axis=1
    )

    # Ticket promedio
    grp["ticket_promedio"] = grp.apply(
        lambda r: r["importe_total"] / r["clientes_únicos"] if r["clientes_únicos"] > 0 else 0, axis=1
    )

    # Delta vs mes anterior
    if df_anterior is not None and not df_anterior.empty:
        ant = df_anterior.groupby("id_vendedor")["importe_neto"].sum().reset_index()
        ant = ant.rename(columns={"importe_neto": "importe_anterior"})
        grp = grp.merge(ant, on="id_vendedor", how="left")
        grp["importe_anterior"] = grp["importe_anterior"].fillna(0)
        grp["importe_vs_mes_anterior"] = grp.apply(
            lambda r: (r["importe_total"] - r["importe_anterior"]) / r["importe_anterior"]
            if r["importe_anterior"] > 0 else None,
            axis=1
        )
    else:
        grp["importe_vs_mes_anterior"] = None

    # Rankings
    grp = grp.sort_values("importe_total", ascending=False).reset_index(drop=True)
    grp["ranking_actual"] = grp.index + 1

    if df_anterior is not None and not df_anterior.empty and "importe_anterior" in grp.columns:
        grp_ant = grp.sort_values("importe_anterior", ascending=False).reset_index(drop=True)
        rank_ant = {row["id_vendedor"]: i + 1 for i, row in grp_ant.iterrows()}
        grp["ranking_anterior"] = grp["id_vendedor"].map(rank_ant)
        grp["delta_ranking"]    = grp["ranking_anterior"] - grp["ranking_actual"]
    else:
        grp["ranking_anterior"] = grp["ranking_actual"]
        grp["delta_ranking"]    = 0

    # Semáforo
    grp["color_semaforo"] = grp["cumplimiento_pct"].apply(_color_semaforo)
    grp["label_semaforo"] = grp["cumplimiento_pct"].apply(_label_semaforo)

    return grp.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# KPIs DE PRODUCTOS
# ═══════════════════════════════════════════════════════════════

def kpi_productos(
    df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    DataFrame con KPIs por producto incluyendo Pareto.
    """
    if df.empty:
        return pd.DataFrame()

    grp = df.groupby("id_producto").agg(
        importe_total    = ("importe_neto", "sum"),
        unidades_vendidas = ("cantidad",    "sum"),
        n_transacciones  = ("id_venta",     "count"),
    ).reset_index()

    # Info del producto
    if "descripcion" in df.columns:
        info = df.drop_duplicates("id_producto")[["id_producto", "descripcion", "categoria"]]
        grp  = grp.merge(info, on="id_producto", how="left")

    # Pareto
    grp = calcular_pareto(grp, "importe_total", "id_producto")

    # Delta vs anterior
    if df_anterior is not None and not df_anterior.empty:
        ant = df_anterior.groupby("id_producto")["importe_neto"].sum().reset_index()
        ant = ant.rename(columns={"importe_neto": "importe_anterior"})
        grp = grp.merge(ant, on="id_producto", how="left")
        grp["importe_anterior"] = grp["importe_anterior"].fillna(0)
        grp["vs_periodo_anterior"] = grp.apply(
            lambda r: (r["importe_total"] - r["importe_anterior"]) / r["importe_anterior"]
            if r["importe_anterior"] > 0 else None,
            axis=1
        )
    else:
        grp["vs_periodo_anterior"] = None

    return grp.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# KPIs DE CLIENTES
# ═══════════════════════════════════════════════════════════════

def kpi_clientes(
    df: pd.DataFrame,
    clientes_df: pd.DataFrame,
    df_anterior: pd.DataFrame | None = None,
    fecha_hasta: date | None = None,
) -> pd.DataFrame:
    """
    DataFrame con KPIs por cliente incluyendo Pareto y flags de riesgo.
    """
    if df.empty:
        return pd.DataFrame()

    grp = df.groupby("id_cliente").agg(
        importe_total    = ("importe_neto",  "sum"),
        frecuencia_compra = ("id_venta",     "count"),
        ultima_compra    = ("fecha",         "max"),
        primera_compra   = ("fecha",         "min"),
    ).reset_index()

    grp["ticket_promedio"] = grp["importe_total"] / grp["frecuencia_compra"]

    # Días desde última compra
    ref_date = pd.Timestamp(fecha_hasta) if fecha_hasta else pd.Timestamp.now()
    grp["dias_desde_ultima_compra"] = (ref_date - grp["ultima_compra"]).dt.days

    # Info del cliente
    info_cols = ["id_cliente", "razon_social", "canal", "zona", "id_vendedor_asignado"]
    if "nombre_vendedor" in df.columns:
        vend_info = df.drop_duplicates("id_cliente")[["id_cliente", "nombre_vendedor"]]
        grp = grp.merge(vend_info, on="id_cliente", how="left")
    
    cli_info = clientes_df[[c for c in info_cols if c in clientes_df.columns]]
    grp = grp.merge(cli_info, on="id_cliente", how="left")

    # Pareto
    grp = calcular_pareto(grp, "importe_total", "id_cliente")

    # Delta vs anterior
    if df_anterior is not None and not df_anterior.empty:
        ant = df_anterior.groupby("id_cliente")["importe_neto"].sum().reset_index()
        ant = ant.rename(columns={"importe_neto": "importe_anterior"})
        grp = grp.merge(ant, on="id_cliente", how="left")
        grp["importe_anterior"] = grp["importe_anterior"].fillna(0)
        grp["vs_periodo_anterior"] = grp.apply(
            lambda r: (r["importe_total"] - r["importe_anterior"]) / r["importe_anterior"]
            if r["importe_anterior"] > 0 else None,
            axis=1
        )
    else:
        grp["vs_periodo_anterior"] = None

    # Flag en riesgo: categoría A o B con >30 días sin compra
    grp["flag_en_riesgo"] = (
        (grp["categoria_pareto"].isin(["A", "B"])) &
        (grp["dias_desde_ultima_compra"] > 30)
    )

    return grp.reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# EVOLUCIÓN MENSUAL
# ═══════════════════════════════════════════════════════════════

def kpi_evolucion_mensual(
    df: pd.DataFrame,
    objetivos_df: pd.DataFrame | None = None,
    id_vendedor: str | None = None,
    n_meses: int = 13,
) -> pd.DataFrame:
    """
    Ventas mensuales con objetivo para el gráfico de evolución.
    """
    if df.empty:
        return pd.DataFrame()

    if id_vendedor:
        df = df[df["id_vendedor"] == id_vendedor]

    mensual = df.groupby(df["fecha"].dt.to_period("M")).agg(
        importe    = ("importe_neto", "sum"),
        n_ventas   = ("id_venta",     "count"),
        n_clientes = ("id_cliente",   "nunique"),
    ).reset_index()
    mensual["periodo_str"] = mensual["fecha"].astype(str)
    mensual = mensual.rename(columns={"fecha": "periodo"})

    # Recortar a los últimos n_meses
    mensual = mensual.sort_values("periodo").tail(n_meses).reset_index(drop=True)

    # Agregar objetivo
    if objetivos_df is not None and not objetivos_df.empty:
        obj = objetivos_df.copy()
        if id_vendedor:
            obj = obj[obj["id_vendedor"] == id_vendedor]
        obj_mensual = obj.groupby(
            pd.to_datetime(obj["periodo"]).dt.to_period("M")
        )["objetivo"].sum().reset_index()
        obj_mensual = obj_mensual.rename(columns={"periodo": "periodo"})
        mensual = mensual.merge(obj_mensual, on="periodo", how="left")
        mensual["objetivo"] = mensual["objetivo"].fillna(0)

    return mensual


# ═══════════════════════════════════════════════════════════════
# INSIGHT AUTOMÁTICO
# ═══════════════════════════════════════════════════════════════

def generar_insight_ejecutivo(
    kpi_ventas: dict,
    kpi_vend: pd.DataFrame,
    alertas_df: pd.DataFrame | None = None,
) -> str:
    """Genera un párrafo de insight dinámico para la vista gerencial."""
    from config import fmt_moneda, fmt_pct

    importe = fmt_moneda(kpi_ventas.get("importe_total", 0))
    cumpl   = fmt_pct(kpi_ventas.get("cumplimiento_pct", 0))

    n_verde  = len(kpi_vend[kpi_vend["label_semaforo"] == "success"]) if not kpi_vend.empty else 0
    n_naranja = len(kpi_vend[kpi_vend["label_semaforo"] == "warning"]) if not kpi_vend.empty else 0
    n_rojo   = len(kpi_vend[kpi_vend["label_semaforo"] == "danger"])  if not kpi_vend.empty else 0

    # Cliente con mayor caída
    cliente_caida = ""
    if not kpi_vend.empty and "vs_periodo_anterior" in kpi_vend.columns:
        pass  # se calcularía de kpi_clientes

    n_alertas = len(alertas_df) if alertas_df is not None else 0
    n_criticas = len(alertas_df[alertas_df["severidad"] == "alta"]) if alertas_df is not None else 0
    n_medias   = len(alertas_df[alertas_df["severidad"] == "media"]) if alertas_df is not None else 0
    n_info     = len(alertas_df[alertas_df["severidad"].isin(["baja", "info"])]) if alertas_df is not None else 0

    delta_txt = ""
    if kpi_ventas.get("importe_vs_anterior") is not None:
        from config import fmt_delta
        delta_txt = f", {fmt_delta(kpi_ventas['importe_vs_anterior'])} vs período anterior"

    # HTML (no markdown): el insight se renderiza dentro de un <div> con
    # unsafe_allow_html, donde los ** de markdown no se interpretan.
    return (
        f"El equipo lleva <strong>{importe}</strong> en ventas{delta_txt}, "
        f"alcanzando el <strong>{cumpl}</strong> del objetivo. "
        f"{n_verde} vendedores están en 🟢 verde, {n_naranja} en 🟡 naranja y {n_rojo} en 🔴 rojo. "
        f"Se detectaron <strong>{n_alertas} alertas activas</strong>: "
        f"{n_criticas} críticas, {n_medias} medias, {n_info} informativas."
    )


# ═══════════════════════════════════════════════════════════════
# HELPERS PRIVADOS
# ═══════════════════════════════════════════════════════════════

def _get_objetivo_periodo(
    objetivos_df: pd.DataFrame,
    fecha_desde: date | None,
    fecha_hasta: date | None,
) -> pd.DataFrame:
    """Suma de objetivos por vendedor en el período."""
    if objetivos_df is None or objetivos_df.empty:
        return pd.DataFrame(columns=["id_vendedor", "objetivo"])
    obj = objetivos_df.copy()
    if fecha_desde and fecha_hasta:
        obj = obj[
            (obj["periodo"] >= pd.Timestamp(fecha_desde)) &
            (obj["periodo"] <= pd.Timestamp(fecha_hasta))
        ]
    return obj.groupby("id_vendedor")["objetivo"].sum().reset_index()


def _color_semaforo(cumpl: float | None) -> str:
    if cumpl is None:
        return "#E84855"
    if cumpl >= 1.00:
        return "#00C49F"
    elif cumpl >= 0.80:
        return "#FFB347"
    return "#E84855"


def _label_semaforo(cumpl: float | None) -> str:
    if cumpl is None:
        return "danger"
    if cumpl >= 1.00:
        return "success"
    elif cumpl >= 0.80:
        return "warning"
    return "danger"
