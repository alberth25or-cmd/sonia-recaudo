"""Muestreo de auditoría sobre la banda automática.

EL PROBLEMA QUE RESUELVE
------------------------
1,612 depósitos se aplican solos y nadie los mira. La pregunta que hace un
contralor es "¿cómo saben que no se están equivocando?". Sin una respuesta, la
banda automática no se aprueba, por buena que sea la medición de laboratorio.

QUÉ PUEDE Y QUÉ NO PUEDE ESTE CONTROL
-------------------------------------
Muestrear 2% (unos 32 casos) NO mide una tasa de error del 0.06%: con 32
observaciones esperarías 0.02 errores. Eso no es un instrumento de medición.

Lo que sí hace es detectar una REGRESIÓN. Si algo se rompe —cambia un formato de
fecha, se corrompe el maestro de facturas, alguien toca la tolerancia— la tasa
salta a varios puntos y la muestra lo cachea. Es un canario, no una balanza.
La tabla de poder de detección está abajo y se imprime en el informe, para que
nadie lo confunda con una garantía.

    python auditoria.py
"""

from pathlib import Path

import pandas as pd

PORCENTAJE = 0.02
UMBRAL_ALERTA = 0.02     # más de 2% de error en la muestra -> parar y revisar
REGISTRO = Path(__file__).parent / "auditorias.csv"


def muestra(decisiones, periodo, porcentaje=PORCENTAJE):
    """Muestra aleatoria y REPRODUCIBLE de la banda automática.

    La semilla sale del periodo, así que auditar la misma semana dos veces
    devuelve los mismos casos: sin eso, la auditoría no es verificable.
    """
    auto = decisiones[decisiones.cola == "AUTO"]
    n = max(1, round(len(auto) * porcentaje))
    semilla = abs(hash(str(periodo))) % (2**31)
    return auto.sample(n=min(n, len(auto)), random_state=semilla)


def poder_de_deteccion(n):
    """Probabilidad de ver al menos un error en la muestra, según la tasa real."""
    return [(p, 1 - (1 - p) ** n) for p in (0.0006, 0.01, 0.02, 0.05, 0.10)]


def evaluar(n_revisados, n_errores):
    """Lectura del resultado de una tanda de auditoría."""
    if not n_revisados:
        return "pendiente", "Sin casos revisados todavía."
    tasa = n_errores / n_revisados
    if n_errores == 0:
        return "ok", (f"{n_revisados} casos revisados sin errores. Consistente con la "
                      f"tasa esperada; no la confirma (ver poder de detección).")
    if tasa <= UMBRAL_ALERTA:
        return "atencion", (f"{n_errores} error(es) en {n_revisados} casos ({tasa:.1%}). "
                            f"Dentro del umbral, pero conviene revisar cuáles.")
    return "alerta", (f"{n_errores} errores en {n_revisados} casos ({tasa:.1%}) — por encima "
                      f"del {UMBRAL_ALERTA:.0%}. Parar la aplicación automática y revisar "
                      f"qué cambió en los datos o en la configuración.")


def registrar_tanda(periodo, n_revisados, n_errores, ruta=REGISTRO):
    """Guarda el resultado para poder ver la tendencia entre periodos."""
    fila = pd.DataFrame([{"periodo": periodo, "revisados": n_revisados,
                          "errores": n_errores,
                          "tasa": round(n_errores / n_revisados, 4) if n_revisados else None}])
    if ruta.exists():
        previo = pd.read_csv(ruta)
        fila = pd.concat([previo[previo.periodo != periodo], fila], ignore_index=True)
    fila.to_csv(ruta, index=False)
    return fila


def historial(ruta=REGISTRO):
    return pd.read_csv(ruta) if ruta.exists() else pd.DataFrame(
        columns=["periodo", "revisados", "errores", "tasa"])


def main():
    import datos
    from agentes import recaudo

    decisiones = recaudo.procesar(datos.facturas(), datos.pagos())
    auto = decisiones[decisiones.cola == "AUTO"]
    m = muestra(decisiones, periodo="2026-S33")

    print("=" * 72)
    print("MUESTREO DE AUDITORÍA  ·  control sobre la banda automática")
    print("=" * 72)
    print(f"  Aplicados sin revisión : {len(auto):,}")
    print(f"  Muestra ({PORCENTAJE:.0%})          : {len(m)} casos "
          f"· {len(m) * 20 / 60:.0f} min de trabajo")
    print(f"  Monto muestreado       : S/ {m.monto.sum():,.2f}")

    print(f"\n  Qué puede detectar esta muestra de {len(m)} casos:")
    print(f"    {'tasa de error real':<22} {'probabilidad de detectarla'}")
    for p, poder in poder_de_deteccion(len(m)):
        barra = "█" * int(poder * 34)
        etiqueta = "← la esperada" if p < 0.001 else ""
        print(f"    {p:>8.2%}{'':<14} {poder:>6.0%}  {barra} {etiqueta}")

    print(f"\n  Sirve para cachear que algo se rompió (≥5% se detecta 4 de cada 5 veces),")
    print(f"  no para confirmar la tasa base. Eso lo hace backtest.py sobre el ground truth.")

    print(f"\n  Casos de la muestra (los primeros 5):")
    for c in m.head(5).itertuples():
        print(f"    {c.cliente}  {c.fecha:%d/%m/%Y}  S/ {c.monto:>10,.2f}  "
              f"-> {len(c.facturas_propuestas)} factura(s)")
    print("=" * 72)


if __name__ == "__main__":
    main()
