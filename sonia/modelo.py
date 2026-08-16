"""Modelo entrenado — el artefacto que Integratel puede reentrenar con sus datos.

QUÉ HACE, Y POR QUÉ ESTO Y NO OTRA COSA
---------------------------------------
En aprendizaje.py medimos si un modelo elegía mejor que la heurística entre
combinaciones ambiguas: empató (67.5% ambos). Reemplazar una regla que ya
funciona por un modelo que iguala no aporta nada.

Así que aquí el modelo hace un trabajo distinto, donde la heurística no llega:
decidir CUÁNDO ESTÁ LO BASTANTE SEGURO como para aplicar el caso sin humano.

La heurística ordena pero no sabe cuánto confía. El modelo sí devuelve una
probabilidad, y el margen entre la primera y la segunda opción es una señal de
certeza. Si ese margen es amplio, el caso puede salir de la cola humana.

Eso sube el STP en vez de disputarle el puesto a la regla.

CÓMO SE USA
-----------
    python modelo.py                    entrena, mide y guarda el artefacto
    python modelo.py --datos /ruta      lo mismo sobre otros CSV

El artefacto queda en modelo_recaudo.joblib. En producción se recarga con
`cargar()` y se consulta con `margen()`; si no existe el archivo, el sistema
sigue funcionando solo con la heurística.
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

import aprendizaje
import backtest
import datos
import solver

ARTEFACTO = Path(__file__).parent / "modelo_recaudo.joblib"
UMBRALES = [0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


def _entrenar(entrena):
    m = GradientBoostingClassifier(n_estimators=120, max_depth=3,
                                   learning_rate=0.08, random_state=0)
    m.fit(entrena[aprendizaje.CARACTERISTICAS], entrena.correcta)
    return m


def evaluar_umbrales(modelo, evalua):
    """Para cada umbral de margen: cuántos casos se auto-aplicarían y con qué acierto.

    El margen es la diferencia entre la probabilidad de la mejor combinación y la
    de la segunda. Un margen amplio significa que el modelo no duda.
    """
    evalua = evalua.copy()
    evalua["puntaje"] = modelo.predict_proba(evalua[aprendizaje.CARACTERISTICAS])[:, 1]

    eventos = []
    for ev, g in evalua.groupby("evento"):
        g = g.sort_values("puntaje", ascending=False)
        top = g.iloc[0]
        segundo = float(g.iloc[1].puntaje) if len(g) > 1 else 0.0
        heur = g.loc[g.posicion_heuristica.idxmin()]
        eventos.append({
            "evento": ev,
            "margen": float(top.puntaje) - segundo,
            "modelo_acierta": int(top.correcta),
            "heuristica_acierta": int(heur.correcta),
            "coinciden": int(top.name == heur.name),
        })
    ev = pd.DataFrame(eventos)

    filas = []
    for u in UMBRALES:
        seguros = ev[ev.margen >= u]
        filas.append({
            "umbral": u,
            "auto_aplicables": len(seguros),
            "pct_de_la_cola": len(seguros) / len(ev) if len(ev) else 0,
            "acierto_en_esos": seguros.modelo_acierta.mean() if len(seguros) else float("nan"),
            "errores": int((1 - seguros.modelo_acierta).sum()) if len(seguros) else 0,
        })
    return ev, pd.DataFrame(filas)


def cargar():
    """Devuelve (modelo, metadatos) o (None, None) si no se ha entrenado."""
    if not ARTEFACTO.exists():
        return None, None
    p = joblib.load(ARTEFACTO)
    return p["modelo"], p["meta"]


def margen(combinaciones, por_factura, fecha_pago, n_abiertas, modelo=None):
    """Margen de confianza del modelo entre la mejor combinación y la segunda.

    Devuelve (indice_mejor, margen) o (0, None) si no hay modelo entrenado.
    """
    if modelo is None:
        modelo, _ = cargar()
    if modelo is None or len(combinaciones) < 2:
        return 0, None
    X = pd.DataFrame([aprendizaje._caracteristicas(c, por_factura, fecha_pago, n_abiertas)
                      for c in combinaciones])[aprendizaje.CARACTERISTICAS]
    prob = modelo.predict_proba(X)[:, 1]
    orden = np.argsort(-prob)
    return int(orden[0]), float(prob[orden[0]] - prob[orden[1]])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datos", help="carpeta con los CSV (por defecto, los del sistema)")
    args = ap.parse_args()

    if args.datos:
        import contrato
        contrato.RAIZ = Path(args.datos)
        print(f"Usando los datos de {args.datos}\n")

    print("Construyendo el conjunto de entrenamiento...")
    df = aprendizaje.construir_dataset()
    entrena = df[df.mes == aprendizaje.MES_ENTRENAMIENTO]
    evalua = df[df.mes == aprendizaje.MES_EVALUACION]

    print(f"  {df.evento.nunique():,} eventos ambiguos · {len(df):,} combinaciones candidatas")
    print(f"  entrena con {entrena.evento.nunique():,} eventos · "
          f"evalúa con {evalua.evento.nunique():,}")

    if entrena.evento.nunique() < 20 or evalua.evento.nunique() < 20:
        print("\n  Muy pocos eventos para concluir. El artefacto se guarda igual.")

    modelo = _entrenar(entrena)
    ev, curva = evaluar_umbrales(modelo, evalua)

    print("\n" + "=" * 76)
    print("¿CUÁNDO EL MODELO ESTÁ LO BASTANTE SEGURO PARA APLICAR SIN HUMANO?")
    print("=" * 76)
    print(f"  Sobre {len(ev)} eventos ambiguos de julio. El margen es la distancia entre")
    print(f"  la probabilidad de la mejor combinación y la de la segunda.\n")
    print(f"  {'margen ≥':>9} {'casos':>7} {'% de la cola':>13} {'acierto':>9} {'errores':>9}")
    print("  " + "-" * 52)
    for r in curva.itertuples():
        acierto = f"{r.acierto_en_esos:.1%}" if r.auto_aplicables else "—"
        print(f"  {r.umbral:>9.2f} {r.auto_aplicables:>7} {r.pct_de_la_cola:>12.1%} "
              f"{acierto:>9} {r.errores:>9}")

    base_h = ev.heuristica_acierta.mean()
    base_m = ev.modelo_acierta.mean()
    print(f"\n  Sin filtrar por confianza: heurística {base_h:.1%} · modelo {base_m:.1%}")
    print(f"  Coinciden en la misma respuesta: {ev.coinciden.mean():.1%} de los casos")

    # ------------------------------------------------------------------ veredicto
    print("\n" + "-" * 76)
    utiles = curva[(curva.acierto_en_esos >= 0.95) & (curva.auto_aplicables >= 5)]
    if len(utiles):
        mejor = utiles.iloc[0]
        print(f"  SIRVE. Con margen ≥ {mejor.umbral:.2f}, {int(mejor.auto_aplicables)} casos "
              f"({mejor.pct_de_la_cola:.0%} de la cola)")
        print(f"  se aplicarían solos con {mejor.acierto_en_esos:.0%} de acierto — "
              f"{int(mejor.errores)} error(es).")
        print(f"  Conectarlo sacaría esos casos del trabajo humano.")
    else:
        print("  NO ALCANZA sobre estos datos: en ningún umbral el modelo llega al 95% de")
        print("  acierto con una cantidad de casos que valga la pena. El artefacto queda")
        print("  entregado y entrenado; con historial real de varios años la curva cambia.")
    print("-" * 76)

    print("\n  Qué pesa en su decisión:")
    for nombre, peso in sorted(zip(aprendizaje.CARACTERISTICAS, modelo.feature_importances_),
                               key=lambda t: -t[1])[:5]:
        print(f"    {nombre:<20} {peso:.3f}  {'█' * int(peso * 55)}")

    # Artefacto final: se reentrena con TODO lo disponible, no solo con junio.
    final = _entrenar(df)
    meta = {"eventos_entrenamiento": int(df.evento.nunique()),
            "combinaciones": int(len(df)),
            "caracteristicas": aprendizaje.CARACTERISTICAS,
            "acierto_evaluacion": round(float(base_m), 4),
            "acierto_heuristica": round(float(base_h), 4),
            "curva_umbrales": json.loads(curva.to_json(orient="records"))}
    joblib.dump({"modelo": final, "meta": meta}, ARTEFACTO)
    print(f"\n  Artefacto guardado: {ARTEFACTO.name} "
          f"({ARTEFACTO.stat().st_size / 1024:.0f} KB)")
    print(f"  Reentrenar con datos propios:  python modelo.py --datos /ruta/a/los/csv")


if __name__ == "__main__":
    main()
