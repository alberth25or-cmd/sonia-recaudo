"""STP — Straight-Through Processing, la métrica de la industria.

CONTEXTO
--------
Esto que construimos tiene nombre en la industria: cash application automation,
dentro de order-to-cash. HighRadius, SAP Cash Application, Sidetrade y Serrala
resuelven el mismo problema, y todos miden lo mismo: STP, el porcentaje de pagos
que se aplican solos, sin intervención humana.

Referencias públicas de la categoría (publicadas por los propios proveedores —
son material de marketing, no benchmarks auditados; citarlas como orden de
magnitud, no como cifra exacta):
    ~80%   piso de lo que entregan las herramientas líderes
    ~95%   clase mundial
     96%   L'Oreal con HighRadius

QUÉ NO ES STP
-------------
El 80.5% (2,709 de 3,364 facturas que calzan al centavo) NO es STP. Ese cálculo
agrupa los pagos por FACTURA_AFECTADA, que es la respuesta que hoy produce un
analista a mano. Mide la calidad del dato después del trabajo humano, no la
automatización. Usarlo como STP infla la línea base y hunde el argumento ante
cualquiera que conozca su propia operación.

STP aquí = depósitos que el motor aplica solo, sin que nadie los mire.
"""

import datos
from agentes import recaudo

PISO_INDUSTRIA = 80.0
CLASE_MUNDIAL = 95.0


def medir():
    decisiones = recaudo.procesar(datos.facturas(), datos.pagos())
    total = len(decisiones)
    n = decisiones.cola.value_counts()

    auto = int(n.get("AUTO", 0))
    confirmar = int(n.get("CONFIRMAR", 0))
    hipotesis = int(n.get("HIPOTESIS", 0))
    investigar = int(n.get("INVESTIGAR", 0))

    return {
        "depositos": total,
        "stp_actual": auto / total * 100,
        "monto_stp": float(decisiones[decisiones.cola == "AUTO"].monto.sum()),
        # Techos alcanzables si la capa agéntica resuelve cada cola sucesiva
        "techo_con_desambiguacion": (auto + confirmar) / total * 100,
        "techo_con_pagos_parciales": (auto + confirmar + hipotesis) / total * 100,
        "irreducible": investigar / total * 100,
        "colas": {"auto": auto, "confirmar": confirmar,
                  "hipotesis": hipotesis, "investigar": investigar},
    }


def escala(valor, ancho=44):
    """Barra de posicionamiento contra el piso y el estándar de la industria."""
    pos = int(valor / 100 * ancho)
    piso = int(PISO_INDUSTRIA / 100 * ancho)
    clase = int(CLASE_MUNDIAL / 100 * ancho)
    barra = ["·"] * ancho
    barra[piso] = "|"
    barra[clase] = "|"
    for i in range(min(pos, ancho)):
        barra[i] = "=" if barra[i] == "·" else "|"
    return "".join(barra)


def main():
    m = medir()

    print("=" * 74)
    print("STRAIGHT-THROUGH PROCESSING  ·  la métrica con que se mide esta categoría")
    print("=" * 74)
    print(f"\n  {m['depositos']:,} depósitos procesados sobre el dataset del reto (sintético)\n")

    print(f"  {'0%':<4}{'piso industria 80%':>42}{'':>4}{'clase mundial 95%':>0}")
    print(f"  {escala(m['stp_actual'])}")
    print(f"  ^ SON-IA hoy: {m['stp_actual']:.1f}%  ({m['colas']['auto']:,} depósitos · "
          f"S/ {m['monto_stp']:,.0f} aplicados sin que nadie los mire)\n")

    print("-" * 74)
    print("HACIA DÓNDE PUEDE SUBIR")
    print("-" * 74)
    print(f"  {m['stp_actual']:>5.1f}%   hoy — solo con el solver determinista, sin capa LLM activa")
    print(f"  {m['techo_con_desambiguacion']:>5.1f}%   si el agente desambigua los {m['colas']['confirmar']} casos "
          f"con varias combinaciones válidas")
    print(f"  {m['techo_con_pagos_parciales']:>5.1f}%   si además resuelve los {m['colas']['hipotesis']} pagos parciales")
    print(f"  {100 - m['irreducible']:>5.1f}%   techo con estos datos — los {m['colas']['investigar']} "
          f"restantes son depósitos")
    print(f"          huérfanos y moneda extranjera, irresolubles sin información externa\n")

    brecha = PISO_INDUSTRIA - m["stp_actual"]
    print("-" * 74)
    print("CÓMO SE DICE ESTO SIN EXAGERAR")
    print("-" * 74)
    if brecha > 0:
        print(f"  · Estamos a {brecha:.1f} puntos del piso de la industria, con el motor")
        print(f"    determinista solo. La capa agéntica todavía no está activada.")
    else:
        print(f"  · Ya superamos el piso de la industria ({PISO_INDUSTRIA:.0f}%).")
    print(f"  · El techo con estos datos es {100 - m['irreducible']:.1f}%: el estándar mundial de 95%")
    print(f"    exige resolver los huérfanos, y eso necesita el extracto bancario")
    print(f"    completo, que no viene en el dataset del reto.")
    print(f"  · NO decir '80.5%' como línea base: esa cifra ya incluye el trabajo")
    print(f"    manual que estamos reemplazando.")
    print(f"  · NO decir 'Integratel está en X%': el dataset es sintético. Lo medible")
    print(f"    es lo que ESTE motor logra sobre ESTOS datos, y que el método de")
    print(f"    medición es el correcto. Las cifras de la industria son publicaciones")
    print(f"    de los propios proveedores, no benchmarks auditados.")
    print("=" * 74)


if __name__ == "__main__":
    main()
