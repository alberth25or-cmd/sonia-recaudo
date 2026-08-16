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

# El asignador aprendido es OPCIONAL: ataca los casos que el solver no resuelve.
# Si falta el artefacto —o sklearn— el motor funciona igual con la heurística.
try:
    import asignador
except Exception:                                     # pragma: no cover
    asignador = None

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
#
# INVESTIGAR bajó de 300 a 120 segundos al conectar asignador.py. El supuesto de
# 5 minutos correspondía a un caso que llegaba EN BLANCO: el operador abría el
# estado de cuenta y buscaba desde cero. Ahora llega con una factura señalada y
# su confianza (97.7% de acierto medido sobre julio), así que el trabajo pasa a
# ser confirmar o corregir. Se deja por encima de HIPOTESIS porque aquí ninguna
# factura absorbe el depósito y la revisión es menos evidente.
SEGUNDOS_POR_CASO = {"AUTO": 0, "CONFIRMAR": 20, "HIPOTESIS": 60, "INVESTIGAR": 120}
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

    # Se carga una sola vez, no por depósito. None = no hay artefacto entrenado.
    modelo = asignador.cargar()[0] if asignador else None

    decisiones = []
    for d in _depositos(pagos).itertuples():
        cands = backtest.candidatas_abiertas(
            d.RAZON_SOCIAL, d.fecha_pago, por_factura, facturas_cliente,
            pagos_factura, backtest.VENTANA_ADELANTO_DIAS,
        )
        deposito = solver.a_centimos(d.monto)
        soluciones, podado = solver.resolver(cands, deposito, tolerancia_centimos=tol)

        parcial, ranking_modelo = None, []
        if soluciones:
            ordenadas = solver.ranking(soluciones, por_factura, d.fecha_pago)
            propuesta = ordenadas[0]
            cola = "AUTO" if len(soluciones) == 1 else "CONFIRMAR"
            alternativas = [list(s) for s in ordenadas[1:4]]
        else:
            propuesta = ()
            alternativas = []
            absorben = [c for c in cands if c["centimos"] > deposito]
            cola = "HIPOTESIS" if absorben else "INVESTIGAR"

            # Aquí no hay combinaciones que ordenar, así que entra el asignador
            # aprendido: puntúa factura por factura la probabilidad de que el
            # pago la esté tocando. Es lo que hace que la cola INVESTIGAR deje
            # de llegar en blanco. El humano sigue confirmando: el modelo
            # propone, nunca aplica.
            if asignador and cands:
                ranking_modelo = asignador.proponer(cands, deposito, d.fecha_pago,
                                                    modelo=modelo)

            # La sugerencia de pago parcial exige una factura que ABSORBA el
            # depósito. Se elige la mejor puntuada entre esas; sin modelo, la
            # que vence más cerca.
            if absorben:
                puntuadas = {r["factura"]: r["puntaje"] for r in ranking_modelo
                             if r["puntaje"] is not None}
                if puntuadas:
                    elegida = max(absorben, key=lambda c: puntuadas.get(c["factura"], -1))
                else:
                    elegida = min(absorben,
                                  key=lambda c: abs((c["fecha_vto"] - d.fecha_pago).days)
                                  if c["fecha_vto"] is not None else 10**6)
                parcial = {
                    "factura": elegida["factura"],
                    "importe": round(elegida["centimos"] / 100, 2),
                    "saldo_restante": round((elegida["centimos"] - deposito) / 100, 2),
                    "puntaje": puntuadas.get(elegida["factura"]),
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
            "ranking_modelo": ranking_modelo,
            "abiertas": [{"factura": c["factura"],
                          "importe": round(c["centimos"] / 100, 2),
                          "vence": c["fecha_vto"]} for c in cands],
            "explicacion": _explicar(cola, propuesta, cands, por_factura, d, ranking_modelo),
        })

    return pd.DataFrame(decisiones)


def _explicar(cola, propuesta, cands, por_factura, dep, ranking=()):
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

    # INVESTIGAR. Antes este caso llegaba en blanco y el operador arrancaba de
    # cero; con el asignador entrenado llega con una factura señalada.
    top = next((r for r in ranking if r.get("puntaje") is not None), None)
    if top:
        # Un decimal, y nunca "100%": el modelo no está seguro del todo nunca, y
        # decirlo así le enseña al operador a no revisar.
        conf = min(top["puntaje"], 0.999)
        return (f"Ninguna combinación suma exacto. El modelo señala la factura "
                f"{top['factura']} (S/ {top['importe']:,.2f}) como la más probable, "
                f"con {conf:.1%} de confianza. Confirmar o corregir.")
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
