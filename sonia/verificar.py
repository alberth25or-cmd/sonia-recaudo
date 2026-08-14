"""Verifica contra los CSV las cifras que el documento de contexto da por buenas.

No confiamos en el documento: si vamos a pararnos frente al jurado con estos
numeros, tienen que salir de los datos delante de nosotros.
"""

import datos


def main():
    f = datos.facturas()
    p = datos.pagos()
    n = datos.notas_credito()
    c = datos.clientes()

    print("=== FILAS ===")
    for nombre, df in [("clientes", c), ("facturas", f), ("pagos", p), ("ncs", n)]:
        print(f"  {nombre:10s} {len(df):>6,}")

    print("\n=== TRAMPA DEL RUC ===")
    ruc_f = f.groupby("RAZON_SOCIAL").NUMERO_IDENTIFICACION_FISCAL.first()
    ruc_c = c.set_index("RAZON_SOCIAL").NUMERO_IDENTIFICACION_FISCAL
    comun = ruc_f.index.intersection(ruc_c.index)
    discrepan = (ruc_f[comun] != ruc_c[comun]).sum()
    print(f"  razones sociales en ambas tablas : {len(comun)}")
    print(f"  con RUC distinto                 : {discrepan}")
    print(f"  RUCs unicos en pagos / filas     : {p.NRO_IDENTIFICACION_FISCAL.nunique()} / {len(p)}")

    print("\n=== FECHAS ===")
    print(f"  facturas sin fecha_emision parseada : {f.fecha_emision.isna().sum()}")
    print(f"  facturas sin fecha_vto parseada     : {f.fecha_vto.isna().sum()}")
    print(f"  pagos sin fecha parseada            : {p.fecha_pago.isna().sum()}")
    print(f"  rango de pagos : {p.fecha_pago.min():%Y-%m-%d} a {p.fecha_pago.max():%Y-%m-%d}")

    print("\n=== CRUCE FACTURAS x PAGOS ===")
    pagado = p.groupby("FACTURA_AFECTADA").monto.sum()
    f["pagado"] = f.NRO_DOC_FISCAL.map(pagado).fillna(0.0)
    f["brecha"] = (f.total - f.pagado).round(2)

    sin_pago = (f.pagado == 0).sum()
    exacto = (f.brecha.abs() < 0.005).sum()
    parcial = (f.brecha > 0.005).sum() - sin_pago
    sobre = (f.brecha < -0.005).sum()
    print(f"  calce exacto        : {exacto:>5,}")
    print(f"  pago parcial        : {parcial:>5,}   brecha S/ {f.brecha[f.brecha > 0.005].sum() - f.brecha[f.pagado == 0].sum():,.0f}")
    print(f"  sobrepago           : {sobre:>5,}")
    print(f"  sin pago registrado : {sin_pago:>5,}")

    huerfanos = p[~p.FACTURA_AFECTADA.isin(set(f.NRO_DOC_FISCAL))]
    print(f"\n  PAGOS HUERFANOS (apuntan a factura desconocida)")
    print(f"    cantidad : {len(huerfanos):,}")
    print(f"    monto    : S/ {huerfanos.monto.sum():,.2f}")

    print("\n=== PAGOS AGRUPADOS (el 48% del dinero) ===")
    # un evento = un cliente pagando en un mismo dia
    ev = p.groupby(["RAZON_SOCIAL", "fecha_pago"]).agg(
        n_facturas=("FACTURA_AFECTADA", "nunique"),
        n_pagos=("monto", "size"),
        monto=("monto", "sum"),
    )
    agrupados = ev[ev.n_facturas > 1]
    print(f"  eventos totales (cliente-dia)  : {len(ev):,}")
    print(f"  eventos agrupados (>1 factura) : {len(agrupados):,}")
    print(f"  maximo de facturas en un evento: {ev.n_facturas.max()}")
    print(f"  monto en agrupados : S/ {agrupados.monto.sum():,.0f} de S/ {p.monto.sum():,.0f}"
          f"  ({agrupados.monto.sum() / p.monto.sum():.1%})")

    print("\n=== NOTAS DE CREDITO ===")
    print(f"  NCs que cruzan con una factura : {n.FACTURA_AFECTADA.isin(set(f.NRO_DOC_FISCAL)).sum()} / {len(n)}")

    print("\n=== MONEDA ===")
    print(f"  pagos en USD : {(p.MONEDA_FACTURA == 'USD').sum()}")


if __name__ == "__main__":
    main()
