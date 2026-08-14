"""Solver determinista de asignacion de depositos a facturas.

El problema real de recaudo: llega un deposito de S/ X de un cliente que tiene N
facturas abiertas. Hay que decidir que subconjunto de facturas paga.

Eso es subset-sum, no es lenguaje natural. Se resuelve exacto y en milisegundos.
El LLM no debe tocar esta parte: debe entrar cuando el solver devuelve VARIAS
soluciones validas (ambiguedad real) o NINGUNA (hay que hipotetizar por que).

Todo se trabaja en centimos (int) para no arrastrar error de punto flotante.
"""

from bisect import bisect_left, bisect_right

# Tope de candidatas para la busqueda exhaustiva. Con 30 son 2^15 = 32,768
# combinaciones por mitad: instantaneo. Por encima se poda (ver podar()).
MAX_CANDIDATAS = 30


def a_centimos(x):
    return int(round(float(x) * 100))


def _sumas_de_subconjuntos(items):
    """Todas las sumas alcanzables. items: lista de (id, centimos).

    Devuelve lista ordenada de (suma, tupla_de_ids).
    """
    sumas = [(0, ())]
    for ident, cent in items:
        sumas += [(s + cent, ids + (ident,)) for s, ids in sumas]
    sumas.sort(key=lambda t: t[0])
    return sumas


def podar(candidatas, objetivo):
    """Si hay demasiadas candidatas, quedarse con las mas plausibles.

    Criterio: primero las que caben en el deposito (una factura mayor al deposito
    no puede ser parte de la solucion), y de esas las mas antiguas, que es la
    regla de imputacion mas comun en cobranza.
    """
    caben = [c for c in candidatas if c["centimos"] <= objetivo]
    caben.sort(key=lambda c: c["fecha_emision"])
    return caben[:MAX_CANDIDATAS]


def resolver(candidatas, deposito_centimos, tolerancia_centimos=0, max_soluciones=50):
    """Encuentra los subconjuntos de facturas que suman el deposito.

    candidatas: lista de dicts con 'factura', 'centimos', 'fecha_emision'.
    Devuelve (soluciones, podado) donde cada solucion es una tupla de nro de factura.
    """
    podado = False
    if len(candidatas) > MAX_CANDIDATAS:
        candidatas = podar(candidatas, deposito_centimos)
        podado = True

    if not candidatas:
        return [], podado

    items = [(c["factura"], c["centimos"]) for c in candidatas]
    mitad = len(items) // 2
    izq = _sumas_de_subconjuntos(items[:mitad])
    der = _sumas_de_subconjuntos(items[mitad:])

    claves_der = [s for s, _ in der]
    soluciones = []

    for suma_izq, ids_izq in izq:
        falta = deposito_centimos - suma_izq
        lo = bisect_left(claves_der, falta - tolerancia_centimos)
        hi = bisect_right(claves_der, falta + tolerancia_centimos)
        for k in range(lo, hi):
            _, ids_der = der[k]
            combinado = ids_izq + ids_der
            if combinado:  # el subconjunto vacio no es una asignacion
                soluciones.append(combinado)
                if len(soluciones) >= max_soluciones:
                    return soluciones, podado

    return soluciones, podado


def ranking(soluciones, por_factura, fecha_pago):
    """Ordena las soluciones candidatas por plausibilidad de negocio.

    Sin esto, 'hay 7 combinaciones validas' es inutil para el operador. Con esto,
    hay una propuesta y seis alternativas.

    La señal dominante es el vencimiento: la mediana de pago del reto cae 1 dia
    ANTES del vencimiento, asi que la combinacion correcta es casi siempre la que
    agrupa facturas que vencen cerca del dia en que entro la plata. Empatan pocas,
    y ahi desempata FIFO (imputar primero lo mas antiguo, lo estandar en cobranza).
    """
    def clave(sol):
        desvios = []
        for nro in sol:
            vto = por_factura[nro]["fecha_vto"]
            desvios.append(abs((vto - fecha_pago).days) if vto is not None else 999)
        cerca = sum(desvios) / len(desvios)
        antiguedad = min(por_factura[nro]["fecha_emision"] for nro in sol)
        return (round(cerca), len(sol), antiguedad)

    return sorted(soluciones, key=clave)
