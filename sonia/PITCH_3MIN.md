# Pitch de 3 minutos — SON-IA

**Cómo usar este documento.** Cada lámina trae dos cosas separadas:

- **EN LA LÁMINA** — el texto que va proyectado. Es denso a propósito: el jurado
  lo lee mientras hablas y ahí viven los datos que no alcanzas a decir.
- **LO QUE DICES** — el guion hablado, cronometrado. **No leas la lámina en voz
  alta.** Si dices lo mismo que está escrito, desperdicias los dos canales.

Total hablado: **450 palabras ≈ 3:00** a ritmo de presentación (150 palabras/min).
Si vas justo de tiempo, el plan de corte está al final.

---

## Lámina 1 · El problema
**≈ 18 s**

### EN LA LÁMINA

> # Ya pagaron. Nadie sabe qué factura.

Del banco llega esto y nada más:

| Empresa | Monto | Fecha |
|---|---|---|
| CLIENT_00756 | S/ 6,297.10 | 04/06/2026 |

Ese cliente tiene **12 facturas abiertas**.
Con 20 facturas abiertas → **más de 1 millón de combinaciones posibles**.

Mientras tanto: figura como moroso · lo llama cobranza · le cortan el servicio.

### LO QUE DICES

«Una empresa pagó hace dos semanas. Sigue apareciendo como morosa, la siguen
llamando, y le van a cortar el servicio. No porque no haya pagado: porque nadie
logró averiguar **cuál** de sus facturas estaba pagando. Veinte facturas
abiertas son más de un millón de combinaciones.»

---

## Lámina 2 · Esto ya está resuelto en el mundo
**≈ 20 s**

### EN LA LÁMINA

> # El problema tiene nombre y tiene solución probada

**Cash application**, dentro del ciclo *order-to-cash*.

Quiénes lo resuelven: **HighRadius · SAP Cash Application · Sidetrade · Serrala**

Todos lo miden con **un solo indicador**:

> **STP** *(Straight-Through Processing)* — qué % de los pagos se aplica sin que
> nadie los toque.

| Referencia | STP |
|---|---|
| Piso de las herramientas líderes | ~80% |
| Clase mundial | ~95% |
| L'Oréal con HighRadius* | 96% · US$ 57M de reducción de riesgo crediticio |

<sub>*Caso publicado por el proveedor.</sub>

**Lo que no existe: una implementación sobre los sistemas de Integratel.**

### LO QUE DICES

«Esto tiene nombre: *cash application*. HighRadius, SAP y Sidetrade lo resuelven
hace años, y todos lo miden igual: qué porcentaje se aplica sin que nadie lo
toque. L'Oréal reporta noventa y seis. El problema tiene solución probada; lo
que no existe es una implementación sobre los sistemas de ustedes.»

---

## Lámina 3 · Nuestra arquitectura
**≈ 11 s — esta lámina se muestra más de lo que se habla**

### EN LA LÁMINA

> # Tres capas. Cada una donde gana.

| Capa | Qué es | Qué resuelve |
|---|---|---|
| **1 · Algoritmo exacto** | Combinatoria, no IA | **70.6%** sin intervención |
| **2 · Modelo entrenado** | Gradient boosting | **96.6%** de lo que la capa 1 no resuelve |
| **3 · Modelo de lenguaje** | Gemma 3, on-premise | Explica y clasifica — **nunca decide** |

> **Nada que decida sobre dinero pasa por una probabilidad.**
> Lo que se aplica solo es exclusivamente lo que tiene **una única solución
> matemática exacta**.

### LO QUE DICES

«Nuestra solución son tres capas, y cada una está puesta donde gana. Lo
importante es la regla de abajo: **nada que decida sobre dinero pasa por una
probabilidad.**»

---

## Lámina 4 · La capa determinista
**≈ 18 s**

### EN LA LÁMINA

> # Encontrar qué facturas suman el depósito

**El problema formal:** *subset-sum* — NP-completo.

**La técnica:** *meet-in-the-middle* — **Horowitz & Sahni, J. ACM, 1974**
Parte las candidatas en dos mitades, ordena una y busca por bisección.

```
2³⁰ combinaciones  →  2 × 2¹⁵     (mil millones → treinta mil)
```

**Decisiones de ingeniería que importan:**

- Aritmética en **céntimos enteros** — con flotantes la igualdad exacta se rompe
- **Saldo, no total** — 169 facturas del período se pagan en cuotas
- **Ventana de suspenso de 10 días** — 5.8% de los pagos llega antes de la factura
- Desempate: cercanía al vencimiento → menos facturas → FIFO

**Tolerancia calibrada, no elegida a dedo:**

| Tolerancia | Resuelve solo | Se equivoca |
|---|---|---|
| **S/ 0.00** ← operamos aquí | 70.6% | **0.06%** (1 de 1,596) |
| S/ 1.00 | 73.6% | 2.8% |
| S/ 5.00 | 74.5% | 7.5% |

### LO QUE DICES

«Encontrar qué subconjunto de facturas suma el depósito es *subset-sum*, un
problema NP-completo. Lo resolvemos con *meet-in-the-middle*, la técnica de
Horowitz y Sahni: mil millones de combinaciones se vuelven treinta mil, en
milisegundos. Y ahí nos equivocamos **una vez de cada mil quinientas noventa y
seis**.»

---

## Lámina 5 · La capa que aprende
**≈ 26 s**

### EN LA LÁMINA

> # 537 depósitos donde ninguna combinación cuadra

**Primero medimos qué son.** La mediana paga el **59%** de lo facturado.
No son descuentos ni retenciones (eso daría 95-99%): son **pagos parciales
grandes** repartidos entre varias facturas.

**El planteamiento correcto.** Ahí no hay combinaciones que ordenar. La pregunta
cambia de unidad:

> ~~¿Cuál combinación es la correcta?~~
> **¿Cuál es la probabilidad de que este depósito esté tocando esta factura?**

Una fila por **factura abierta**, no por combinación → 5,042 ejemplos.
Los **1,612 casos que el algoritmo ya resolvió** son datos etiquetados gratis:
los fáciles enseñan a atacar los difíciles.

**Técnica:** gradient boosting — *Friedman, Annals of Statistics, 2001*
**Validación:** separación **temporal** (entrena junio, evalúa julio), respuesta escondida

| Julio, verdad escondida | Regla simple | **Modelo** |
|---|---|---|
| Casos con 2+ facturas abiertas | 79.4% | **96.6%** |
| Cola *investigar* (hoy llega en blanco) | 0% | **97.7%** |

**Descartamos que sea un truco del generador:** quitarle el rasgo dominante
cuesta **1.1 puntos**. La señal está distribuida, no en una llave.

### LO QUE DICES

«Quedan quinientos treinta y siete depósitos sin calce exacto. Medimos qué son:
la mediana paga el cincuenta y nueve por ciento de lo facturado — pagos
parciales grandes. Ahí no hay combinaciones que ordenar, así que el modelo hace
otra cosa: **puntúa factura por factura**. Contra la regla obvia, imputar a la
que vence más cerca, pasa de **setenta y nueve a noventa y siete por ciento**.»

---

## Lámina 6 · El modelo de lenguaje
**≈ 18 s**

### EN LA LÁMINA

> # Gemma 3, corriendo dentro de la máquina

**Los datos financieros de sus clientes no salen a ningún servicio externo.**

| Sí hace | No hace |
|---|---|
| Redactar la explicación de cada caso escalado | Decidir a qué factura va un pago |
| Clasificar los correos entrantes | Calcular montos |

**Y no es una postura, es una medición:**

| Pedirle al LLM que elija entre combinaciones | 66.7% |
|---|---|
| La heurística determinista | **74.1%** |

→ **pierde por 7.4 puntos.** Por eso no está ahí.

*Backend intercambiable:* `local` (Ollama) · `nube` (API) · `off` (plantillas).
El sistema nunca se cae por falta de modelo.

### LO QUE DICES

«El modelo de lenguaje corre **dentro de la máquina**: los datos de sus clientes
no salen a ningún servicio externo. Escribe la explicación que lee el operador y
clasifica correos. No decide sobre dinero, y no es postura: lo probamos y
**pierde por siete puntos**.»

---

## Lámina 7 · Los agentes y el orquestador
**≈ 18 s**

### EN LA LÁMINA

> # Cuatro agentes que se hablan entre sí

| Agente | Su especialidad |
|---|---|
| **Facturación** | Detecta servicio activo sin facturar y errores que exigen nota de crédito |
| **Recaudo** | Identifica a qué factura pertenece cada depósito |
| **Cobranza** | Clasifica correos y prioriza a quién contactar |
| **Inteligencia de Negocio** | Riesgo de impago, antigüedad de deuda, priorización |

**El orquestador** asigna, controla tiempos y **encadena**:

```
Cobranza lee "ya pagué"
   → le pide a Recaudo que priorice ese cliente
      → si el pago ya estaba aplicado, lo saca de la ruta de cobranza
```

Todo queda registrado: **hora, autor, motivo. Y es reversible.**

### LO QUE DICES

«Cuatro agentes, coordinados por un orquestador. Y **se hablan**: cobranza lee
un correo que dice "ya pagué", le pide a recaudo que priorice ese cliente, y si
el pago ya estaba aplicado lo saca de la ruta de cobranza para que no lo vuelvan
a llamar.»

---

## Lámina 8 · El resultado
**≈ 19 s**

### EN LA LÁMINA

> # En su unidad de medida

| | |
|---|---|
| **70.6%** | de los depósitos aplicados sin intervención — 1,612 de 2,283 |
| **1 de 1,596** | tasa de error en la banda automática |
| **18.8 min/día** | trabajo humano restante — **0.045 FTE** |
| **34 → 19 min** | efecto de conectar el modelo entrenado |

**Los 671 que sí requieren criterio no llegan en blanco:** llegan con la
propuesta hecha, el motivo escrito y la confianza a la vista.

> **Cómo lo medimos.** Escondimos la columna que hoy un analista llena a mano y
> reconstruimos cada depósito como llega del banco. El motor resolvió sin verla.
> Entrenar con junio, evaluar con julio.

### LO QUE DICES

«El resultado: setenta coma seis por ciento se aplica solo. Lo que queda son
**diecinueve minutos de trabajo al día**, no una persona a tiempo completo. Y
todo está medido escondiendo la columna que hoy llena un analista a mano:
entrenamos con junio y evaluamos con julio.»

---

## Lámina 9 · Qué cuesta y qué necesitamos
**≈ 21 s**

### EN LA LÁMINA

> # Cero licencias. El costo es la integración.

| Concepto | Costo |
|---|---|
| Software | **S/ 0** — Python, scikit-learn, Ollama, Gemma: todo abierto |
| Hardware | Una laptop. Con GPU el LLM va 4× más rápido; sin GPU funciona igual |
| Cómputo | ≈ US$ 10/mes. **No crece con el volumen** — crece con los casos difíciles |
| Integración con AMDOCS e ISIS | Semanas-persona de TI — **trabajo de sistemas, no de algoritmo** |

**Qué necesitamos de ustedes:**

1. **Lectura** de las seis tablas (o sus equivalentes en AMDOCS / ISIS)
2. **Su histórico de `FACTURA_AFECTADA`** para entrenar
3. **Un analista, 20 minutos al día**

> **Aquí el modelo aprendió de dos meses. Ustedes tienen años.**
> Con ese histórico aprende el comportamiento **de cada cliente** — que es donde
> esta categoría llega al 95%.

*Comparación: una plataforma comercial es licencia anual + meses de implementación.*

### LO QUE DICES

«Cero licencias: todo es abierto y corre en una laptop. Lo que cuesta es la
integración con AMDOCS e ISIS, que es trabajo de sistemas. Y necesitamos una
cosa: **su histórico**. Aquí el modelo aprendió de dos meses; ustedes tienen
años, y ahí es donde esta categoría llega al noventa y cinco.»

---

## Lámina 10 · Cierre
**≈ 11 s**

### EN LA LÁMINA

> # Sus clientes ya están pagando.
> # El problema era identificar ese dinero.

| 70.6% | 19 min/día | 1 error / 1,596 | En una laptop |
|---|---|---|---|

**Y el sistema aprende de su propia gente:** cada caso que un analista resuelve
queda como ejemplo de entrenamiento. Propone mejor la próxima vez.

> Cada número de esta presentación tiene un comando que lo reproduce.

### LO QUE DICES

«Sus clientes ya están pagando. Hicimos que identificar ese dinero deje de
costar un día de trabajo. Y **cada número que dijimos tiene un comando que lo
reproduce**.»

---

# Plan de corte si vas sobre tiempo

| Si te sobran | Quita |
|---|---|
| 15 s | Lámina 7 (agentes) — se muestra sin hablar |
| 30 s | Lámina 7 + la mitad de la 4 (deja solo el error de 1/1,596) |
| 45 s | Lámina 7 + Lámina 3 (fusiónala con la 4) |

**Nunca cortes la 2, la 5 ni la 9.** La 2 da confianza en que el problema tiene
solución, la 5 es la pieza técnica que nos distingue, y la 9 es lo que convierte
una demo en un proyecto.

---

# Anexo · Láminas de respaldo (solo si preguntan)

## A1 · Por qué esta opción y no otra

| Alternativa | Por qué no |
|---|---|
| **Plataforma comercial** (HighRadius, SAP) | Licencia anual + meses de implementación. Los datos salen de la red |
| **Todo con un LLM** | Medido: pierde por 7.4 puntos y no es auditable |
| **Optimización global** (CP-SAT sobre todos los depósitos) | Medido: pierde por 12.9 puntos (62.5% vs 75.4%) |
| **Solo reglas** | No cubre los 537 casos sin calce exacto |

**Lo nuestro:** on-premise, cero licencias, auditable línea por línea, y cada
decisión de diseño está medida en vez de supuesta.

## A2 · Los experimentos que perdieron

Los reportamos porque explican por qué el sistema es liviano:

| Hipótesis | Resultado |
|---|---|
| Un LLM elige mejor entre combinaciones ambiguas | **−7.4 pts** (66.7% vs 74.1%) |
| Un modelo entrenado supera a la heurística en la cola *confirmar* | **empate** (67.5% ambos) |
| Asignación global óptima con CP-SAT | **−12.9 pts** (62.5% vs 75.4%) |
| La confianza del modelo sirve como puerta de auto-aplicación | **invertida** — 77.8% al margen 0.30, 47.1% al 0.90 |

En la cola *confirmar*, el modelo asignó **0.741 de importancia** a
`dias_vto_max`: aprendiendo desde cero **redescubrió la regla de negocio** que la
heurística ya codificaba. Por eso ahí no está conectado.

## A3 · Marco teórico completo

| Componente | Fundamento |
|---|---|
| Subset-sum exacto | Horowitz & Sahni (1974), *Computing Partitions with Applications to the Knapsack Problem*, J. ACM |
| Gradient boosting | Friedman (2001), *Greedy Function Approximation*, Annals of Statistics |
| Escalamiento por tipo de incertidumbre | Clasificación selectiva / opción de rechazo — Chow (1970), IEEE Trans. Inf. Theory |
| Ordenamiento de candidatas | Familia *learning-to-rank* (LambdaRank / LambdaMART). Usamos la formulación por ítem: más simple y con más ejemplos disponibles |
| Despliegue seguro del modelo | *Modo sombra* — el modelo predice y se compara contra el humano antes de que se le dé peso. Práctica estándar de MLOps |
| Validación de los datos entregados | Ley de Benford + pruebas de repetición, montos redondos y series huérfanas |

## A4 · Las preguntas difíciles

**«¿Y si se equivoca?»**
Tres respuestas: el error está **medido**, no supuesto (1 de 1,596); toda decisión
es reversible y queda registrada con hora, autor y motivo; y cada semana se
audita una muestra de lo aplicado automáticamente.

**«¿El modelo decide sobre el dinero?»**
No. Solo actúa donde el algoritmo exacto no encuentra respuesta, y ahí **propone,
no aplica**: siempre confirma una persona.

**«¿Cómo sé que el modelo sirve?»**
Lo comparamos contra la regla obvia sobre los mismos casos, entrenando con junio
y evaluando con julio con la respuesta escondida. Y le quitamos su rasgo más
importante para ver si dependía de un solo dato: pierde 1.1 puntos.

**«¿El agente emite la factura?»**
No. Elegimos profundizar en recaudo porque su equipo lo señaló como el cuello de
botella más difícil, y porque es donde los datos permitían medir de verdad. La
emisión automática requiere integrarse con AMDOCS e ISIS: trabajo de sistemas.

**«¿Esto no lo hace HighRadius ya?»**
Sí, y por eso sabemos que funciona. La diferencia es que esto corre sobre sus
datos, dentro de su infraestructura, y coordina recaudo con facturación y
cobranza.

---

# Lo que NO se dice

1. **No decir «Integratel está en X% de STP».** El dataset del reto es sintético.
   Lo medible es lo que este motor logra sobre estos datos.
2. **No presentar los S/ 106,289 de huérfanos como dinero real.** El 92% apunta a
   series válidas inexistentes: es un desacople del generador de datos.
3. **No comparar el 70.6% con ninguna cifra de la operación actual de ellos** —
   no la conocemos.
4. **No mencionar a otros equipos.** No aporta y gasta tiempo.

**Regla general:** presentar la **estructura del problema**, no los soles. Los
importes describen el dataset, no la caja de Integratel.
