"""Agente de BI — riesgo de cobranza dudosa, aging y priorización.

Base: prototipo de Agentes 1551 (agente_bi.py), con tres correcciones:

  1. VENTANA TEMPORAL. Hay facturas desde abril 2023 pero pagos solo de
     jun–jul 2026. Una factura de 2023 sin pago registrado casi seguro se pagó
     fuera de los datos, no es mora. El prototipo original contaba 23 de esas
     (S/ 79,116) como deuda. Aquí el análisis se acota a lo emitido dentro de
     la ventana, como advierte la sección 5.3 del documento de contexto.

  2. FECHA DE CORTE DEL AGING. El original usaba max(FECHA_VTO) = 2026-08-18
     como "hoy", 18 días después del último pago observado, lo que corría todos
     los buckets. Aquí el corte es el último pago real.

  3. KPIs SEPARADOS. El original imprimía "10 clientes ALTO | deuda total
     S/ 159,964" en una línea; esa deuda es de los ~1,000 clientes, no de los
     10. Se reportan por separado para que no se lea mal en una lámina.

Este agente NO relee los CSV crudos: consume lo que ya calcularon Recaudo y
Facturación. Esa dependencia es la coordinación entre agentes que pide la ficha.
"""

import pandas as pd

INICIO_VENTANA = pd.Timestamp("2026-06-01")
BUCKETS = ["Vigente", "0-30 días", "31-60 días", "61-90 días", "90+ días"]


def _saldos(facturas, pagos):
    """Saldo pendiente por factura, acotado a la ventana con datos completos."""
    pagado = pagos.groupby("FACTURA_AFECTADA").monto.sum()
    f = facturas[facturas.fecha_emision >= INICIO_VENTANA].copy()
    f["pagado"] = f.NRO_DOC_FISCAL.map(pagado).fillna(0.0)
    f["saldo"] = (f.total - f.pagado).round(2)
    return f[f.saldo > 0.005]


def calcular_pcd(clientes, facturas, pagos):
    """Provisión de cobranza dudosa: riesgo tributario + comportamiento de pago."""
    pendientes = _saldos(facturas, pagos)

    resumen = pendientes.groupby("RAZON_SOCIAL").agg(
        facturas_pendientes=("NRO_DOC_FISCAL", "count"),
        deuda_pendiente=("saldo", "sum"),
    )

    sunat = clientes.set_index("RAZON_SOCIAL")
    riesgo_sunat = (
        (sunat.SUNAT_ESTADO_RUC == "NO HABIDO") | (sunat.SUNAT_ESTADO_CONTRIBUYENTE != "ACTIVO")
    ).astype(int) * 2

    base = resumen.join(riesgo_sunat.rename("puntos_sunat"), how="left").fillna({"puntos_sunat": 0})
    base["puntos_deuda"] = base.facturas_pendientes.clip(upper=5)
    base["puntaje_riesgo"] = base.puntos_sunat + base.puntos_deuda
    base["nivel_pcd"] = pd.cut(
        base.puntaje_riesgo, bins=[-1, 1, 4, 99], labels=["BAJO", "MEDIO", "ALTO"]
    ).astype(str)

    return base.reset_index().sort_values("puntaje_riesgo", ascending=False)


def calcular_aging(facturas, pagos):
    """Antigüedad de la deuda, cortada al último pago realmente observado."""
    corte = pagos.fecha_pago.max()
    pendientes = _saldos(facturas, pagos).copy()
    pendientes["dias_vencido"] = (corte - pendientes.fecha_vto).dt.days

    pendientes["bucket"] = pd.cut(
        pendientes.dias_vencido,
        bins=[-10**6, 0, 30, 60, 90, 10**6],
        labels=BUCKETS,
    ).astype(str)

    resumen = pendientes.groupby("bucket").agg(
        n_facturas=("NRO_DOC_FISCAL", "count"),
        monto_pendiente=("saldo", "sum"),
    ).reindex(BUCKETS).fillna(0).reset_index()
    resumen.attrs["fecha_corte"] = corte
    return resumen


def priorizar(pcd, fuga, top_n=10):
    """A quién cobrar primero y por qué — la estrategia ad-hoc que pide la ficha."""
    con_fuga = set(fuga[fuga.nivel_riesgo.isin(["ALTO", "CRITICO"])].RAZON_SOCIAL)

    p = pcd.copy()
    p["tiene_fuga"] = p.RAZON_SOCIAL.isin(con_fuga)

    def estrategia(r):
        if r.nivel_pcd == "ALTO" and r.tiene_fuga:
            return ("URGENTE: riesgo de impago Y servicio activo sin facturar. "
                    "Visita comercial, no cobranza automática.")
        if r.nivel_pcd == "ALTO":
            return "Riesgo alto de impago. Priorizar en la siguiente ronda de cobranza."
        if r.tiene_fuga:
            return "Paga bien pero tiene servicio sin facturar — corregir antes de que acumule."
        return "Seguimiento estándar."

    p["estrategia"] = p.apply(estrategia, axis=1)
    orden = {"ALTO": 0, "MEDIO": 1, "BAJO": 2}
    p["_o"] = p.nivel_pcd.map(orden)
    return p.sort_values(["_o", "tiene_fuga", "deuda_pendiente"],
                         ascending=[True, False, False]).drop(columns="_o").head(top_n)


def kpis(pcd, aging):
    alto = pcd[pcd.nivel_pcd == "ALTO"]
    mayor = aging.loc[aging.monto_pendiente.idxmax()]
    return {
        "clientes_riesgo_alto": int(len(alto)),
        "deuda_de_los_riesgo_alto_soles": round(float(alto.deuda_pendiente.sum()), 2),
        "deuda_pendiente_total_soles": round(float(pcd.deuda_pendiente.sum()), 2),
        "bucket_mayor_concentracion": mayor.bucket,
        "monto_bucket_mayor_soles": round(float(mayor.monto_pendiente), 2),
    }
