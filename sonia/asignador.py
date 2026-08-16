"""Asignador aprendido — el modelo que ataca los casos que el solver no resuelve.

QUÉ PROBLEMA ATACA, Y POR QUÉ ES OTRO
-------------------------------------
El solver de solver.py resuelve por suma exacta: encuentra qué combinación de
facturas suma el depósito. Cuando existe una sola, se aplica sola (70.6%).

Pero quedan 537 depósitos donde NO existe ninguna combinación exacta. Medimos
qué son: la mediana paga el 59% de lo que se le facturó. No son descuentos ni
retenciones —eso daría 95-99%— son PAGOS PARCIALES GRANDES: el cliente debe algo
repartido en varias facturas y abona una parte.

Ahí no hay combinaciones que ordenar, así que el enfoque de aprendizaje.py —que
elige entre las candidatas del solver— no aplica. La pregunta es otra:

    dado un depósito y N facturas abiertas, ¿a cuál se está aplicando?

POR QUÉ SE PUNTÚA FACTURA POR FACTURA
-------------------------------------
Predecir el CONJUNTO es combinatorio y se queda sin ejemplos. Predecir factura
por factura ("¿está este depósito tocando esta factura?") da una fila por factura
abierta en vez de una por combinación: 5,356 filas en lugar de unos cientos. Y es
auditable — el operador ve por qué se propuso cada una.

Luego se ordena por puntaje y se acumula hasta cubrir el depósito.

DE DÓNDE SALEN LOS EJEMPLOS
---------------------------
De los casos FÁCILES. Los 1,612 depósitos que el solver resolvió exacto son
datos etiquetados gratis: enseñan qué forma tiene una asignación correcta. El
modelo aprende de ellos y se evalúa sobre los difíciles, que es donde hace falta.

En producción no hace falta ese rodeo: Integratel tiene años de FACTURA_AFECTADA.

CONTRA QUÉ SE COMPARA
---------------------
Contra la heurística que corre hoy, sobre los mismos casos y con separación
temporal (entrena junio, evalúa julio). El baseline medido es:

    pago parcial   68.9%   (propone la factura que vence más cerca)
    investigar      0.0%   (hoy no propone nada: el caso llega en blanco)

CÓMO SE USA
-----------
    python asignador.py                 entrena, mide contra la heurística y guarda
    python asignador.py --datos /ruta   lo mismo sobre otros CSV

En producción se consulta con `proponer()`. Si no hay artefacto entrenado,
devuelve el orden heurístico: el sistema nunca depende de que el modelo exista.
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

import backtest
import datos
import solver

ARTEFACTO = Path(__file__).parent / "asignador.joblib"
MES_ENTRENAMIENTO = 6
MES_EVALUACION = 7

CARACTERISTICAS = [
    # relación de importes: la señal más directa de si el depósito toca esta factura
    "ratio_saldo_deposito", "cabe_entera", "sobrante_relativo", "log_saldo",
    # tiempo: contra qué estaba pagando el cliente
    "dias_vto", "abs_dias_vto", "dias_desde_emision",
    "rank_vto", "rank_antiguedad",
    # contexto de la cartera del cliente en ese momento
    "n_abiertas", "deposito_sobre_cartera", "saldo_sobre_cartera",
    "es_la_mayor", "es_la_menor", "acumulado_fifo",
    # estado de la factura
    "parcialmente_pagada",
]


def _filas_del_deposito(abiertas, deposito_centimos, fecha_pago):
    """Una fila por factura abierta. Solo información disponible al decidir.

    `abiertas` viene de backtest.candidatas_abiertas, que ya trae el SALDO (no el
    total) y solo cuenta pagos estrictamente anteriores a esta fecha.
    """
    if not abiertas or deposito_centimos <= 0:
        return []

    cartera = sum(c["centimos"] for c in abiertas)
    orden_vto = sorted(range(len(abiertas)), key=lambda i: (
        abs((abiertas[i]["fecha_vto"] - fecha_pago).days)
        if abiertas[i]["fecha_vto"] is not None else 10**6))
    orden_fifo = sorted(range(len(abiertas)), key=lambda i: abiertas[i]["fecha_emision"])

    rank_vto = {idx: r for r, idx in enumerate(orden_vto)}
    rank_fifo = {idx: r for r, idx in enumerate(orden_fifo)}

    # Suma acumulada en orden FIFO: captura "el depósito alcanza para las
    # primeras k facturas más antiguas", que es como paga buena parte de la gente.
    acumulado, acum = {}, 0
    for i in orden_fifo:
        acum += abiertas[i]["centimos"]
        acumulado[i] = acum

    mayor = max(c["centimos"] for c in abiertas)
    menor = min(c["centimos"] for c in abiertas)

    filas = []
    for i, c in enumerate(abiertas):
        saldo = c["centimos"]
        vto = ((c["fecha_vto"] - fecha_pago).days
               if c["fecha_vto"] is not None else 999)
        filas.append({
            "factura": c["factura"],
            "ratio_saldo_deposito": saldo / deposito_centimos,
            "cabe_entera": int(saldo <= deposito_centimos),
            "sobrante_relativo": (deposito_centimos - saldo) / deposito_centimos,
            "log_saldo": float(np.log1p(saldo / 100)),
            "dias_vto": float(vto),
            "abs_dias_vto": float(abs(vto)),
            "dias_desde_emision": float((fecha_pago - c["fecha_emision"]).days),
            "rank_vto": rank_vto[i],
            "rank_antiguedad": rank_fifo[i],
            "n_abiertas": len(abiertas),
            "deposito_sobre_cartera": deposito_centimos / cartera if cartera else 0.0,
            "saldo_sobre_cartera": saldo / cartera if cartera else 0.0,
            "es_la_mayor": int(saldo == mayor),
            "es_la_menor": int(saldo == menor),
            "acumulado_fifo": acumulado[i] / deposito_centimos,
            "parcialmente_pagada": int(c.get("parcial", 0)),
        })
    return filas


def construir_dataset(ventana=backtest.VENTANA_ADELANTO_DIAS):
    """Una fila por (depósito, factura abierta). Etiqueta 1 = el pago la tocó.

    Se construye sobre TODOS los depósitos, no solo los difíciles: los que el
    solver resuelve exacto son los que enseñan qué forma tiene un acierto.
    """
    f, p = datos.facturas(), datos.pagos()
    por_factura, fx_cliente, pagos_fx = backtest.construir_indices(f, p)
    conocidas = set(por_factura)
    tol = solver.a_centimos(0.00)

    filas = []
    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        verdad = set(grupo.FACTURA_AFECTADA)
        if not verdad <= conocidas:
            continue  # toca facturas fuera del dataset: no se puede etiquetar

        abiertas = backtest.candidatas_abiertas(cliente, fecha, por_factura,
                                                fx_cliente, pagos_fx, ventana)
        if not abiertas:
            continue
        # Marcar cuáles venían ya parcialmente pagadas (saldo < total original)
        for c in abiertas:
            c["parcial"] = int(c["centimos"] < por_factura[c["factura"]]["centimos"])

        deposito = solver.a_centimos(grupo.monto.sum())
        soluciones, _ = solver.resolver(abiertas, deposito, tolerancia_centimos=tol)

        # Cómo lo clasificaría el motor de hoy: define sobre qué casos se evalúa.
        if soluciones:
            cola = "AUTO" if len(soluciones) == 1 else "CONFIRMAR"
        else:
            cola = ("HIPOTESIS" if any(c["centimos"] > deposito for c in abiertas)
                    else "INVESTIGAR")

        alcanzable = verdad <= {c["factura"] for c in abiertas}
        for fila in _filas_del_deposito(abiertas, deposito, fecha):
            fila.update({
                "evento": f"{cliente}|{fecha:%Y%m%d}",
                "mes": fecha.month,
                "cola": cola,
                "alcanzable": int(alcanzable),
                "toca": int(fila["factura"] in verdad),
            })
            filas.append(fila)

    return pd.DataFrame(filas)


def _entrenar(df):
    m = GradientBoostingClassifier(n_estimators=200, max_depth=3,
                                   learning_rate=0.06, random_state=0)
    m.fit(df[CARACTERISTICAS], df.toca)
    return m


def _heuristica_top1(g):
    """Lo que el operador recibe HOY: la factura que vence más cerca del pago.

    Solo propone cuando alguna factura ABSORBE el depósito (cola HIPOTESIS); si
    ninguna lo hace, hoy el caso llega en blanco al operador.
    """
    absorben = g[g.cabe_entera == 0]      # saldo > depósito: puede absorberlo
    if absorben.empty:
        return None
    return absorben.loc[absorben.abs_dias_vto.idxmin()]


def _regla_simple_top1(g):
    """El rival justo: la factura que vence más cerca, sin exigir que absorba.

    Medir contra lo que el sistema hace hoy exagera la ganancia, porque hoy la
    cola INVESTIGAR no propone nada y puntúa 0 por ausencia, no por error. Esta
    regla de una línea es lo que cualquiera escribiría en diez minutos, y es
    contra ella que el modelo tiene que justificarse.
    """
    return g.loc[g.abs_dias_vto.idxmin()]


def evaluar(modelo, evalua):
    """Top-1 del modelo contra top-1 de la heurística, por cola, mismos eventos."""
    evalua = evalua.copy()
    evalua["puntaje"] = modelo.predict_proba(evalua[CARACTERISTICAS])[:, 1]

    filas = []
    for ev, g in evalua.groupby("evento"):
        if not g.alcanzable.iloc[0] or not g.toca.any():
            continue  # la verdad no está entre las abiertas: nadie puede acertar
        mejor = g.loc[g.puntaje.idxmax()]
        heur = _heuristica_top1(g)

        # Propuesta de conjunto: ordenar por puntaje y acumular hasta cubrir el
        # depósito. `acumulado_fifo` está en unidades de depósito, así que el
        # saldo relativo de cada factura es ratio_saldo_deposito.
        orden = g.sort_values("puntaje", ascending=False)
        acum, elegidas = 0.0, []
        for r in orden.itertuples():
            if acum >= 0.999:
                break
            elegidas.append(r.factura)
            acum += r.ratio_saldo_deposito
        reales = set(g[g.toca == 1].factura)
        propuestas = set(elegidas)

        filas.append({
            "evento": ev,
            "cola": g.cola.iloc[0],
            "n_abiertas": len(g),
            # Un solo candidato: acertar no tiene mérito. Se reportan aparte.
            "trivial": int(len(g) == 1),
            "modelo_top1": int(mejor.toca),
            "heuristica_top1": int(heur.toca) if heur is not None else 0,
            "heuristica_propone": int(heur is not None),
            "regla_simple_top1": int(_regla_simple_top1(g).toca),
            "modelo_top2": int(g.nlargest(2, "puntaje").toca.any()),
            "conjunto_precision": len(propuestas & reales) / max(len(propuestas), 1),
            "conjunto_recall": len(propuestas & reales) / max(len(reales), 1),
        })
    return pd.DataFrame(filas)


# --------------------------------------------------------------- API de producción
def cargar():
    """Devuelve (modelo, metadatos) o (None, None) si no se ha entrenado."""
    if not ARTEFACTO.exists():
        return None, None
    p = joblib.load(ARTEFACTO)
    return p["modelo"], p["meta"]


MINIMO_PROPUESTAS = 3
MAXIMO_PROPUESTAS = 12


def proponer(abiertas, deposito_centimos, fecha_pago, modelo=None):
    """Ordena las facturas abiertas por probabilidad de estar recibiendo el pago.

    CUÁNTAS DEVUELVE, Y POR QUÉ NO UN NÚMERO FIJO
    ---------------------------------------------
    Un tope fijo de 3 rompe en los depósitos grandes: uno de S/ 7,950 contra 24
    facturas abiertas devolvía tres de S/ 110 —cada una correcta por separado, y
    juntas un 4% del monto—. El operador no puede hacer nada con eso.

    Así que se acumula en orden de puntaje HASTA CUBRIR el depósito, con un
    mínimo de 3 para dar contexto y un máximo de 12 para que la pantalla siga
    siendo legible. Cada entrada trae `acumulado`, que es lo que deja ver de un
    vistazo si la propuesta explica el monto o se queda corta.

    ARRANQUE EN FRÍO: sin artefacto entrenado devuelve el orden heurístico
    (vencimiento más cercano) con puntaje None. El sistema funciona el día uno.
    """
    filas = _filas_del_deposito(abiertas, deposito_centimos, fecha_pago)
    if not filas:
        return []

    if modelo is None:
        modelo, _ = cargar()

    if modelo is None:
        orden = sorted(range(len(filas)), key=lambda i: filas[i]["abs_dias_vto"])
        puntajes = [None] * len(filas)
    else:
        prob = modelo.predict_proba(pd.DataFrame(filas)[CARACTERISTICAS])[:, 1]
        orden = list(np.argsort(-prob))
        puntajes = [round(float(x), 3) for x in prob]

    salida, acumulado = [], 0
    for i in orden:
        if len(salida) >= MINIMO_PROPUESTAS and (acumulado >= deposito_centimos
                                                 or len(salida) >= MAXIMO_PROPUESTAS):
            break
        centimos = int(round(filas[i]["ratio_saldo_deposito"] * deposito_centimos))
        acumulado += centimos
        salida.append({
            "factura": filas[i]["factura"],
            "importe": round(centimos / 100, 2),
            "puntaje": puntajes[i],
            "acumulado": round(acumulado / 100, 2),
        })
    return salida


# ------------------------------------------------------------------------- informe
def _bloque(res, titulo, colas):
    sub = res[res.cola.isin(colas)]
    if sub.empty:
        return None
    return {
        "titulo": titulo,
        "casos": len(sub),
        "heuristica": sub.heuristica_top1.mean(),
        "regla_simple": sub.regla_simple_top1.mean(),
        "modelo": sub.modelo_top1.mean(),
        "modelo_top2": sub.modelo_top2.mean(),
        "sin_propuesta_hoy": int((~sub.heuristica_propone.astype(bool)).sum()),
    }


def main():
    ap = argparse.ArgumentParser(description="Asignador aprendido para los casos sin calce exacto")
    ap.add_argument("--datos", help="carpeta con los CSV (por defecto, los del sistema)")
    args = ap.parse_args()

    if args.datos:
        import contrato
        contrato.RAIZ = Path(args.datos)
        print(f"Usando los datos de {args.datos}\n")

    print("Construyendo el conjunto de entrenamiento (una fila por factura abierta)...")
    df = construir_dataset()
    entrena = df[df.mes == MES_ENTRENAMIENTO]
    evalua = df[df.mes == MES_EVALUACION]

    print(f"  {len(df):,} filas · {df.evento.nunique():,} depósitos · "
          f"{df.toca.mean():.1%} de las filas son la factura correcta")
    print(f"  entrena junio: {entrena.evento.nunique():,} depósitos · "
          f"evalúa julio: {evalua.evento.nunique():,}")

    if entrena.evento.nunique() < 50 or evalua.evento.nunique() < 50:
        print("\n  Muy pocos depósitos para concluir. El artefacto se guarda igual.")

    modelo = _entrenar(entrena)
    res = evaluar(modelo, evalua)

    print("\n" + "=" * 78)
    print("¿EL MODELO RESUELVE LO QUE EL SOLVER NO?   ·  julio, verdad escondida")
    print("=" * 78)
    print("  Acierto top-1: la factura mejor puntuada es una de las que el pago tocó.")
    print("  'hoy' = lo que recibe el operador · 'regla' = elegir la que vence más cerca\n")
    print(f"  {'':<26}{'casos':>7}{'hoy':>8}{'regla':>8}{'modelo':>9}{'top-2':>8}")
    print("  " + "-" * 66)

    bloques = [_bloque(res, "Pago parcial", ["HIPOTESIS"]),
               _bloque(res, "Investigar", ["INVESTIGAR"]),
               _bloque(res, "LOS DIFÍCILES (juntos)", ["HIPOTESIS", "INVESTIGAR"]),
               _bloque(res, "Elegir entre opciones", ["CONFIRMAR"])]
    for b in [x for x in bloques if x]:
        print(f"  {b['titulo']:<26}{b['casos']:>7}{b['heuristica']:>7.1%}"
              f"{b['regla_simple']:>8.1%}{b['modelo']:>9.1%}{b['modelo_top2']:>8.1%}")

    dificiles = res[res.cola.isin(["HIPOTESIS", "INVESTIGAR"])]
    delta = 0.0
    if len(dificiles):
        # La comparación que vale es contra la regla simple: medir contra 'hoy'
        # exagera, porque INVESTIGAR puntúa 0 por no proponer nada, no por errar.
        delta = dificiles.modelo_top1.mean() - dificiles.regla_simple_top1.mean()
        nt = dificiles[~dificiles.trivial.astype(bool)]
        blanco = dificiles[~dificiles.heuristica_propone.astype(bool)]

        print("\n  " + "-" * 66)
        print(f"  Contra la regla simple: {delta:+.1%} "
              f"({int(dificiles.modelo_top1.sum() - dificiles.regla_simple_top1.sum()):+d} casos)")
        if len(nt):
            print(f"  Excluyendo los {int(dificiles.trivial.sum())} casos con UNA sola factura abierta "
                  f"(acertar no tiene mérito):")
            print(f"     {len(nt)} casos · regla {nt.regla_simple_top1.mean():.1%} · "
                  f"modelo {nt.modelo_top1.mean():.1%}")
        if len(blanco):
            print(f"  De los {len(blanco)} que hoy llegan SIN propuesta, el modelo acierta "
                  f"{blanco.modelo_top1.mean():.1%}")
        print(f"  Conjunto propuesto — precisión {dificiles.conjunto_precision.mean():.1%} · "
              f"cobertura {dificiles.conjunto_recall.mean():.1%}")

    # ----------------------------------------------------------------- veredicto
    print("\n" + "-" * 78)
    if delta > 0.05:
        print("  SIRVE. Supera a la regla simple por margen amplio en los casos que el")
        print("  solver no resuelve. Convierte investigación en confirmación.")
    elif delta > 0:
        print("  MEJORA LEVE. Supera a la regla simple pero por poco sobre estos datos.")
        print("  Vale como modo sombra, no para decidir solo todavía.")
    else:
        print("  NO SUPERA a una regla de una línea. Se entrega el mecanismo entrenado y")
        print("  medido; con historial real de varios años cambia la curva.")
    print("-" * 78)

    print("\n  Qué pesa en su decisión:")
    for nombre, peso in sorted(zip(CARACTERISTICAS, modelo.feature_importances_),
                               key=lambda t: -t[1])[:6]:
        print(f"    {nombre:<24} {peso:.3f}  {'█' * int(peso * 50)}")

    # Artefacto final: reentrenado con todo lo disponible, no solo con junio.
    final = _entrenar(df)
    meta = {
        "filas": int(len(df)),
        "depositos": int(df.evento.nunique()),
        "caracteristicas": CARACTERISTICAS,
        "evaluacion": {b["titulo"]: {"casos": b["casos"],
                                     "hoy": round(b["heuristica"], 4),
                                     "regla_simple": round(b["regla_simple"], 4),
                                     "modelo": round(b["modelo"], 4)}
                       for b in bloques if b},
    }
    joblib.dump({"modelo": final, "meta": meta}, ARTEFACTO)
    print(f"\n  Artefacto guardado: {ARTEFACTO.name} "
          f"({ARTEFACTO.stat().st_size / 1024:.0f} KB)")
    print(f"  Reentrenar con datos propios:  python asignador.py --datos /ruta/a/los/csv")


if __name__ == "__main__":
    main()
