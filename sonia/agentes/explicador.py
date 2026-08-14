"""Explicador — convierte una decisión del solver en lenguaje que el operador audita.

Base: prototipo de Agentes 1551 (explicador_llm.py), reconectado a la capa
intercambiable de llm.py (local / Claude / plantilla).

Aquí el LLM aporta de verdad: el solver ya decidió qué facturas y con qué
confianza; falta que un humano entienda la propuesta en cinco segundos y pueda
confirmarla sin abrir otro sistema.

El caso es la ÚNICA fuente de verdad del prompt. El modelo interpreta, no inventa.
"""

import llm

SISTEMA = (
    "Eres el Agente de Recaudo de Integratel (Movistar B2B). Escribes para un "
    "analista de cobranzas que debe confirmar o rechazar una propuesta en segundos.\n\n"
    "Reglas estrictas:\n"
    "- Máximo 2 frases. Español peruano, directo, sin saludos ni despedidas.\n"
    "- No repitas el monto ni la fecha en crudo: el analista ya los ve en pantalla. "
    "Di qué significan.\n"
    "- Si el motor no encontró calce, di qué conviene revisar primero.\n"
    "- No inventes montos, fechas ni números de factura que no estén en el caso."
)


def _plantilla(caso):
    cola = caso["cola"]
    if cola == "AUTO":
        return (f"Calza exacto con {len(caso['facturas_propuestas'])} factura(s). "
                f"Aplicable sin revisión.")
    if cola == "CONFIRMAR":
        return (f"{caso['n_soluciones']} combinaciones distintas suman este monto. "
                f"Se propone la más cercana al vencimiento; conviene confirmar cuál corresponde.")
    if cola == "HIPOTESIS":
        return ("No calza con ninguna combinación exacta, pero cabe dentro de una "
                "factura abierta: probable pago parcial.")
    return (f"No corresponde a ninguna de las {caso['n_candidatas']} facturas abiertas "
            f"del cliente. Revisar factura fuera del sistema o moneda distinta.")


def explicar(caso):
    texto = llm.generar(
        SISTEMA,
        f"Cliente: {caso['cliente']}\n"
        f"Depósito: S/ {caso['monto']:,.2f} del {caso['fecha']:%d/%m/%Y}\n"
        f"Facturas abiertas del cliente ese día: {caso['n_candidatas']}\n"
        f"Combinaciones que suman exacto: {caso['n_soluciones']}\n"
        f"Propuesta del motor: {caso['facturas_propuestas'] or 'ninguna'}\n"
        f"Situación: {caso['explicacion']}",
        max_tokens=160,
    )
    return texto or _plantilla(caso)
