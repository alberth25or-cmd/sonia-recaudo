"""Por que hay facturas correctas que quedan fuera del universo de candidatas.

Solo hay dos causas posibles con el filtro actual:
  A) la factura se emitio DESPUES del pago  -> el pago precede a su factura
  B) la factura ya figuraba saldada antes    -> nuestro control de saldo la cierra
"""

from collections import defaultdict

import datos
import solver
from backtest import construir_indices


def main():
    f = datos.facturas()
    p = datos.pagos()
    por_factura, facturas_cliente, pagos_factura = construir_indices(f, p)
    conocidas = set(por_factura)

    causas = defaultdict(int)
    desfases = []
    cliente_distinto = 0

    for (cliente, fecha), grupo in p.groupby(["RAZON_SOCIAL", "fecha_pago"]):
        verdad = set(grupo.FACTURA_AFECTADA)
        if not verdad <= conocidas:
            continue
        for nro in verdad:
            info = por_factura[nro]
            if info["cliente"] != cliente:
                cliente_distinto += 1
                continue
            if info["fecha_emision"] > fecha:
                causas["emitida despues del pago"] += 1
                desfases.append((info["fecha_emision"] - fecha).days)
            else:
                pagado_antes = sum(c for fp, c in pagos_factura.get(nro, ()) if fp < fecha)
                if info["centimos"] - pagado_antes <= 0:
                    causas["ya figuraba saldada"] += 1
                else:
                    causas["OK - estaba disponible"] += 1

    total = sum(causas.values()) + cliente_distinto
    print("POR QUE UNA FACTURA CORRECTA NO ESTA ENTRE LAS CANDIDATAS")
    print(f"  (analizado sobre {total:,} vinculos pago->factura)\n")
    for causa, n in sorted(causas.items(), key=lambda kv: -kv[1]):
        print(f"  {causa:<28s} {n:>6,}  {n / total:>6.1%}")
    print(f"  {'la factura es de OTRO cliente':<28s} {cliente_distinto:>6,}  {cliente_distinto / total:>6.1%}")

    if desfases:
        ds = sorted(desfases)
        print(f"\n  Desfase cuando la factura se emite despues del pago (dias):")
        print(f"    min {ds[0]} · mediana {ds[len(ds) // 2]} · max {ds[-1]}")
        print(f"    dentro de 45 dias: {sum(1 for d in ds if d <= 45) / len(ds):.1%}")

    print("\n" + "=" * 58)
    print("CONTROL: pagos cuya FECHA_PAGO es anterior a FECHA_EMISION")
    pf = p.merge(f[["NRO_DOC_FISCAL", "fecha_emision"]],
                 left_on="FACTURA_AFECTADA", right_on="NRO_DOC_FISCAL", how="inner")
    antes = pf.fecha_pago < pf.fecha_emision
    print(f"  {antes.sum():,} de {len(pf):,} pagos ({antes.mean():.1%})")
    print(f"  monto involucrado: S/ {pf.monto[antes].sum():,.2f}")


if __name__ == "__main__":
    main()
