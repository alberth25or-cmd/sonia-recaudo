"""Capa de modelo de lenguaje con backend intercambiable.

Tres modos, una sola interfaz. Se elige con la variable de entorno SONIA_LLM:

    local      Ollama corriendo en la máquina. Los datos NO salen de la red
               interna — el argumento de gobierno del dato para una telco.
    claude     API de Anthropic. Mejor redacción, requiere ANTHROPIC_API_KEY.
    off        Sin modelo. Los agentes caen a plantilla y reglas.

Sin la variable, se autodetecta: local si Ollama responde, luego Claude si hay
API key, y si no, off. La demo nunca se cae por falta de backend.

Que el backend sea intercambiable no es solo higiene: permite mostrarle al
jurado el mismo caso resuelto on-premise y en la nube, cambiando una variable.
"""

import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELO_LOCAL = os.environ.get("SONIA_MODELO_LOCAL", "gemma3:12b")
MODELO_CLAUDE = "claude-opus-5"

_backend_cache = None


def _ollama_vivo(timeout=1.5):
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def backend():
    """Resuelve el backend una sola vez por proceso."""
    global _backend_cache
    if _backend_cache is not None:
        return _backend_cache

    elegido = os.environ.get("SONIA_LLM", "").strip().lower()
    if elegido in ("local", "claude", "off"):
        _backend_cache = elegido
    elif _ollama_vivo():
        _backend_cache = "local"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        _backend_cache = "claude"
    else:
        _backend_cache = "off"
    return _backend_cache


def etiqueta():
    """Nombre legible del motor, para mostrar en la UI y en el log de auditoría."""
    return {"local": f"{MODELO_LOCAL} (on-premise)",
            "claude": f"{MODELO_CLAUDE} (nube)",
            "off": "reglas y plantillas"}[backend()]


def _generar_local(sistema, usuario, max_tokens, temperatura):
    cuerpo = json.dumps({
        "model": MODELO_LOCAL,
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": usuario}],
        "stream": False,
        "options": {"temperature": temperatura, "num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["message"]["content"].strip()


def _generar_claude(sistema, usuario, max_tokens, temperatura):
    import anthropic
    cliente = anthropic.Anthropic()
    # Tarea acotada con todos los datos en el prompt: sin razonamiento extendido,
    # para acotar latencia y costo. max_tokens cubre solo el texto de salida.
    respuesta = cliente.messages.create(
        model=MODELO_CLAUDE,
        max_tokens=max_tokens,
        thinking={"type": "disabled"},
        output_config={"effort": "low"},
        system=sistema,
        messages=[{"role": "user", "content": usuario}],
    )
    return next((b.text for b in respuesta.content if b.type == "text"), "").strip()


def generar(sistema, usuario, max_tokens=200, temperatura=0.2):
    """Devuelve el texto del modelo, o None si no hay backend o falló.

    None significa 'usa tu plantilla': el que llama nunca se queda sin respuesta.
    """
    modo = backend()
    if modo == "off":
        return None
    try:
        if modo == "local":
            return _generar_local(sistema, usuario, max_tokens, temperatura)
        return _generar_claude(sistema, usuario, max_tokens, temperatura)
    except Exception:
        return None


def elegir(sistema, usuario, opciones, max_tokens=8):
    """Pide al modelo elegir UNA opción de una lista cerrada.

    Devuelve el índice elegido, o None si el modelo no respondió algo válido.
    Validamos siempre contra la lista: nunca se confía en el texto crudo.
    """
    texto = generar(sistema, usuario, max_tokens=max_tokens, temperatura=0.0)
    if not texto:
        return None
    digitos = "".join(c for c in texto if c.isdigit())
    if not digitos:
        return None
    idx = int(digitos[:2]) - 1  # las opciones se numeran desde 1
    return idx if 0 <= idx < len(opciones) else None


if __name__ == "__main__":
    print(f"Backend activo: {backend()}  ->  {etiqueta()}")
    if backend() != "off":
        print("\nPrueba:")
        print(generar("Responde en español, máximo una frase.",
                      "¿Qué es la conciliación de pagos?", max_tokens=80))
