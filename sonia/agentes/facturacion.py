"""Agente de Facturación — fuga de ingresos y calidad de emisión.

Base: prototipo de Agentes 1551 (agente_facturacion.py). Portado a datos.py.

Dos capacidades:
  1. FUGA DE INGRESOS — clientes con servicio activo cuya última factura es
     demasiado vieja. Servicio prendido y sin cobrar = plata que se escapa.
  2. CALIDAD — tasa de notas de crédito, el indicador que la ficha pide reducir.

Hallazgo del equipo que este módulo respeta: COD_CUENTA arrastra la misma
inconsistencia de anonimización que el RUC, así que el cruce cliente↔factura
va SIEMPRE por RAZON_SOCIAL.
"""

import pandas as pd

UMBRAL_DIAS = 60
TOPE_MESES_EXPOSICION = 12  # no extrapolar más de un año, para no inflar el caso


def detectar_fuga(planta_fija, planta_movil, facturas, umbral_dias=UMBRAL_DIAS):
    referencia = facturas.fecha_emision.max()
    ultima_x_cliente = facturas.groupby("RAZON_SOCIAL").fecha_emision.max()

    con_fija = set(planta_fija[planta_fija.STATUS_DESC == "Active"].RAZON_SOCIAL)
    con_movil = set(planta_movil[planta_movil.ESTADO_LINEA == "Activo"].RAZON_SOCIAL)

    filas = []
    for cliente in con_fija | con_movil:
        ultima = ultima_x_cliente.get(cliente)
        nunca = pd.isna(ultima)
        dias = None if nunca else (referencia - ultima).days
        if nunca:
            nivel, motivo = "CRITICO", "Servicio activo y nunca facturado."
        elif dias > umbral_dias:
            nivel, motivo = "ALTO", f"Sin factura hace {dias} días (umbral: {umbral_dias})."
        else:
            nivel, motivo = "NORMAL", "Dentro del ciclo esperado."
        filas.append({
            "RAZON_SOCIAL": cliente,
            "tiene_fija": cliente in con_fija,
            "tiene_movil": cliente in con_movil,
            "ultima_factura": ultima,
            "dias_sin_facturar": 10**6 if nunca else dias,
            "nunca_facturado": nunca,
            "nivel_riesgo": nivel,
            "motivo": motivo,
        })

    return pd.DataFrame(filas).sort_values("dias_sin_facturar", ascending=False)


def estimar_impacto(fuga, facturas):
    """Traduce días sin facturar a soles usando el ticket mensual del propio cliente."""
    f = facturas.copy()
    f["mes"] = f.fecha_emision.dt.to_period("M")
    ticket_x_cliente = f.groupby(["RAZON_SOCIAL", "mes"]).total.sum().groupby("RAZON_SOCIAL").mean()
    ticket_general = ticket_x_cliente.mean()

    riesgo = fuga[fuga.nivel_riesgo.isin(["ALTO", "CRITICO"])].copy()
    meses = (riesgo.dias_sin_facturar.clip(upper=TOPE_MESES_EXPOSICION * 30)) / 30
    ticket = riesgo.RAZON_SOCIAL.map(ticket_x_cliente).fillna(ticket_general)
    riesgo["impacto_soles"] = (meses * ticket).round(2)
    return riesgo.sort_values("impacto_soles", ascending=False)


def calidad(facturas, notas_credito):
    con_nc = notas_credito.FACTURA_AFECTADA.nunique()
    return {
        "total_facturas": len(facturas),
        "facturas_con_nota_credito": int(con_nc),
        "tasa_error_pct": round(con_nc / len(facturas) * 100, 2),
        "monto_corregido_soles": round(float(notas_credito.monto.sum()), 2),
    }


def kpis(fuga, impacto, cal):
    en_riesgo = fuga[fuga.nivel_riesgo.isin(["ALTO", "CRITICO"])]
    return {
        "clientes_con_fuga": int(len(en_riesgo)),
        "nunca_facturados": int(fuga.nunca_facturado.sum()),
        "impacto_estimado_soles": round(float(impacto.impacto_soles.sum()), 2),
        "tasa_error_facturacion_pct": cal["tasa_error_pct"],
    }
