"""Asignación global por cliente — ¿decidir depósito por depósito pierde soluciones?

LA HIPÓTESIS
------------
Hoy el motor procesa los depósitos en orden cronológico: cada uno se lleva las
facturas que le calzan, y el siguiente ya no las tiene. Eso es greedy. Si el
depósito del 5 de junio se queda con una factura que en realidad correspondía al
del 20, ambos quedan mal.

La alternativa: plantear TODOS los depósitos de un cliente contra TODAS sus
facturas abiertas como un solo problema de asignación, y resolverlo óptimo con
programación por restricciones (CP-SAT de OR-Tools).

El 85% de los clientes tiene 2 o más depósitos en la ventana, así que la
población donde esto puede ganar es grande. Si gana o no es una pregunta
empírica, y este módulo la responde.

FORMULACIÓN
-----------
Por cliente:
    x[i][d] = 1  si la factura i se aplica al depósito d
    cada factura va a lo sumo a un depósito
    si un depósito se declara resuelto, sus facturas suman su monto exacto
    maximizar el número de depósitos resueltos (desempate: monto resuelto)

    python asignacion.py
"""

import time

from ortools.sat.python import cp_model

import backtest
import datos
import solver

LIMITE_SEGUNDOS = 2.0     # por cliente; el problema es diminuto, con esto sobra
MAX_FACTURAS = 60         # por encima de esto el modelo crece sin aportar


def resolver_cliente(depositos, facturas, limite=LIMITE_SEGUNDOS):
    """depositos: [(id, centimos)] · facturas: [(nro, centimos)] -> {id_dep: [nros]}"""
    if not depositos or not facturas:
        return {}

    modelo = cp_model.CpModel()
    x = {(i, d): modelo.NewBoolVar(f"x_{i}_{d}")
         for i in range(len(facturas)) for d in range(len(depositos))}
    resuelto = [modelo.NewBoolVar(f"y_{d}") for d in range(len(depositos))]

    # Una factura no puede aplicarse a dos depósitos distintos
    for i in range(len(facturas)):
        modelo.AddAtMostOne(x[i, d] for d in range(len(depositos)))

    for d, (_, monto) in enumerate(depositos):
        suma = sum(x[i, d] * facturas[i][1] for i in range(len(facturas)))
        # Si el depósito se declara resuelto, sus facturas suman exacto;
        # si no, no se le asigna ninguna.
        modelo.Add(suma == monto).OnlyEnforceIf(resuelto[d])
        modelo.Add(suma == 0).OnlyEnforceIf(resuelto[d].Not())

    # Prioridad: resolver la mayor cantidad de depósitos; a igualdad, el mayor monto
    modelo.Maximize(sum(resuelto[d] * (10**6 + depositos[d][1]) for d in range(len(depositos))))

    solucionador = cp_model.CpSolver()
    solucionador.parameters.max_time_in_seconds = limite
    solucionador.parameters.num_workers = 4
    if solucionador.Solve(modelo) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {}

    return {
        depositos[d][0]: [facturas[i][0] for i in range(len(facturas))
                          if solucionador.Value(x[i, d])]
        for d in range(len(depositos)) if solucionador.Value(resuelto[d])
    }


def comparar():
    f, p = datos.facturas(), datos.pagos()
    por_factura, fx_cliente, pagos_fx = backtest.construir_indices(f, p)
    conocidas = set(por_factura)

    # Verdad por evento, y los depósitos tal como llegan del banco
    verdad, depositos_cliente = {}, {}
    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        clave = (cliente, fecha)
        verdad[clave] = set(grupo.FACTURA_AFECTADA)
        depositos_cliente.setdefault(cliente, []).append(
            (clave, solver.a_centimos(grupo.monto.sum())))

    secuencial = global_ = evaluables = 0
    t0 = time.time()

    for cliente, deps in depositos_cliente.items():
        deps.sort(key=lambda t: t[0][1])  # cronológico

        # --- estrategia actual: cada depósito por su cuenta, en orden ---
        for clave, monto in deps:
            if not verdad[clave] <= conocidas:
                continue
            evaluables += 1
            cands = backtest.candidatas_abiertas(cliente, clave[1], por_factura, fx_cliente,
                                                 pagos_fx, backtest.VENTANA_ADELANTO_DIAS)
            sols, _ = solver.resolver(cands, monto)
            if sols and set(solver.ranking(sols, por_factura, clave[1])[0]) == verdad[clave]:
                secuencial += 1

        # --- estrategia global: todos los depósitos del cliente a la vez ---
        universo = {}
        for clave, _ in deps:
            for c in backtest.candidatas_abiertas(cliente, clave[1], por_factura, fx_cliente,
                                                  pagos_fx, backtest.VENTANA_ADELANTO_DIAS):
                universo[c["factura"]] = c["centimos"]
        if len(universo) > MAX_FACTURAS:
            universo = dict(sorted(universo.items(), key=lambda kv: -kv[1])[:MAX_FACTURAS])

        asignacion = resolver_cliente(deps, list(universo.items()))
        for clave, _ in deps:
            if verdad[clave] <= conocidas and set(asignacion.get(clave, [])) == verdad[clave]:
                global_ += 1

    return {"evaluables": evaluables, "secuencial": secuencial, "global": global_,
            "segundos": time.time() - t0}


def main():
    print("Comparando estrategia secuencial vs. asignación global por cliente...")
    print("(resuelve un modelo CP-SAT por cliente; toma unos minutos)\n")
    r = comparar()
    n = r["evaluables"]

    print("=" * 72)
    print("¿ASIGNAR GLOBALMENTE LE GANA A DECIDIR DEPÓSITO POR DEPÓSITO?")
    print("=" * 72)
    print(f"  Eventos evaluables            : {n:,}")
    print(f"  Secuencial (lo que hay hoy)   : {r['secuencial']:>5,}  ({r['secuencial'] / n:.1%})")
    print(f"  Asignación global (CP-SAT)    : {r['global']:>5,}  ({r['global'] / n:.1%})")

    delta = r["global"] - r["secuencial"]
    print(f"\n  Diferencia: {delta:+,} eventos ({delta / n:+.1%})")
    print(f"  Tiempo total: {r['segundos']:.0f}s")

    print("\n" + "-" * 72)
    if delta > 0:
        print("  La asignación global gana. Vale cambiar el motor: resolver por cliente")
        print("  en vez de por depósito evita que un pago bloquee la solución de otro.")
    elif delta == 0:
        print("  Empate. El enfoque secuencial no está perdiendo soluciones aquí: la")
        print("  ventana de suspenso y el saldo por factura ya evitan casi todo el")
        print("  bloqueo que la formulación global corregiría.")
    else:
        print("  El secuencial gana. La asignación global maximiza depósitos resueltos,")
        print("  y ese criterio a veces prefiere una combinación que cuadra el conjunto")
        print("  pero no corresponde a la realidad. Optimalidad matemática no es acierto.")
    print("=" * 72)


if __name__ == "__main__":
    main()
