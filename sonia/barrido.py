"""Calibracion de la ventana de suspenso y la tolerancia de calce.

Hay un trade-off real: ampliar la ventana mete en juego facturas que todavia no
se habian emitido (sube el techo alcanzable) pero agrega candidatas que generan
combinaciones espurias (baja la precision del ranking). Este barrido busca el
punto donde el neto es mejor, en vez de elegirlo a ojo.
"""

import backtest


def fila(ventana, tolerancia):
    stats, montos, amb, _ = backtest.ejecutar(ventana, tolerancia)
    ev = sum(stats[f"{e}:total"] - stats[f"{e}:huerfano"] for e in ("agrupado", "simple"))
    ok = stats["agrupado:acierto_top1"] + stats["simple:acierto_top1"]
    err = stats["agrupado:error"] + stats["simple:error"]
    sin = stats["agrupado:sin_solucion"] + stats["simple:sin_solucion"]
    fuera = stats["agrupado:fuera_de_universo"] + stats["simple:fuera_de_universo"]
    monto_ok = montos["agrupado:acierto_top1"] + montos["simple:acierto_top1"]
    ag_ev = stats["agrupado:total"] - stats["agrupado:huerfano"]
    return {
        "ventana": ventana,
        "tol": tolerancia,
        "acierto": ok / ev,
        "agrupado": stats["agrupado:acierto_top1"] / ag_ev,
        "error": err / ev,
        "sin_sol": sin / ev,
        "techo": (ev - fuera) / ev,
        "monto": monto_ok,
    }


def main():
    print("Calibrando... (cada corrida procesa los 3,548 pagos)\n")
    print(f"{'ventana':>7} {'tol S/':>7} | {'acierto':>8} {'agrupados':>10} {'error':>7} "
          f"{'sin sol':>8} {'techo':>7} | {'S/ conciliado':>14}")
    print("-" * 82)

    resultados = []
    for ventana in (0, 5, 10, 15, 20, 30, 45, 61):
        r = fila(ventana, 1.00)
        resultados.append(r)
        print(f"{r['ventana']:>7} {r['tol']:>7.2f} | {r['acierto']:>7.1%} {r['agrupado']:>10.1%} "
              f"{r['error']:>7.1%} {r['sin_sol']:>8.1%} {r['techo']:>7.1%} | {r['monto']:>14,.2f}")

    mejor = max(resultados, key=lambda r: r["acierto"])
    print(f"\n  -> mejor ventana: {mejor['ventana']} dias ({mejor['acierto']:.1%})")

    print(f"\n{'ventana':>7} {'tol S/':>7} | {'acierto':>8} {'agrupados':>10} {'error':>7} "
          f"{'sin sol':>8} {'techo':>7} | {'S/ conciliado':>14}")
    print("-" * 82)
    for tol in (0.00, 0.50, 1.00, 5.00, 20.00):
        r = fila(mejor["ventana"], tol)
        print(f"{r['ventana']:>7} {r['tol']:>7.2f} | {r['acierto']:>7.1%} {r['agrupado']:>10.1%} "
              f"{r['error']:>7.1%} {r['sin_sol']:>8.1%} {r['techo']:>7.1%} | {r['monto']:>14,.2f}")


if __name__ == "__main__":
    main()
