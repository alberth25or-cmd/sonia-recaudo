# Manual de uso — SON-IA

Cómo trabajar con lo construido. Organizado por lo que quieres hacer, no por archivo.

---

## Lo único que hay que abrir

**`sonia\torre.html`.** Doble clic. No necesita servidor, ni internet, ni instalar
nada: es una sola página que funciona en cualquier navegador y se puede enviar por
correo tal cual.

Cinco pestañas, cada una un trabajo:

| Pestaña | Qué se hace ahí | Quién · cada cuánto |
|---|---|---|
| **Resumen** | Cómo va todo y qué requiere atención | Todos · al entrar |
| **Asignar depósitos** | Buscar una empresa y resolver sus depósitos | Analista · a diario |
| **Cartera** | Fuga de ingresos, riesgo de impago, correos | Jefatura · semanal |
| **Auditar** | Revisar una muestra de lo que se aplicó solo | Contraloría · semanal |
| **Registro** | Todo lo decidido, con hora y motivo · descargas | Contraloría · al cerrar |

Las decisiones se guardan en el navegador, así que se puede cerrar y seguir después.

**Requisito opcional:** Ollama corriendo (`ollama serve`) al *generar* la torre, para
que las explicaciones las escriba el modelo. Sin él se generan con plantillas — solo
cambia la calidad del texto, no los números.

---

## El día a día del operador

**1. Abre la torre.** El Resumen dice cuántos depósitos se aplicaron solos, cuántos
esperan y cuánto trabajo son en minutos.

**2. Va a Asignar depósitos.** Ve la lista de empresas con casos pendientes,
**ordenadas por urgencia**: primero las que escribieron diciendo que pagaron, luego
las de riesgo alto de impago. Busca una empresa o toma la primera.

**3. Resuelve sus casos uno a uno.** Cada caso llega con la propuesta hecha:

- **Varias combinaciones válidas** → elige de una lista con la suma a la vista.
- **Pago parcial** → el depósito no cubre la factura entera; aprueba y queda el saldo.
- **Nada cuadra exacto** → el modelo señala las facturas más probables con su
  confianza y el acumulado contra el depósito. Confirma o corrige con el listado
  completo.

**4. Si algo no corresponde**, lo devuelve o lo pospone con el motivo.

Si se equivoca, **Deshacer** en Registro revierte la última decisión.

**Una vez por semana:** pestaña Auditar. Revisa una muestra de los que se aplicaron
solos —no son casos sospechosos, son justo aquellos de los que el sistema estaba
seguro— y marca si estuvieron bien.

**Cuando haya decisiones acumuladas:** en Registro, «Exportar para reentrenar» genera
el archivo con el que el modelo aprende de esas decisiones. Ver `realimentacion.py`.

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

## Cargar un período nuevo

Tres pasos, siempre los mismos:

```bash
python contrato.py C:\ruta\a\sus\exports   # 1. valida que los datos sirvan
python asignador.py --datos C:\ruta        # 2. reentrena el modelo con ellos
python torre.py                            # 3. regenera la torre
```

El paso 2 es opcional la primera vez —el modelo que viene entrenado funciona— pero
con datos propios rinde mejor.

`contrato.py` recorre las seis tablas y dice, columna por columna, si está y qué
formato de fecha detectó. Si los nombres difieren:

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
| Los textos salen genéricos | Ollama estaba detenido al generar | `ollama serve` y `python torre.py` de nuevo |
| Cambié código y no se refleja | La torre es un archivo generado | `python torre.py` para regenerarla |
| Las decisiones desaparecieron | Se guardan por navegador y por equipo | Descargar el registro antes de cambiar de máquina |
| `contrato.py` marca NO CUMPLE | Columnas o formato distintos | Usar `alias=`, `sep=`, `encoding=` |
| Los casos no traen sugerencia | Falta el artefacto entrenado | `python asignador.py` y regenerar la torre |

---

## Qué NO decir

Tres cosas que el sistema mide y que conviene no exagerar:

1. **No decir "Integratel está en X% de STP".** El dataset es sintético; lo medible
   es lo que este motor logra sobre estos datos.
2. **No usar el 80.5%** (2,709 de 3,364 facturas que calzan) como línea base: esa
   cifra ya incluye el trabajo manual que estamos reemplazando.
3. **No presentar los S/ 106,289 de huérfanos** como dinero real: `procedencia.py`
   muestra que el 92% apunta a series válidas inexistentes — artefacto del generador.
