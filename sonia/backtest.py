"""Backtest del motor de recaudo contra el ground truth del reto.

SIMULACION
----------
En la realidad el deposito llega identificado por empresa pero SIN saber que
factura paga. En los datos, PAGOS.FACTURA_AFECTADA ya trae esa respuesta: es el
trabajo manual que alguien en Integratel ya hizo.

Entonces escondemos esa columna. Para cada evento (cliente + dia) le damos al
motor solo lo que tendria en produccion:
  - el monto total depositado
  - las facturas del cliente abiertas a esa fecha

y comparamos su propuesta contra la respuesta escondida.

Esto no es una demo: es una medicion sobre los 3,548 pagos del dataset entregado.

ADVERTENCIA SOBRE EL DATASET
----------------------------
Los CSV del reto son SINTETICOS. La metodologia (esconder la respuesta y medir)
transfiere a produccion; el numero concreto depende de que el generador haya
reproducido la distribucion real de casos dificiles. Ver procedencia.py, que
separa que patrones son estructurales del negocio y cuales del generador.
"""

import sys
from collections import defaultdict

import pandas as pd

import datos
import solver

TOLERANCIA_SOLES = 1.00  # margen para dar un calce por bueno (redondeos, centavos)

# El 5.8% de los pagos del dataset llega ANTES de que su factura se emita, y sin
# esta ventana se rompen 161 eventos agrupados.
#
# OJO CON LA INTERPRETACION: en el dataset sintetico ese desfase se concentra
# entre 9 y 15 dias (mediana 10), lo que parece un efecto de frontera de ciclo
# del generador mas que pago anticipado organico -- un anticipo real se
# concentraria en 1-3 dias. La ventana es necesaria para procesar ESTOS datos;
# en produccion habria que recalibrarla contra el comportamiento verdadero.
# Ver procedencia.py. 10 dias es el optimo medido en barrido.py.
VENTANA_ADELANTO_DIAS = 10


def construir_indices(f, p):
    por_factura = {
        r.NRO_DOC_FISCAL: {
            "cliente": r.RAZON_SOCIAL,
            "centimos": solver.a_centimos(r.total),
            "fecha_emision": r.fecha_emision,
            "fecha_vto": None if pd.isna(r.fecha_vto) else r.fecha_vto,
        }
        for r in f.itertuples()
    }

    facturas_cliente = defaultdict(list)
    for nro, info in por_factura.items():
        facturas_cliente[info["cliente"]].append(nro)

    pagos_factura = defaultdict(list)
    for r in p.itertuples():
        pagos_factura[r.FACTURA_AFECTADA].append((r.fecha_pago, solver.a_centimos(r.monto)))

    return por_factura, facturas_cliente, pagos_factura


def candidatas_abiertas(cliente, fecha, por_factura, facturas_cliente, pagos_factura, ventana):
    """Facturas del cliente abiertas a esa fecha, con su SALDO como monto.

    El monto candidato es el saldo y no el total: 169 facturas del reto se pagan
    en cuotas, y contra esas lo que llega a cuadrar es lo que queda debiendo.
    """
    limite = fecha + pd.Timedelta(days=ventana)
    abiertas = []
    for nro in facturas_cliente.get(cliente, ()):
        info = por_factura[nro]
        if info["fecha_emision"] > limite:
            continue
        pagado_antes = sum(c for fp, c in pagos_factura.get(nro, ()) if fp < fecha)
        saldo = info["centimos"] - pagado_antes
        if saldo <= 0:
            continue
        abiertas.append({"factura": nro, "centimos": saldo,
                         "fecha_emision": info["fecha_emision"],
                         "fecha_vto": info["fecha_vto"]})
    return abiertas


def ejecutar(ventana=VENTANA_ADELANTO_DIAS, tolerancia_soles=TOLERANCIA_SOLES, guardar_fallos=False):
    f = datos.facturas()
    p = datos.pagos()
    por_factura, facturas_cliente, pagos_factura = construir_indices(f, p)
    conocidas = set(por_factura)
    tol = solver.a_centimos(tolerancia_soles)

    stats = defaultdict(int)
    montos = defaultdict(float)
    ambiguedad = []
    fallos = []

    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        verdad = set(grupo.FACTURA_AFECTADA)
        deposito = solver.a_centimos(grupo.monto.sum())
        soles = grupo.monto.sum()

        stats["eventos"] += 1
        etq = "agrupado" if len(verdad) > 1 else "simple"
        stats[f"{etq}:total"] += 1
        montos[f"{etq}:total"] += soles

        # Eventos que tocan facturas fuera del dataset: no se pueden evaluar.
        if not verdad <= conocidas:
            stats[f"{etq}:huerfano"] += 1
            montos[f"{etq}:huerfano"] += soles
            continue

        cands = candidatas_abiertas(cliente, fecha, por_factura, facturas_cliente,
                                    pagos_factura, ventana)

        # Techo alcanzable: si alguna factura de la respuesta no esta entre las
        # candidatas, ningun solver puede acertar. Separa el limite del universo
        # de candidatas del limite del algoritmo.
        if not verdad <= {c["factura"] for c in cands}:
            stats[f"{etq}:fuera_de_universo"] += 1
            montos[f"{etq}:fuera_de_universo"] += soles

        soluciones, podado = solver.resolver(cands, deposito, tolerancia_centimos=tol)
        if podado:
            stats[f"{etq}:podado"] += 1

        if not soluciones:
            stats[f"{etq}:sin_solucion"] += 1
            montos[f"{etq}:sin_solucion"] += soles
            if guardar_fallos:
                fallos.append((cliente, fecha, soles, len(cands), len(verdad)))
            continue

        ordenadas = solver.ranking(soluciones, por_factura, fecha)
        propuesta = set(ordenadas[0])

        if len(soluciones) > 1:
            stats[f"{etq}:ambiguo"] += 1
            ambiguedad.append(len(soluciones))

        if propuesta == verdad:
            stats[f"{etq}:acierto_top1"] += 1
            montos[f"{etq}:acierto_top1"] += soles
        elif any(set(s) == verdad for s in ordenadas):
            stats[f"{etq}:verdad_en_lista"] += 1
            montos[f"{etq}:verdad_en_lista"] += soles
        else:
            stats[f"{etq}:error"] += 1
            montos[f"{etq}:error"] += soles

    return stats, montos, ambiguedad, fallos


def reportar(stats, montos, ambiguedad, fallos, ventana, tolerancia):
    print("=" * 64)
    print("BACKTEST DEL MOTOR DE RECAUDO  ·  ground truth = 3,548 pagos reales")
    print(f"ventana de suspenso: {ventana} dias · tolerancia de calce: S/ {tolerancia:.2f}")
    print("=" * 64)

    for etq, titulo in [("agrupado", "PAGOS AGRUPADOS (varias facturas en un dia)"),
                        ("simple", "PAGOS SIMPLES (una sola factura)")]:
        total = stats[f"{etq}:total"]
        evaluables = total - stats[f"{etq}:huerfano"]
        print(f"\n{titulo}")
        print(f"  eventos                    : {total:>5,}   S/ {montos[f'{etq}:total']:>12,.2f}")
        print(f"  no evaluables (huerfanos)  : {stats[f'{etq}:huerfano']:>5,}   S/ {montos[f'{etq}:huerfano']:>12,.2f}")
        print(f"  evaluables                 : {evaluables:>5,}")
        if not evaluables:
            continue
        for clave, nombre in [("acierto_top1", "ACIERTO en la 1a propuesta"),
                              ("verdad_en_lista", "correcta pero no 1a"),
                              ("error", "propuesta incorrecta"),
                              ("sin_solucion", "sin solucion -> escala")]:
            n = stats[f"{etq}:{clave}"]
            print(f"    {nombre:<28s} {n:>5,}  {n / evaluables:>6.1%}   S/ {montos[f'{etq}:{clave}']:>12,.2f}")
        fuera = stats[f"{etq}:fuera_de_universo"]
        print(f"    {'-- techo alcanzable':<28s} {evaluables - fuera:>5,}  {(evaluables - fuera) / evaluables:>6.1%}"
              f"   ({fuera:,} con facturas fuera del universo)")
        print(f"    (ambiguos: {stats[f'{etq}:ambiguo']:,} · podados: {stats[f'{etq}:podado']:,})")

    ev = sum(stats[f"{e}:total"] - stats[f"{e}:huerfano"] for e in ("agrupado", "simple"))
    ok = stats["agrupado:acierto_top1"] + stats["simple:acierto_top1"]
    monto_ok = montos["agrupado:acierto_top1"] + montos["simple:acierto_top1"]
    print("\n" + "-" * 64)
    print(f"GLOBAL: {ok:,} de {ev:,} eventos resueltos automaticamente  ({ok / ev:.1%})")
    print(f"        S/ {monto_ok:,.2f} conciliados sin intervencion humana")
    if ambiguedad:
        print(f"        ambiguedad media cuando la hay: {sum(ambiguedad) / len(ambiguedad):.1f} combinaciones")
    print("-" * 64)

    if fallos:
        print("\nMuestra de eventos sin solucion (los que van al agente LLM):")
        for cliente, fecha, soles, ncand, nverdad in sorted(fallos, key=lambda t: -t[2])[:8]:
            print(f"  {cliente}  {fecha:%Y-%m-%d}  S/ {soles:>10,.2f}  "
                  f"{ncand:>3} candidatas, la verdad usaba {nverdad}")


def main():
    ventana = int(sys.argv[1]) if len(sys.argv) > 1 else VENTANA_ADELANTO_DIAS
    stats, montos, amb, fallos = ejecutar(ventana, guardar_fallos=True)
    reportar(stats, montos, amb, fallos, ventana, TOLERANCIA_SOLES)


if __name__ == "__main__":
    main()
