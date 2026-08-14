"""Agente de Cobranza — clasifica las comunicaciones entrantes de clientes.

Base: prototipo de Agentes 1551 (agente_cobranza.py).

La ficha dice que hoy "ningún buzón está centralizado, organizado ni respondido
automáticamente". Este agente lee cada mensaje, lo clasifica, y sobre todo
detecta los que confirman un pago — esos se le pasan a Recaudo para conciliar.
Ahí se cierra el ciclo entre dos agentes.

Dos modos, igual que el explicador: con ANTHROPIC_API_KEY usa Claude; sin ella
cae a reglas por palabra clave. La demo nunca depende de la red.
"""

import llm

CATEGORIAS = [
    "CONFIRMACION_PAGO",
    "RECLAMO_MONTO",
    "SOLICITUD_DOCUMENTO",
    "RECLAMO_SERVICIO",
    "OTRO",
]

_PALABRAS = {
    "CONFIRMACION_PAGO": ["voucher", "comprobante", "ya pagué", "ya cancelé", "realicé el pago",
                          "pago realizado", "transferencia", "depósito", "yape", "plin",
                          "hicimos el pago"],
    "RECLAMO_MONTO": ["no estoy de acuerdo", "monto cobrado", "cobro duplicado", "mal calculado",
                      "no coincide", "refacturación", "aumento", "dos veces"],
    "SOLICITUD_DOCUMENTO": ["reenv", "copia de", "enviar la factura", "necesito la factura",
                            "en pdf", "mandarme la última factura"],
    "RECLAMO_SERVICIO": ["corte", "suspendido", "suspensión", "sin servicio", "no funciona"],
}


def _por_reglas(texto):
    bajo = texto.lower()
    puntajes = {c: sum(1 for p in _PALABRAS.get(c, ()) if p in bajo) for c in CATEGORIAS}
    mejor = max(puntajes, key=puntajes.get)
    if puntajes[mejor] == 0:
        return "OTRO", 0.4
    return mejor, min(0.55 + puntajes[mejor] * 0.15, 0.9)


_SISTEMA = (
    "Clasificas correos de clientes B2B de telecomunicaciones en una sola "
    "categoría. Respondes ÚNICAMENTE con el número de la categoría, sin más texto."
)


def _por_modelo(asunto, cuerpo):
    opciones = "\n".join(f"{i}. {c}" for i, c in enumerate(CATEGORIAS, 1))
    idx = llm.elegir(
        _SISTEMA,
        f"Categorías:\n{opciones}\n\nAsunto: {asunto}\nCuerpo: {cuerpo}\n\nNúmero:",
        CATEGORIAS,
    )
    return (CATEGORIAS[idx], 0.9) if idx is not None else (None, 0)


def clasificar(correo):
    texto = f"{correo['asunto']} {correo['cuerpo']}"
    categoria, confianza = _por_modelo(correo["asunto"], correo["cuerpo"])
    motor = llm.etiqueta()
    if categoria is None:  # sin backend, o respuesta no válida
        categoria, confianza = _por_reglas(texto)
        motor = "reglas y plantillas"
    return {**correo, "categoria": categoria, "confianza": round(confianza, 2), "motor": motor}


def clasificar_lote(correos):
    return [clasificar(c) for c in correos]


def kpis(clasificados):
    from collections import Counter
    dist = Counter(c["categoria"] for c in clasificados)
    return {
        "correos_procesados": len(clasificados),
        "confirmaciones_de_pago": dist.get("CONFIRMACION_PAGO", 0),
        "distribucion": dict(dist),
        "motor": clasificados[0]["motor"] if clasificados else "—",
    }
