"""Capa de aprendizaje — la pieza que la industria tiene y nosotros no teníamos.

QUÉ ES Y QUÉ NO ES
------------------
NO es un modelo entrenado listo para producción. Un modelo entrenado sobre el
dataset sintético del reto aprendería los artefactos del generador (ver
procedencia.py) y fallaría en producción de formas difíciles de detectar.

SÍ es la maquinaria completa: extracción de características, entrenamiento y
arnés de evaluación. Se entrega SIN entrenar; Integratel la entrena con sus
datos reales. Lo que aquí se demuestra es que el mecanismo funciona y cuánto
aporta frente a la heurística.

LO QUE NO SE PUEDE APRENDER CON ESTOS DATOS
-------------------------------------------
HighRadius aprende el comportamiento POR CLIENTE ("esta empresa paga por lote
los martes"). Aquí la mediana es 2 eventos por cliente y solo el 4% tiene 5 o
más: no hay historial. Así que este modelo aprende patrones GLOBALES —qué forma
tiene una combinación correcta— no perfiles individuales. Con datos reales de
varios años, las mismas características admiten el corte por cliente.

CÓMO SE EVALÚA
--------------
Separación TEMPORAL, no aleatoria: se entrena con los eventos de junio y se
evalúa con los de julio. Eso imita el despliegue —aprender del pasado, predecir
el futuro— y evita el optimismo de un split aleatorio.

    python aprendizaje.py
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

import backtest
import datos
import solver

TOLERANCIA = 1.00   # más holgada que en producción: genera más casos ambiguos para entrenar
MES_ENTRENAMIENTO = 6
MES_EVALUACION = 7

CARACTERISTICAS = [
    "n_facturas", "dias_vto_medio", "dias_vto_min", "dias_vto_max", "dispersion_vto",
    "antiguedad_media", "fraccion_abiertas", "misma_serie", "importe_medio", "rango_importe",
]


def _caracteristicas(combinacion, por_factura, fecha_pago, n_abiertas):
    """Solo información disponible al decidir. Nada que dependa de la respuesta."""
    vtos, emisiones, importes, series = [], [], [], set()
    for nro in combinacion:
        info = por_factura[nro]
        if info["fecha_vto"] is not None:
            vtos.append((info["fecha_vto"] - fecha_pago).days)
        emisiones.append((fecha_pago - info["fecha_emision"]).days)
        importes.append(info["centimos"] / 100)
        series.add(nro.split("-")[0])

    vtos = vtos or [999]
    return {
        "n_facturas": len(combinacion),
        "dias_vto_medio": float(np.mean(vtos)),
        "dias_vto_min": float(np.min(vtos)),
        "dias_vto_max": float(np.max(vtos)),
        "dispersion_vto": float(np.std(vtos)) if len(vtos) > 1 else 0.0,
        "antiguedad_media": float(np.mean(emisiones)),
        "fraccion_abiertas": len(combinacion) / max(n_abiertas, 1),
        "misma_serie": int(len(series) == 1),
        "importe_medio": float(np.mean(importes)),
        "rango_importe": float(np.max(importes) - np.min(importes)) if len(importes) > 1 else 0.0,
    }


def construir_dataset():
    """Una fila por combinación candidata. Etiqueta 1 = es la correcta."""
    f, p = datos.facturas(), datos.pagos()
    por_factura, fx_cliente, pagos_fx = backtest.construir_indices(f, p)
    conocidas = set(por_factura)
    tol = solver.a_centimos(TOLERANCIA)

    filas = []
    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        verdad = set(grupo.FACTURA_AFECTADA)
        if not verdad <= conocidas:
            continue
        cands = backtest.candidatas_abiertas(cliente, fecha, por_factura, fx_cliente,
                                             pagos_fx, backtest.VENTANA_ADELANTO_DIAS)
        sols, _ = solver.resolver(cands, solver.a_centimos(grupo.monto.sum()),
                                  tolerancia_centimos=tol)
        if len(sols) < 2:
            continue  # sin ambigüedad no hay nada que aprender a ordenar

        ordenadas = solver.ranking(sols, por_factura, fecha)
        for posicion, combo in enumerate(ordenadas):
            fila = _caracteristicas(combo, por_factura, fecha, len(cands))
            fila.update({
                "evento": f"{cliente}|{fecha:%Y%m%d}",
                "mes": fecha.month,
                "posicion_heuristica": posicion,
                "correcta": int(set(combo) == verdad),
            })
            filas.append(fila)

    return pd.DataFrame(filas)


def main():
    print("Construyendo el conjunto de entrenamiento...")
    df = construir_dataset()

    entrena = df[df.mes == MES_ENTRENAMIENTO]
    evalua = df[df.mes == MES_EVALUACION]
    ev_entrena = entrena.evento.nunique()
    ev_evalua = evalua.evento.nunique()

    print(f"\n  combinaciones candidatas : {len(df):,}")
    print(f"  eventos ambiguos         : {df.evento.nunique():,}")
    print(f"  entrenamiento (junio)    : {ev_entrena:,} eventos · {len(entrena):,} combinaciones")
    print(f"  evaluación (julio)       : {ev_evalua:,} eventos · {len(evalua):,} combinaciones")

    if ev_entrena < 20 or ev_evalua < 20:
        print("\n  Muy pocos eventos para un resultado con sentido. El pipeline queda")
        print("  construido y listo para datos reales, pero no se puede concluir nada aquí.")
        return

    modelo = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.08,
                                        random_state=0)
    modelo.fit(entrena[CARACTERISTICAS], entrena.correcta)

    evalua = evalua.copy()
    evalua["puntaje"] = modelo.predict_proba(evalua[CARACTERISTICAS])[:, 1]

    # Top-1 de cada estrategia sobre los MISMOS eventos de julio
    aciertos_modelo = aciertos_heuristica = 0
    for _, g in evalua.groupby("evento"):
        aciertos_modelo += int(g.loc[g.puntaje.idxmax(), "correcta"])
        aciertos_heuristica += int(g.loc[g.posicion_heuristica.idxmin(), "correcta"])

    print("\n" + "=" * 70)
    print("¿APRENDER SUPERA A LA HEURÍSTICA?  ·  entrenado en junio, evaluado en julio")
    print("=" * 70)
    print(f"  Eventos ambiguos de julio : {ev_evalua}")
    print(f"  Heurística determinista   : {aciertos_heuristica:>4}  "
          f"({aciertos_heuristica / ev_evalua:.1%})")
    print(f"  Modelo aprendido          : {aciertos_modelo:>4}  "
          f"({aciertos_modelo / ev_evalua:.1%})")
    delta = aciertos_modelo - aciertos_heuristica
    print(f"\n  Diferencia: {delta:+d} eventos ({delta / ev_evalua:+.1%})")

    print("\n  Qué pesa en la decisión del modelo:")
    for nombre, peso in sorted(zip(CARACTERISTICAS, modelo.feature_importances_),
                               key=lambda t: -t[1])[:5]:
        print(f"    {nombre:<20} {peso:.3f}  {'█' * int(peso * 60)}")

    print("\n" + "-" * 70)
    print("  El modelo NO se entrega entrenado: aprendió del generador sintético.")
    print("  Lo que se entrega es este pipeline, para entrenarlo con datos reales.")
    print("=" * 70)


if __name__ == "__main__":
    main()
