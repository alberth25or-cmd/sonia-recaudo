"""Agente de Recaudo — identifica a qué factura pertenece cada depósito.

QUÉ PROBLEMA RESUELVE
---------------------
Del banco llega una lista de depósitos: empresa, monto, fecha. Sin factura.
Alguien en Integratel tiene que averiguar, para cada uno, qué factura(s) paga.
Ese es el cuello de botella que el equipo de Movistar señaló como el más duro.

CÓMO LO RESUELVE
----------------
No le pregunta al LLM qué facturas suman el depósito: eso es subset-sum y se
resuelve exacto con código (ver solver.py). El LLM entra solo donde hay criterio
de negocio en juego.

El resultado de cada depósito cae en una de cuatro colas, según cuánto trabajo
humano necesita. Ver triaje.py para la medición de carga.

LO QUE ESTE AGENTE NO HACE
--------------------------
No lee PAGOS.FACTURA_AFECTADA para decidir. Esa columna es la respuesta que hoy
producen a mano los analistas — usarla como insumo mediría la calidad del dato,
no la capacidad del agente. Aquí se usa exclusivamente para EVALUAR la propuesta
a posteriori (ver backtest.py), nunca para construirla.
"""

import pandas as pd

import backtest
import solver

TOLERANCIA_SOLES = 0.00  # calibrado en triaje.py: con 0 la banda automática se equivoca 1 de 1,596

COLAS = {
    "AUTO": "Solución única y exacta — se aplica sin intervención",
    "CONFIRMAR": "Varias combinaciones válidas — el humano elige entre opciones ordenadas",
    "HIPOTESIS": "Sin calce exacto, pero el depósito cabe en una factura abierta (pago parcial)",
    "INVESTIGAR": "Nada encaja — depósito huérfano, moneda extranjera o factura fuera del sistema",
}

# Fuente única de los tiempos por caso: los usan triaje.py, orquestador.py y
# reporte.py. Son SUPUESTOS de diseño, no medidos con un operador real —
# cronometrar y ajustar aquí recalcula el personal en los tres sitios.
SEGUNDOS_POR_CASO = {"AUTO": 0, "CONFIRMAR": 20, "HIPOTESIS": 60, "INVESTIGAR": 300}
DIAS_HABILES_VENTANA = 43   # jun-jul 2026
JORNADA_MINUTOS = 7 * 60    # horas productivas por jornada


def carga_humana(decisiones):
    """Minutos de trabajo humano por día hábil, y su equivalente en FTE."""
    minutos = sum(
        int((decisiones.cola == cola).sum()) * seg / 60 / DIAS_HABILES_VENTANA
        for cola, seg in SEGUNDOS_POR_CASO.items()
    )
    return {"minutos_por_dia_habil": round(minutos, 1),
            "fte": round(minutos / JORNADA_MINUTOS, 3)}


def _depositos(pagos):
    """Reconstruye lo que llega del banco: empresa, día y monto. Sin la factura."""
    return (
        pagos.groupby(["RAZON_SOCIAL", "fecha_pago"])
        .agg(monto=("monto", "sum"), n_movimientos=("monto", "size"))
        .reset_index()
    )


def procesar(facturas, pagos, tolerancia_soles=TOLERANCIA_SOLES):
    """Procesa todos los depósitos y devuelve una decisión por cada uno."""
    por_factura, facturas_cliente, pagos_factura = backtest.construir_indices(facturas, pagos)
    tol = solver.a_centimos(tolerancia_soles)

    decisiones = []
    for d in _depositos(pagos).itertuples():
        cands = backtest.candidatas_abiertas(
            d.RAZON_SOCIAL, d.fecha_pago, por_factura, facturas_cliente,
            pagos_factura, backtest.VENTANA_ADELANTO_DIAS,
        )
        deposito = solver.a_centimos(d.monto)
        soluciones, podado = solver.resolver(cands, deposito, tolerancia_centimos=tol)

        parcial = None
        if soluciones:
            ordenadas = solver.ranking(soluciones, por_factura, d.fecha_pago)
            propuesta = ordenadas[0]
            cola = "AUTO" if len(soluciones) == 1 else "CONFIRMAR"
            alternativas = [list(s) for s in ordenadas[1:4]]
        else:
            propuesta = ()
            alternativas = []
            # Si el depósito cabe dentro de alguna factura abierta, la hipótesis
            # natural es pago parcial. Se sugiere la que vence más cerca del
            # depósito: es contra la que el cliente estaba pagando.
            absorben = [c for c in cands if c["centimos"] > deposito]
            cola = "HIPOTESIS" if absorben else "INVESTIGAR"
            if absorben:
                elegida = min(absorben, key=lambda c: abs((c["fecha_vto"] - d.fecha_pago).days)
                              if c["fecha_vto"] is not None else 10**6)
                parcial = {
                    "factura": elegida["factura"],
                    "importe": round(elegida["centimos"] / 100, 2),
                    "saldo_restante": round((elegida["centimos"] - deposito) / 100, 2),
                }

        decisiones.append({
            "cliente": d.RAZON_SOCIAL,
            "fecha": d.fecha_pago,
            "monto": round(d.monto, 2),
            "cola": cola,
            "facturas_propuestas": list(propuesta),
            "n_candidatas": len(cands),
            "n_soluciones": len(soluciones),
            "alternativas": alternativas,
            "parcial_sugerido": parcial,
            "abiertas": [{"factura": c["factura"],
                          "importe": round(c["centimos"] / 100, 2),
                          "vence": c["fecha_vto"]} for c in cands],
            "explicacion": _explicar(cola, propuesta, cands, por_factura, d),
        })

    return pd.DataFrame(decisiones)


def _explicar(cola, propuesta, cands, por_factura, dep):
    """Una línea que el operador pueda auditar sin abrir otro sistema."""
    if cola == "AUTO":
        vtos = [por_factura[n]["fecha_vto"] for n in propuesta if por_factura[n]["fecha_vto"] is not None]
        cerca = min((abs((v - dep.fecha_pago).days) for v in vtos), default=None)
        detalle = f"; vence a {cerca} día(s) del depósito" if cerca is not None else ""
        return (f"Única combinación que suma exacto: {len(propuesta)} factura(s){detalle}.")
    if cola == "CONFIRMAR":
        return (f"{len(propuesta)} factura(s) en la propuesta principal, pero hay más combinaciones "
                f"que suman lo mismo. Se ordenó por cercanía al vencimiento.")
    if cola == "HIPOTESIS":
        mayores = [c for c in cands if c["centimos"] > solver.a_centimos(dep.monto)]
        return (f"Ninguna combinación suma exacto, pero el depósito cabe dentro de "
                f"{len(mayores)} factura(s) abierta(s): probable pago parcial.")
    return (f"Ninguna de las {len(cands)} facturas abiertas del cliente explica el monto. "
            f"Revisar si corresponde a una factura fuera del sistema o a otra moneda.")


def kpis(decisiones):
    conteo = decisiones.cola.value_counts()
    monto = decisiones.groupby("cola").monto.sum()
    total = len(decisiones)
    auto = int(conteo.get("AUTO", 0))
    return {
        "depositos_procesados": total,
        "aplicados_sin_intervencion": auto,
        # STP (straight-through processing) es la métrica con que la industria
        # mide esta categoría. Ver benchmark.py para el posicionamiento.
        "stp_pct": round(auto / total * 100, 1) if total else 0,
        "monto_aplicado_solo_soles": round(float(monto.get("AUTO", 0)), 2),
        "en_cola_confirmar": int(conteo.get("CONFIRMAR", 0)),
        "en_cola_hipotesis": int(conteo.get("HIPOTESIS", 0)),
        "en_cola_investigar": int(conteo.get("INVESTIGAR", 0)),
    }
