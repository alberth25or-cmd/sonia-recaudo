"""Triaje de la cola humana: cuantos casos llegan, de que tipo, y cuanto cuestan.

La pregunta de negocio no es "cuantos casos escalan" sino "cuanta gente hace
falta". Y eso depende del TIPO de caso, no del numero: confirmar una propuesta
ya calculada toma segundos; investigar un deposito huerfano toma minutos.

Cuatro colas, de menor a mayor esfuerzo humano:

  COLA_0  AUTO       el solver encontro UNA sola combinacion exacta.
                     Se aplica sola. El humano no la ve (solo la audita por muestreo).
  COLA_1  CONFIRMAR  varias combinaciones validas. El humano ve la propuesta
                     ordenada y las alternativas: elige. No calcula nada.
  COLA_2  HIPOTESIS  no hay combinacion exacta, pero el deposito cabe dentro de
                     una factura abierta -> pago parcial. El agente propone, el
                     humano aprueba.
  COLA_3  INVESTIGAR nada encaja. Deposito huerfano, USD sin tipo de cambio,
                     factura fuera del sistema. Aqui si hace falta un analista.

Los tiempos por caso son SUPUESTOS declarados, no medidos. Cambialos en
SEGUNDOS_POR_CASO y el calculo de personal se recalcula solo.
"""

from collections import defaultdict

import pandas as pd

import backtest
import datos
import solver

from agentes import recaudo

# Los tiempos por caso viven en un solo sitio (agentes/recaudo.py); aqui solo se
# les pone un nombre de cola legible para el reporte.
SEGUNDOS_POR_CASO = {
    f"COLA_{i}_{cola}": recaudo.SEGUNDOS_POR_CASO[cola]
    for i, cola in enumerate(("AUTO", "CONFIRMAR", "HIPOTESIS", "INVESTIGAR"))
}

DIAS_HABILES_VENTANA = recaudo.DIAS_HABILES_VENTANA
JORNADA_MINUTOS = recaudo.JORNADA_MINUTOS


def triar(tolerancia_soles=0.0):
    """Clasifica cada evento en una de las cuatro colas."""
    f = datos.facturas()
    p = datos.pagos()
    por_factura, facturas_cliente, pagos_factura = backtest.construir_indices(f, p)
    conocidas = set(por_factura)
    tol = solver.a_centimos(tolerancia_soles)

    colas = defaultdict(lambda: {"n": 0, "soles": 0.0, "aciertos": 0, "evaluables": 0})

    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        verdad = set(grupo.FACTURA_AFECTADA)
        deposito = solver.a_centimos(grupo.monto.sum())
        soles = grupo.monto.sum()
        evaluable = verdad <= conocidas

        cands = backtest.candidatas_abiertas(cliente, fecha, por_factura, facturas_cliente,
                                             pagos_factura, backtest.VENTANA_ADELANTO_DIAS)
        soluciones, _ = solver.resolver(cands, deposito, tolerancia_centimos=tol)

        if len(soluciones) == 1:
            cola = "COLA_0_AUTO"
        elif len(soluciones) > 1:
            cola = "COLA_1_CONFIRMAR"
        elif any(c["centimos"] > deposito for c in cands):
            # el deposito cabe dentro de una factura abierta -> pago parcial plausible
            cola = "COLA_2_HIPOTESIS"
        else:
            cola = "COLA_3_INVESTIGAR"

        colas[cola]["n"] += 1
        colas[cola]["soles"] += soles

        if evaluable and soluciones:
            colas[cola]["evaluables"] += 1
            propuesta = set(solver.ranking(soluciones, por_factura, fecha)[0])
            if propuesta == verdad:
                colas[cola]["aciertos"] += 1

    return colas


def reportar(colas, tolerancia):
    orden = ["COLA_0_AUTO", "COLA_1_CONFIRMAR", "COLA_2_HIPOTESIS", "COLA_3_INVESTIGAR"]
    total = sum(c["n"] for c in colas.values())
    monto_total = sum(c["soles"] for c in colas.values())

    print("=" * 74)
    print(f"TRIAJE DE LA COLA HUMANA  ·  tolerancia S/ {tolerancia:.2f}  ·  {total:,} eventos")
    print("=" * 74)
    print(f"{'cola':<20} {'casos':>7} {'%':>7} {'S/ movido':>13} {'precision':>10} {'min/dia':>9}")
    print("-" * 74)

    minutos_dia_total = 0.0
    for nombre in orden:
        c = colas[nombre]
        if not c["n"]:
            continue
        seg = SEGUNDOS_POR_CASO[nombre]
        minutos_dia = c["n"] * seg / 60 / DIAS_HABILES_VENTANA
        minutos_dia_total += minutos_dia
        prec = f"{c['aciertos'] / c['evaluables']:.1%}" if c["evaluables"] else "—"
        print(f"{nombre:<20} {c['n']:>7,} {c['n'] / total:>6.1%} "
              f"{c['soles']:>13,.0f} {prec:>10} {minutos_dia:>8.0f}m")

    print("-" * 74)
    print(f"{'TOTAL':<20} {total:>7,} {1:>6.0%} {monto_total:>13,.0f} {'':>10} {minutos_dia_total:>8.0f}m")

    fte = minutos_dia_total / JORNADA_MINUTOS
    print(f"\n  Carga humana: {minutos_dia_total:.0f} min/dia habil  ->  {fte:.2f} FTE")
    print(f"  (jornada de {JORNADA_MINUTOS // 60}h productivas; supuestos de tiempo en SEGUNDOS_POR_CASO)")

    auto = colas["COLA_0_AUTO"]
    if auto["evaluables"]:
        errores = auto["evaluables"] - auto["aciertos"]
        print(f"\n  Riesgo de la banda automatica (lo que NADIE revisa):")
        print(f"    {auto['n']:,} casos aplicados solos · {errores} equivocados de "
              f"{auto['evaluables']:,} verificables ({errores / auto['evaluables']:.2%})")
        print(f"    -> es la cifra que justifica el muestreo de auditoria, no la fe")


def main():
    for tol in (0.00, 1.00):
        reportar(triar(tol), tol)
        print()


if __name__ == "__main__":
    main()
