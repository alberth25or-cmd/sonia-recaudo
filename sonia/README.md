# SON-IA — Equipo de agentes para el ciclo de ingreso de Integratel

Reto 3 · Hackatón AI Telecom Challenge · Movistar + Universidad de Lima

Cuatro agentes operadores coordinados por un supervisor, con **recaudo al centro**
porque es el cuello de botella que el propio equipo de Movistar señaló y que el
análisis de datos confirma.

---

## Los datos

Los 6 CSV del reto van incluidos, así que el sistema corre al clonar. Son datos
**sintéticos y anonimizados** por los organizadores: los clientes son
`CLIENT_00001`…`CLIENT_01000` y los RUC están aleatorizados — no hay información
de ninguna empresa real. Ver `procedencia.py` para qué patrones son del negocio
y cuáles del generador.

Antes de correr nada conviene validarlos:

```bash
cd sonia
python contrato.py
```

Debe decir **CUMPLE** en las seis tablas.

## Correr

```bash
python orquestador.py          # ciclo completo: 4 agentes + supervisor + KPIs
python orquestador.py --log    # además, el log de auditoría entero
```

No requiere conexión ni API key. Con `ANTHROPIC_API_KEY` en el entorno, los
agentes de Recaudo y Cobranza usan Claude para redactar y clasificar; sin ella
caen a plantilla y reglas, y el sistema entrega los mismos números.

### Verificación

```bash
python backtest.py    # precisión medida contra ground truth
python triaje.py      # desglose de la cola humana y carga de personal
python diagnostico.py # por qué el universo de candidatas es el que es
python barrido.py     # calibración de la ventana y la tolerancia
```

---

## El resultado

**STP de 70.6%** — 1,612 de 2,283 depósitos aplicados sin que nadie los mire,
S/ 194,482. En esa banda automática el motor **se equivoca 1 vez de cada 1,596**.
La carga humana que queda es de **18.8 minutos por día hábil — 0.045 FTE**.

Ese número era 34 minutos hasta que se conectó `asignador.py`. Los 221 casos de
la cola *investigar* llegaban en blanco y costaban 5 minutos cada uno; ahora
llegan con las facturas más probables señaladas y el trabajo pasa a ser
confirmar. Ver «El asignador aprendido» más abajo.

La precisión de la propuesta, medida escondiendo la respuesta y comparándola
contra los 3,548 pagos del dataset, es **78.4%** sobre los eventos evaluables. Son
dos métricas distintas: el STP es cuántos se aplican solos; la precisión es
cuántas propuestas aciertan, incluidas las que van a revisión.

> El dataset del reto es **sintético** — ver la sección de procedencia más abajo
> antes de citar cualquier cifra en soles.

### Posicionamiento contra la industria

Esto tiene nombre: *cash application automation*, dentro de order-to-cash.
HighRadius, SAP Cash Application, Sidetrade y Serrala resuelven lo mismo y todos
miden STP. El piso de las herramientas líderes ronda el 80%; clase mundial, 95%.

```
python benchmark.py
```

|  | STP |
|---|---|
| SON-IA hoy — solo motor determinista, capa LLM sin activar | **70.6%** |
| Si el agente desambigua los 128 casos con varias combinaciones | 76.2% |
| Si además resuelve los 322 pagos parciales | 90.3% |
| Techo con estos datos | 90.3% |

Los 221 casos restantes son depósitos huérfanos y moneda extranjera: irresolubles
sin el extracto bancario completo, que no viene en el dataset.

> ⚠️ **El 80.5% (2,709 de 3,364 facturas que calzan) no es STP** y no debe usarse
> como línea base. Ese cálculo agrupa por `FACTURA_AFECTADA`, que es la respuesta
> que hoy produce a mano un analista: mide calidad del dato *después* del trabajo
> humano, no automatización. Las cifras de la industria son publicaciones de los
> propios proveedores — sirven como orden de magnitud, no como benchmark auditado.

| Agente | Qué entrega |
|---|---|
| **Recaudo** | 2,283 depósitos procesados · 70.6% aplicados solos · S/ 194,482 |
| **Facturación** | 79 clientes con servicio activo sin facturar · S/ 22,956 de fuga · 5.83% de notas de crédito (línea base a reducir) |
| **BI** | 4 clientes en riesgo alto de cobranza dudosa · S/ 74,822 pendientes · mayor concentración en 0-30 días |
| **Cobranza** | 10 correos clasificados · 4 confirmaciones de pago entregadas a Recaudo |

---

## Dónde aporta el LLM — medido, no supuesto

El modelo corre **on-premise** (Ollama + Gemma 3 12B). Los datos no salen de la
máquina: es la respuesta a la pregunta de gobierno del dato que una telco hace
siempre. El backend es intercambiable con una variable de entorno:

```
SONIA_LLM=local    # Ollama — por defecto si está corriendo
SONIA_LLM=claude   # API de Anthropic, requiere ANTHROPIC_API_KEY
SONIA_LLM=off      # sin modelo: reglas y plantillas
```

Pusimos a prueba la hipótesis obvia —que el agente elegiría mejor que la
heurística entre combinaciones ambiguas— y **resultó falsa**:

```
python desambiguacion.py
```

| Sobre 108 casos ambiguos | Acierto |
|---|---|
| Heurística determinista (vencimiento + antigüedad) | **74.1%** |
| Agente (Gemma 3 12B, on-premise) | 66.7% |

El LLM es **7.4 puntos peor**. La heurística ya codifica el criterio de negocio
mejor de lo que el modelo lo reconstruye desde el prompt. Medido, no supuesto —
y por eso la cola CONFIRMAR sigue resolviéndose con la regla.

Esto **afina la tesis** en vez de romperla. El LLM aporta donde no hay regla que
aplicar:

- **explicar** cada caso al operador en dos frases auditables (corriendo)
- **clasificar** los correos entrantes, que son texto sin estructura (corriendo)
- **hipotetizar** sobre los depósitos que no encajan con nada (siguiente paso)

> Probamos un modelo local de 12B, no "los LLM en general". El arnés de medición
> queda montado y el backend es intercambiable: con una API key se corre lo mismo
> contra Claude y se compara. Eso es precisamente para lo que sirve desacoplarlo.

## La capa de aprendizaje — dos intentos, uno perdido y uno ganado

### Intento 1: que el modelo elija entre las candidatas del solver — empató

```
python aprendizaje.py
```

| Sobre 83 eventos ambiguos de julio | Acierto |
|---|---|
| Heurística determinista | **67.5%** |
| Modelo aprendido (gradient boosting) | **67.5%** |

Empate exacto, y la importancia de características explica por qué: el modelo
asigna **0.741 a `dias_vto_max`**. Aprendiendo desde cero redescubrió la regla de
cercanía al vencimiento que la heurística ya codifica. Misma señal, mismo
resultado. **Reemplazar una regla que funciona por un modelo que la iguala no
aporta nada**, así que la cola CONFIRMAR sigue con la regla.

### Intento 2: que el modelo ataque lo que el solver NO resuelve — ganó

El error del primer intento fue de planteamiento. Ordenar las candidatas del
solver solo sirve donde el solver encontró candidatas; en los **537 depósitos sin
calce exacto no hay ninguna que ordenar**. Medimos qué son esos casos: la mediana
paga el **59%** de lo facturado. No son descuentos ni retenciones —eso daría
95-99%— son pagos parciales grandes repartidos entre varias facturas.

Así que el modelo hace otra cosa: **puntúa factura por factura** la probabilidad
de que el depósito la esté tocando. Una fila por factura abierta en vez de una
por combinación, lo que da 5,042 ejemplos en lugar de unos cientos. Y los casos
que el solver ya resuelve exacto son datos etiquetados gratis: los fáciles
enseñan a atacar los difíciles.

```
python asignador.py
```

| Julio, verdad escondida | Casos | Hoy | Regla simple | Modelo |
|---|---|---|---|---|
| Pago parcial | 130 | 76.9% | 75.4% | **96.9%** |
| Investigar | 86 | 0.0% | 95.3% | **97.7%** |
| **Con 2+ facturas abiertas** | **175** | — | **79.4%** | **96.6%** |

«Regla simple» es imputar a la factura que vence más cerca — lo que cualquiera
escribiría en diez minutos, y el rival contra el que el modelo tiene que
justificarse. Medirlo contra «hoy» exageraría: la cola *investigar* puntúa 0 por
no proponer nada, no por equivocarse.

**Descartamos que dependa de un artefacto del generador.** El rasgo más
importante es `acumulado_fifo` (0.533), que podría ser un atajo si el generador
hubiera fabricado los pagos como «las primeras k facturas FIFO». Quitándolo, el
modelo pierde **1.1 puntos** (96.6% → 95.4%); ese rasgo por sí solo llega apenas
al 62.9%. La señal está distribuida, no concentrada en una llave.

**El modelo propone, nunca aplica.** Solo actúa donde el algoritmo exacto no
encuentra respuesta, y ahí siempre hay una persona que confirma. Lo que sale sin
intervención es exclusivamente lo que tiene una única solución matemática exacta.

### El bucle: el sistema aprende de su propia gente

```
python realimentacion.py realimentacion.csv                # modo sombra
python realimentacion.py realimentacion.csv --reentrenar
```

Cada caso que un operador resuelve en la torre es un ejemplo etiquetado: vio el
depósito, vio las facturas abiertas y eligió. Desde la pestaña Registro exporta
esas decisiones y el modelo se reentrena con ellas.

Antes de aprender, `realimentacion.py` responde la pregunta que importa: **¿el
modelo habría acertado?** Compara lo que proponía contra lo que el humano
eligió — medido *antes* de estudiar esas mismas decisiones. Ese porcentaje es lo
que permite decidir si el modelo se ganó el derecho a proponer con más peso.

Con arranque en frío no hace falta nada de esto: sin artefacto entrenado
`proponer()` devuelve el orden heurístico y el sistema funciona el día uno.

> **Advertencia:** el operador también se equivoca, y aprender de sus decisiones
> propaga sus sesgos. Por eso la auditoría semanal no es opcional: es lo que
> mantiene limpia la fuente de entrenamiento.

## La decisión de diseño que sostiene todo

**El LLM no resuelve el rompecabezas; lo resuelve el código.**

Asignar un depósito a un conjunto de facturas es *subset-sum*: con 20 facturas
abiertas son un millón de combinaciones, y se enumeran exacto en milisegundos.
Pedirle eso a un modelo de lenguaje es lento, no reproducible y alucinable.

El LLM entra donde sí hay criterio de negocio:

- cuando el solver devuelve **varias** combinaciones válidas (pasa en 128 casos,
  con 5.8 alternativas en promedio) y hay que elegir con criterio;
- cuando **ninguna** encaja y hay que hipotetizar por qué;
- para **explicarle** la propuesta al operador en dos frases que pueda auditar.

De ahí sale el costo: ~US$ 0.45 por día hábil de cómputo de IA. Escala con los
casos difíciles, no con el volumen de facturación.

---

## Dónde entra el humano

Cuatro colas, ordenadas por esfuerzo. El humano **confirma, no calcula** — la
aritmética se le muestra resuelta, así que el trabajo lo hace un asistente en
veinte segundos y no un analista senior en diez minutos.

| Cola | Casos | S/ | Qué hace el humano | min/día |
|---|---|---|---|---|
| AUTO | 1,612 | 194,482 | Nada — auditoría por muestreo | 0 |
| CONFIRMAR | 128 | 42,269 | Elige entre opciones ya ordenadas | 1 |
| HIPOTESIS | 322 | 97,639 | Aprueba una propuesta de pago parcial | 7 |
| INVESTIGAR | 221 | 58,446 | Trabajo real de analista | 26 |

La tolerancia de calce está en **S/ 0.00** a propósito. Aflojarla a S/ 1.00
ahorra 8 minutos diarios y compra 28 aplicaciones equivocadas que nadie ve:
mal negocio. La curva completa está en `barrido.py`.

**Falta para producción:** reversibilidad de toda aplicación automática,
muestreo de auditoría del 2% semanal, y un techo diario de la cola INVESTIGAR.

---

## ⚠️ El dataset del reto es sintético

Eso no invalida nada de lo construido, pero cambia qué se puede afirmar:

- **Transfiere a producción:** la arquitectura, el solver, el diseño de colas, la
  estación de verificación y —sobre todo— el **método de medición** (esconder la
  respuesta y comparar). Y los patrones estructurales que existen en cualquier
  operación B2B: pagos agrupados, pagos parciales, depósitos sin etiquetar.
- **NO transfiere:** ningún importe en soles como "dinero de Integratel", ni el
  STP exacto. El 70.6% es lo que este motor logra sobre estos datos.

```
python procedencia.py    # separa hallazgos del negocio de artefactos del generador
```

## Hallazgos sobre los datos, y cuánto pesa cada uno

| Hallazgo | Verificado | ¿Presentable como hallazgo de negocio? |
|---|---|---|
| El RUC no sirve como llave (450 de 999 discrepan; en PAGOS hay uno por fila). `RAZON_SOCIAL` cruza 3,383 de 3,383 sin un cliente equivocado | ✅ | **Sí** — es la trampa de anonimización, y afecta a cualquiera que use estos datos |
| `COD_CUENTA` arrastra la misma inconsistencia (239 de 240) — hallazgo de Agentes 1551 | ✅ | **Sí**, mismo motivo |
| La ventana temporal desbalancea: facturas desde 2023, pagos solo jun–jul 2026. 23 facturas sin pago no son mora | ✅ | **Sí** — es rigor metodológico, no una afirmación sobre el negocio |
| 5.8% de pagos anteriores a su factura | ✅ | **Con cuidado** — no es ruido aleatorio, pero se concentra entre 9 y 15 días, lo que parece frontera de ciclo del generador. Un anticipo real se concentraría en 1–3 días |
| 74 pagos huérfanos por S/ 106,289 | ✅ | **No** — el 92% apunta a números con serie válida que simplemente no existen: desacople del generador, no cobros sin factura |

La regla: presentar la **estructura** del problema y el **método**, no los soles.

---

## Conectar los datos reales de Integratel

El sistema no tiene rutas ni formatos codificados: `contrato.py` es la frontera
con sus sistemas. Declara qué columnas hacen falta y por qué, valida una fuente
antes de procesar nada, y **detecta solo el formato de fecha** de cada columna
—incluido `FECHA_VTO`, que mezcla dos.

```bash
python contrato.py                        # valida los CSV del reto
python contrato.py /ruta/a/sus/exports    # valida una carpeta propia
```

Si sus tablas usan otros nombres o formatos, se mapean sin tocar el resto:

```python
datos.facturas(ruta="/export/sap/facturas.csv",
               alias={"RAZON_SOCIAL": "NOMBRE_CLIENTE"},
               sep=";", encoding="utf-8")
```

**Lo mínimo que se necesita:**

| Tabla | Columnas |
|---|---|
| Facturas | `NRO_DOC_FISCAL`, `RAZON_SOCIAL`, `FECHA_EMISION`, `FECHA_VTO`, importe |
| Pagos | `RAZON_SOCIAL`, `FECHA_PAGO`, `MONTO_PAGADO` |
| Notas de crédito | `FACTURA_AFECTADA`, `FECHAEMISION`, `MONTO` |
| Clientes / planta | `RAZON_SOCIAL` + estado (para PCD y fuga de ingresos) |

`FACTURA_AFECTADA` en pagos **no hace falta para operar** — en producción llega
vacía, que es justamente el problema que el sistema resuelve. Sí hace falta para
**entrenar y medir**: es la resolución manual que sus analistas hicieron durante
años, y es lo que el modelo aprende.

## Estructura

```
sonia/
├── orquestador.py      supervisor: asigna, controla, escala, mide
├── agentes/
│   ├── recaudo.py      identifica a qué factura pertenece cada depósito
│   ├── facturacion.py  fuga de ingresos y calidad de emisión
│   ├── bi.py           PCD, aging y priorización de cobranza
│   ├── cobranza.py     clasifica correos entrantes
│   ├── explicador.py   redacta la propuesta para el operador
│   └── correos.py      corpus sintético (el reto no entrega correos)
├── solver.py           subset-sum determinista — el motor
├── datos.py            carga de los 6 CSV con sus trampas resueltas
├── backtest.py         medición contra ground truth
├── triaje.py           colas humanas y cálculo de personal
├── diagnostico.py      por qué el universo de candidatas es el que es
└── barrido.py          calibración de ventana y tolerancia
```

---

## Créditos y procedencia

Los agentes de Facturación, BI y Cobranza, el corpus de correos sintéticos y el
patrón de fallback sin API key vienen del prototipo de **Agentes 1551**, portados
aquí con tres correcciones (ventana temporal en BI, fecha de corte del aging,
y separación de dos KPIs que se leían como uno).

El motor de recaudo se reescribió: el prototipo agrupaba los pagos por
`PAGOS.FACTURA_AFECTADA`, que es la respuesta que hoy producen a mano los
analistas. Medía calidad del dato, no capacidad del agente. Esta versión
reconstruye el depósito como llega del banco —empresa, monto, fecha— y resuelve
sin mirar esa columna; `FACTURA_AFECTADA` se usa únicamente para calificar la
propuesta a posteriori en `backtest.py`.

## Preguntas abiertas para los organizadores

1. Tipo de cambio para los 21 pagos en USD.
2. Regla de imputación vigente cuando llega un pago parcial (¿más antigua,
   mayor monto, proporcional?).
3. Tolerancia que la empresa considera aceptable para cerrar automáticamente.
4. Si existen los correos reales de clientes.
