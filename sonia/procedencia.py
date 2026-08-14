"""¿Qué hallazgos son del negocio y cuáles del generador de datos?

Los CSV del reto son sintéticos. Eso no invalida la arquitectura ni el método de
medición, pero sí obliga a separar dos cosas antes de presentar:

  - patrones que reflejan cómo factura y cobra una telco -> transferibles
  - artefactos de cómo se generó el archivo             -> NO presentables

Ninguna de estas pruebas es concluyente por separado. Son señales: varias
apuntando en la misma dirección permiten decir "probablemente artefacto" con
honestidad, que es mejor que presentarlo como hallazgo de negocio y que un
jurado lo desmonte.
"""

import numpy as np
import pandas as pd

import datos

BENFORD = np.log10(1 + 1 / np.arange(1, 10))


def _primer_digito(serie):
    d = serie[serie > 0].astype(str).str.replace(r"[^1-9]", "", regex=True).str[:1]
    return d[d != ""].astype(int)


def prueba_benford(nombre, montos):
    """Importes financieros reales siguen Benford. Los generados uniformemente, no."""
    d = _primer_digito(montos)
    obs = d.value_counts(normalize=True).reindex(range(1, 10), fill_value=0).values
    desvio = np.abs(obs - BENFORD).sum()
    print(f"\n  {nombre}  (n={len(d):,})")
    print(f"    {'dígito':<8}" + "".join(f"{i:>6}" for i in range(1, 10)))
    print(f"    {'esperado':<8}" + "".join(f"{v:>6.1%}" for v in BENFORD))
    print(f"    {'observado':<8}" + "".join(f"{v:>6.1%}" for v in obs))
    veredicto = ("compatible con datos financieros reales" if desvio < 0.10 else
                 "desviación moderada" if desvio < 0.25 else
                 "NO sigue Benford — sugiere generación sintética")
    print(f"    desviación total: {desvio:.3f}  ->  {veredicto}")
    return desvio


def prueba_repeticion(nombre, montos):
    """Una telco factura miles de veces el mismo plan: los importes se repiten
    muchísimo. Importes muestreados al azar casi no se repiten."""
    unicos = montos.nunique() / len(montos)
    top = montos.value_counts().head(3)
    print(f"\n  {nombre}")
    print(f"    importes únicos: {unicos:.1%} de {len(montos):,} filas")
    print(f"    más frecuentes: " + " · ".join(f"S/ {v:,.2f} ({n}x)" for v, n in top.items()))
    print("    -> " + ("plausible: hay planes repetidos" if unicos < 0.7 else
                       "casi todos distintos — poco típico de facturación por plan"))
    return unicos


def prueba_desfase_pago_factura(f, p):
    """Si el generador muestreó fechas independientes, los pagos anticipados
    tendrán una distribución plana. Si es negocio, se concentran cerca de cero."""
    pf = p.merge(f[["NRO_DOC_FISCAL", "fecha_emision", "fecha_vto"]],
                 left_on="FACTURA_AFECTADA", right_on="NRO_DOC_FISCAL", how="inner")
    desfase = (pf.fecha_pago - pf.fecha_emision).dt.days
    antes = desfase[desfase < 0]

    print(f"\n  Desfase pago - emisión  (n={len(desfase):,})")
    print(f"    pagos anteriores a su factura: {len(antes):,} ({len(antes) / len(desfase):.1%})")
    if len(antes):
        dias = (-antes).sort_values()
        cuartiles = np.percentile(dias, [25, 50, 75])
        print(f"    días de anticipo — Q1={cuartiles[0]:.0f}  mediana={cuartiles[1]:.0f}  "
              f"Q3={cuartiles[2]:.0f}  max={dias.max()}")
        # Una distribución plana tiene media ~= mitad del rango
        plano = abs(dias.mean() - dias.max() / 2) / dias.max()
        print(f"    media={dias.mean():.1f} vs mitad del rango={dias.max() / 2:.1f}")
        print("    -> " + ("distribución PLANA: consistente con fechas muestreadas al azar"
                           if plano < 0.15 else
                           "concentrada cerca de cero: consistente con pago anticipado real"))
    return len(antes) / len(desfase)


def prueba_huerfanos(f, p):
    """¿Los pagos huérfanos apuntan a facturas con formato válido? Si el número
    es del mismo formato pero no existe, huele a generador desacoplado."""
    conocidas = set(f.NRO_DOC_FISCAL)
    huerfanos = p[~p.FACTURA_AFECTADA.isin(conocidas)]
    series_reales = set(f.NRO_DOC_FISCAL.str.split("-").str[0])
    series_huerfanas = huerfanos.FACTURA_AFECTADA.str.split("-").str[0]

    print(f"\n  Pagos huérfanos  (n={len(huerfanos):,}, S/ {huerfanos.monto.sum():,.2f})")
    print(f"    series usadas: {sorted(series_huerfanas.unique())}")
    coinciden = series_huerfanas.isin(series_reales).mean()
    print(f"    con serie válida del maestro: {coinciden:.0%}")
    print("    -> " + ("mismo formato pero factura inexistente: probable desacople "
                       "del generador, no cobro real sin factura" if coinciden > 0.9 else
                       "series ajenas: podría ser sistema externo"))
    return coinciden


def prueba_montos_redondos(p):
    """Transferencias reales tienen muchos montos redondos (100, 500, 1000).
    Importes calculados con IGV al céntimo, casi ninguno."""
    redondos = (p.monto % 10 == 0).mean()
    print(f"\n  Montos de pago terminados en cero: {redondos:.1%}")
    print("    -> " + ("hay transferencias por monto redondo, típico de pago manual"
                       if redondos > 0.05 else
                       "prácticamente ninguno: los pagos replican el importe facturado al céntimo"))
    return redondos


def main():
    f = datos.facturas()
    p = datos.pagos()

    print("=" * 76)
    print("PROCEDENCIA DE LOS HALLAZGOS  ·  los CSV del reto son sintéticos")
    print("=" * 76)

    print("\n--- Señales sobre los importes " + "-" * 42)
    prueba_benford("Facturas · CHARGE_TOTAL_AMOUNT", f.total)
    prueba_benford("Pagos · MONTO_PAGADO", p.monto)
    prueba_repeticion("Facturas", f.total)
    prueba_montos_redondos(p)

    print("\n--- Señales sobre las fechas " + "-" * 44)
    prueba_desfase_pago_factura(f, p)

    print("\n--- Señales sobre los huérfanos " + "-" * 41)
    prueba_huerfanos(f, p)

    print("\n" + "=" * 76)
    print("CÓMO LEER ESTO")
    print("=" * 76)
    print("""
  Los patrones que sí transfieren a producción son los ESTRUCTURALES: que un
  cliente pague varias facturas en un depósito, que pague de menos, que el
  monto no venga etiquetado. Esos existen en cualquier operación B2B y son los
  que la arquitectura resuelve.

  Lo que NO se debe presentar como hallazgo de negocio es cualquier patrón que
  estas pruebas marquen como artefacto. Decir "detectamos que el 5.8% de los
  pagos llega antes que la factura" sobre un dataset sintético es afirmar algo
  sobre el generador, no sobre Integratel.
""")


if __name__ == "__main__":
    main()
