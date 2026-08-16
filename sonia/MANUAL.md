# Manual de uso — SON-IA

Cómo trabajar con lo construido. Organizado por lo que quieres hacer, no por archivo.

---

## Lo único que hay que abrir

```bash
cd "C:\Users\Luis\Documents\cursor\hacktaton movistar\sonia"
streamlit run app.py
```

Se abre en **http://localhost:8501**. Las páginas están agrupadas por quién las
usa, y cada una es **un trabajo**, no un artefacto:

| Grupo | Página | Qué se hace ahí | Quién |
|---|---|---|---|
| **Operación** | **Hoy** | Ver qué toca y cómo va — es donde aterrizas | Analista |
| | **Conciliar** | Resolver la cola, un depósito a la vez | Analista, a diario |
| **Análisis** | **Cartera** | Fuga de ingresos, riesgo de impago, correos | Jefatura, semanal |
| **Administración** | **Control** | Muestreo de auditoría y trazabilidad | Contraloría, semanal |
| | **Datos** | Cargar los archivos del período | TI, al inicio |

El panel lateral muestra siempre **de dónde salen los datos** y qué motor de
lenguaje está activo, en todas las páginas.

Todo lo demás son comandos de terminal que imprimen números. No tienen pantalla.

**Requisito opcional:** Ollama corriendo (`ollama serve`) para que las explicaciones y
la clasificación de correos las escriba el modelo. Sin él, todo funciona igual con
plantillas y reglas — solo cambia la calidad del texto.

---

## El día a día del operador

Así trabajaría una persona real con esto:

**1. Abre la pestaña Verificación.** Arriba ve "Tu cola de hoy": cuántos casos hay
de cada tipo y cuántos minutos son. Los depósitos que se aplicaron solos no llegan
aquí — ya están resueltos.

**2. Empieza por "Elegir entre opciones".** Son los rápidos: el agente propone, la
suma está a la vista, se confirma o se elige otra combinación. Veinte segundos cada uno.

**3. Sigue con "Aprobar pago parcial".** El depósito no cubre la factura completa;
la pantalla muestra cuánto se aplica y cuánto queda pendiente. Un clic.

**4. Termina con "Investigar".** Los difíciles. Marca facturas en el selector y ve
la suma en vivo hasta cuadrar. Si no es de ese cliente, rechaza con el motivo.

**5. Descarga la auditoría** desde el panel lateral antes de cerrar.

Si se equivoca, **Deshacer** revierte la última decisión.

**Una vez por semana:** pestaña Auditoría. Revisa 32 casos de los que se aplicaron
solos (unos 11 minutos), marca si estuvieron bien, y registra la tanda.

---

## Los comandos, y qué prueba cada uno

Todos se corren desde la carpeta `sonia`.

### Los que usarás

```bash
python orquestador.py           # el ciclo completo: 4 agentes + supervisor + KPIs
python orquestador.py --log     # además, el log de auditoría entero
python torre.py                 # genera torre.html — el informe para proyectar o enviar
python contrato.py              # valida que los datos cumplan lo que el sistema espera
```

### Los que defienden una afirmación

Esta es la tabla que importa para el pitch. Cada número que digas tiene un comando
que lo produce delante de quien pregunte.

| Si alguien pregunta… | Corres… | Y sale |
|---|---|---|
| "¿De dónde sale ese 70.6%?" | `python backtest.py` | La medición escondiendo la respuesta |
| "¿Cómo se compara con la industria?" | `python benchmark.py` | STP contra el piso de 80% y el 95% mundial |
| "¿Cuánta gente hace falta?" | `python triaje.py` | Las cuatro colas y los 18.8 min/día |
| "¿Y si la IA lo hace mejor?" | `python desambiguacion.py` | El LLM pierde por 7.4 puntos |
| "¿Usan machine learning?" | `python asignador.py` | Sí, en los casos sin calce exacto: 79.4% → 96.6% |
| "¿El modelo no aprendió un truco del generador?" | `python asignador.py` | Quitarle el rasgo dominante cuesta 1.1 puntos |
| "¿Por qué no lo usan en todo?" | `python aprendizaje.py` | En las combinaciones del solver empata (67.5%): no aporta |
| "¿Aprende de nosotros?" | `python realimentacion.py <csv>` | Modo sombra: acierto contra lo que eligió el operador |
| "¿No sería mejor optimizar globalmente?" | `python asignacion.py` | CP-SAT pierde por 12.9 puntos |
| "¿Estos hallazgos son reales?" | `python procedencia.py` | Qué es del negocio y qué del generador |
| "¿Cómo eligieron la tolerancia?" | `python barrido.py` | La curva precisión/cobertura completa |
| "¿Funciona con nuestros datos?" | `python contrato.py <ruta>` | Valida columnas y formatos de fecha |

### Los de diagnóstico

```bash
python verificar.py       # confirma las cifras del documento de contexto
python diagnostico.py     # por qué el universo de candidatas es el que es
python auditoria.py       # el muestreo y su poder de detección
python llm.py             # qué motor de lenguaje está activo
```

---

## Qué tecnología decide qué (para no confundirse al explicarlo)

Son cuatro cosas distintas y conviene no mezclarlas:

| Componente | Qué es | ¿Qué hace en producción? |
|---|---|---|
| `solver.py` — subset-sum exacto | Algoritmo, no IA | **Decide** — el 70.6% que se aplica solo |
| `solver.ranking()` | Heurística de reglas de negocio | **Decide** — ordena las combinaciones ambiguas |
| `asignador.py` | Machine learning (gradient boosting) | **Propone, no aplica** — solo donde el solver no encuentra respuesta |
| `aprendizaje.py` | Machine learning sobre las combinaciones | **No** — medido, empató, no conectado |
| `llm.py` → explicador, cobranza | Modelo de lenguaje (Gemma on-premise) | **Redacta y clasifica** — nunca decide sobre dinero |

**Lo que se aplica sin humano es exclusivamente lo que tiene una única solución
matemática exacta.** El modelo entrenado actúa solo donde esa solución no existe,
y ahí propone: siempre hay una persona que confirma. Nunca sale plata por una
probabilidad. Esa separación es deliberada y es defendible ante un auditor.

## Cambiar el motor de lenguaje

```bash
# on-premise (por defecto si Ollama corre) — los datos no salen de la máquina
set SONIA_LLM=local

# nube — mejor redacción, requiere ANTHROPIC_API_KEY
set SONIA_LLM=claude

# sin modelo — reglas y plantillas, siempre funciona
set SONIA_LLM=off
```

Útil en la demo: muestras un caso explicado on-premise, cambias la variable, y
muestras el mismo caso con Claude. Demuestra que la arquitectura está desacoplada.

---

## Conectar los datos reales de Integratel

```bash
python contrato.py C:\ruta\a\sus\exports
```

Recorre las seis tablas y dice, columna por columna, si está y qué formato de fecha
detectó. Si los nombres difieren:

```python
datos.facturas(ruta="/export/sap/facturas.csv",
               alias={"RAZON_SOCIAL": "NOMBRE_CLIENTE"},
               sep=";", encoding="utf-8")
```

`FACTURA_AFECTADA` **no hace falta para operar** — en producción llega vacía, que es
el problema que el sistema resuelve. Sí hace falta para entrenar y medir.

---

## Si algo falla

| Síntoma | Causa | Solución |
|---|---|---|
| La app no abre | Streamlit detenido | `streamlit run app.py` desde `sonia` |
| Los textos salen genéricos | Ollama detenido | `ollama serve`, o dejarlo así: funciona igual |
| Cambié código y no se refleja | Caché de Streamlit | Reiniciar el proceso (la caché es en memoria) |
| `contrato.py` marca NO CUMPLE | Columnas o formato distintos | Usar `alias=`, `sep=`, `encoding=` |
| Veo 81.4% o 79.7% en un HTML | Es el dashboard del prototipo original | Abrir `sonia\torre.html` |

---

## Qué NO decir

Tres cosas que el sistema mide y que conviene no exagerar:

1. **No decir "Integratel está en X% de STP".** El dataset es sintético; lo medible
   es lo que este motor logra sobre estos datos.
2. **No usar el 80.5%** (2,709 de 3,364 facturas que calzan) como línea base: esa
   cifra ya incluye el trabajo manual que estamos reemplazando.
3. **No presentar los S/ 106,289 de huérfanos** como dinero real: `procedencia.py`
   muestra que el 92% apunta a series válidas inexistentes — artefacto del generador.
