"""Realimentación — el sistema aprende de lo que decide el operador.

POR QUÉ ESTA PIEZA EXISTE
-------------------------
El asignador de asignador.py se entrena con historial: depósitos cuya factura
correcta ya se conoce. En una implantación nueva ese historial puede no existir
todavía, y sin él el modelo arranca en frío.

Pero hay una fuente que sí existe desde el día uno: **cada caso que el operador
resuelve en la torre es un ejemplo etiquetado**. Vio el depósito, vio las
facturas abiertas, y eligió. Eso es exactamente la señal que el modelo necesita.

Este módulo cierra ese círculo. El operador exporta sus decisiones desde la
pestaña Registro («Exportar para reentrenar») y aquí se convierten en filas de
entrenamiento.

MODO SOMBRA
-----------
Antes de reentrenar, este módulo responde la pregunta que importa:
**¿el modelo habría acertado?** Compara lo que propuso contra lo que el humano
eligió, decisión por decisión. Ese porcentaje de concordancia es lo que permite
decidir si el modelo ya se ganó el derecho a proponer con más peso — o a
auto-aplicar, si algún día llegara a ese nivel.

Se mide antes de aprender de esas mismas decisiones: medir después sería
preguntarle al modelo por lo que se acaba de estudiar.

UNA ADVERTENCIA HONESTA
-----------------------
El operador también se equivoca. Aprender de sus decisiones propaga sus errores
y sus sesgos: si acostumbra a imputar siempre a la factura más antigua, el
modelo aprenderá eso, sea correcto o no. Por eso la auditoría semanal de la
torre no es opcional — es lo que mantiene limpia la fuente de entrenamiento.

CÓMO SE USA
-----------
    python realimentacion.py realimentacion.csv
        informe: cuánto coincidía el modelo con el humano (modo sombra)

    python realimentacion.py realimentacion.csv --reentrenar
        además, reentrena el asignador incluyendo estas decisiones
"""

import argparse
from pathlib import Path

import joblib
import pandas as pd

import asignador
import backtest
import datos
import solver


def leer(ruta):
    """Lee el CSV exportado por la torre. Solo sirven las filas con facturas."""
    d = pd.read_csv(ruta, dtype=str).fillna("")
    faltan = {"id", "facturas"} - set(d.columns)
    if faltan:
        raise SystemExit(f"Al archivo le faltan columnas: {', '.join(sorted(faltan))}")
    d = d[d.facturas.str.strip() != ""].copy()
    d["elegidas"] = d.facturas.str.split("|").apply(lambda xs: {x.strip() for x in xs if x.strip()})
    # El id es la clave canónica: CLIENTE|AAAA-MM-DD
    partes = d.id.str.rsplit("|", n=1, expand=True)
    d["cliente"] = partes[0]
    d["dia"] = pd.to_datetime(partes[1], errors="coerce")
    return d[d.dia.notna()].reset_index(drop=True)


def _contexto(decisiones):
    """Reconstruye, para cada decisión, las facturas abiertas que se veían ese día."""
    f, p = datos.facturas(), datos.pagos()
    por_factura, fx_cliente, pagos_fx = backtest.construir_indices(f, p)

    depositos = (p.groupby(["RAZON_SOCIAL", "fecha_pago"]).monto.sum().to_dict())
    ctx = []
    for r in decisiones.itertuples():
        monto = depositos.get((r.cliente, r.dia))
        if monto is None:
            continue  # la decisión no corresponde a un depósito del período cargado
        abiertas = backtest.candidatas_abiertas(r.cliente, r.dia, por_factura,
                                                fx_cliente, pagos_fx,
                                                backtest.VENTANA_ADELANTO_DIAS)
        if not abiertas:
            continue
        for c in abiertas:
            c["parcial"] = int(c["centimos"] < por_factura[c["factura"]]["centimos"])
        ctx.append({"id": r.id, "cliente": r.cliente, "dia": r.dia,
                    "centimos": solver.a_centimos(monto), "abiertas": abiertas,
                    "elegidas": r.elegidas})
    return ctx


def concordancia(ctx, modelo):
    """Modo sombra: ¿el modelo proponía lo mismo que eligió el humano?"""
    filas = []
    for c in ctx:
        prop = asignador.proponer(c["abiertas"], c["centimos"], c["dia"], modelo=modelo)
        if not prop:
            continue
        propuestas = {p["factura"] for p in prop}
        filas.append({
            "id": c["id"],
            "coincide_top1": int(prop[0]["factura"] in c["elegidas"]),
            "elegida_en_propuesta": int(bool(c["elegidas"] & propuestas)),
            "confianza_top1": prop[0]["puntaje"],
            "n_elegidas": len(c["elegidas"]),
        })
    return pd.DataFrame(filas)


def filas_de_entrenamiento(ctx):
    """Convierte cada decisión humana en filas etiquetadas, como construir_dataset."""
    filas = []
    for c in ctx:
        for fila in asignador._filas_del_deposito(c["abiertas"], c["centimos"], c["dia"]):
            fila.update({"evento": c["id"], "mes": c["dia"].month,
                         "cola": "OPERADOR", "alcanzable": 1,
                         "toca": int(fila["factura"] in c["elegidas"])})
            filas.append(fila)
    return pd.DataFrame(filas)


def main():
    ap = argparse.ArgumentParser(description="Aprende de las decisiones del operador")
    ap.add_argument("archivo", help="CSV exportado desde la pestaña Registro de la torre")
    ap.add_argument("--reentrenar", action="store_true",
                    help="además de medir, reentrena el asignador incluyendo estas decisiones")
    args = ap.parse_args()

    ruta = Path(args.archivo)
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo {ruta}")

    dec = leer(ruta)
    print(f"Decisiones con facturas asignadas: {len(dec)}")
    ctx = _contexto(dec)
    print(f"  con contexto reconstruible      : {len(ctx)}")
    if not ctx:
        raise SystemExit("Ninguna decisión corresponde a un depósito de los datos cargados.")

    modelo, meta = asignador.cargar()
    if modelo is None:
        print("\n  No hay asignador entrenado todavía: no hay nada que comparar.")
        print("  Ejecute primero  python asignador.py")
    else:
        conc = concordancia(ctx, modelo)
        print("\n" + "=" * 70)
        print("MODO SOMBRA  ·  ¿el modelo proponía lo que el humano eligió?")
        print("=" * 70)
        print(f"  Decisiones comparadas          : {len(conc)}")
        print(f"  El modelo acertó en su 1ª      : {conc.coincide_top1.mean():>7.1%}"
              f"   ({int(conc.coincide_top1.sum())} de {len(conc)})")
        print(f"  La elegida estaba en su lista  : {conc.elegida_en_propuesta.mean():>7.1%}")

        alta = conc[conc.confianza_top1 >= 0.90]
        if len(alta):
            print(f"\n  Cuando el modelo dijo estar seguro (confianza ≥ 90%):")
            print(f"    {len(alta)} decisiones · acertó {alta.coincide_top1.mean():.1%}")
        print("\n  " + "-" * 66)
        print("  Esto se mide ANTES de aprender de estas decisiones. Si la concordancia")
        print("  se sostiene sobre unos cientos de casos, el modelo se ganó el derecho a")
        print("  proponer con más peso. Si no, sigue proponiendo y el humano decidiendo.")

    if not args.reentrenar:
        print(f"\n  Para incorporarlas al modelo:  python realimentacion.py {ruta.name} --reentrenar")
        return

    # ------------------------------------------------------------------ reentrenar
    print("\n" + "=" * 70)
    print("REENTRENANDO con el historial + las decisiones del operador")
    print("=" * 70)
    base = asignador.construir_dataset()
    nuevas = filas_de_entrenamiento(ctx)
    # Las decisiones del operador reemplazan al historial en los casos repetidos:
    # son la corrección humana, y pesan más que lo que el sistema había supuesto.
    base = base[~base.evento.isin(set(nuevas.evento))]
    juntos = pd.concat([base, nuevas], ignore_index=True)

    print(f"  historial          : {base.evento.nunique():,} depósitos · {len(base):,} filas")
    print(f"  decisiones humanas : {nuevas.evento.nunique():,} depósitos · {len(nuevas):,} filas")

    modelo_nuevo = asignador._entrenar(juntos)
    meta = dict(meta or {})
    meta.update({"filas": int(len(juntos)), "depositos": int(juntos.evento.nunique()),
                 "caracteristicas": asignador.CARACTERISTICAS,
                 "decisiones_operador": int(nuevas.evento.nunique())})
    joblib.dump({"modelo": modelo_nuevo, "meta": meta}, asignador.ARTEFACTO)
    print(f"\n  Artefacto actualizado: {asignador.ARTEFACTO.name}")
    print(f"  Vuelva a generar la torre para que use el modelo nuevo:  python torre.py")


if __name__ == "__main__":
    main()
