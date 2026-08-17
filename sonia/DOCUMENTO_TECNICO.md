# SON-IA · Documento técnico completo

**Reto 3 — AI Telecom Challenge · Movistar × Universidad de Lima**
Sistema agéntico para el ciclo de ingreso de Integratel (Movistar B2B Perú):
facturación, recaudo, cobranza e inteligencia de negocio.

---

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [El problema](#2-el-problema)
3. [Los datos: qué nos dieron y qué se puede afirmar con ellos](#3-los-datos)
4. [Estado del arte: cómo resuelve esto la industria](#4-estado-del-arte)
5. [La solución: arquitectura de tres capas](#5-la-solución-arquitectura-de-tres-capas)
6. [Capa 1 · El motor determinista](#6-capa-1--el-motor-determinista)
7. [Capa 2 · El modelo entrenado](#7-capa-2--el-modelo-entrenado)
8. [Capa 3 · El modelo de lenguaje](#8-capa-3--el-modelo-de-lenguaje)
9. [Los agentes, uno por uno](#9-los-agentes-uno-por-uno)
10. [El puesto humano](#10-el-puesto-humano)
11. [Metodología de medición](#11-metodología-de-medición)
12. [Resultados](#12-resultados)
13. [Comparación con cómo lo hacen otras empresas](#13-comparación-con-cómo-lo-hacen-otras-empresas)
14. [Implementación: costo, requisitos y plazos](#14-implementación-costo-requisitos-y-plazos)
15. [Dificultad y riesgo](#15-dificultad-y-riesgo)
16. [Limitaciones honestas](#16-limitaciones-honestas)
17. [Hoja de ruta](#17-hoja-de-ruta)
18. [Anexos](#18-anexos)

---

# 1. Resumen ejecutivo

## Qué construimos

Un sistema de cuatro agentes de IA coordinados por un supervisor, que automatiza
el ciclo de ingreso de Integratel. El foco está en **recaudo** —identificar a qué
factura corresponde cada depósito bancario— porque el propio equipo de Movistar
lo señaló como el cuello de botella más difícil de su operación.

## El resultado, en una tabla

| Indicador | Valor |
|---|---|
| Depósitos aplicados sin intervención humana (**STP**) | **70.6%** — 1,612 de 2,283 |
| Monto conciliado automáticamente | S/ 194,482 |
| Tasa de error en la banda automática | **1 de 1,596** (0.06%) |
| Trabajo humano restante | **18.8 min por día hábil** — 0.045 FTE |
| Acierto del modelo en los casos que el algoritmo no resuelve | **96.6%** (vs 79.4% de una regla simple) |
| Costo de licencias de software | **S/ 0** |

## La idea central

**Tres capas, cada una puesta donde gana, y una regla que no se rompe:**

> **Nada que decida sobre dinero pasa por una probabilidad.**

| Capa | Tecnología | Rol | ¿Decide? |
|---|---|---|---|
| **1** | Algoritmo combinatorio exacto | Resuelve el 70.6% | **Sí** — pero solo cuando hay una única solución matemática |
| **2** | Gradient boosting | Ataca lo que la capa 1 no resuelve | **No** — propone; un humano confirma |
| **3** | Modelo de lenguaje local (Gemma 3) | Explica y clasifica texto | **No** — nunca toca un número |

Esta separación no es una preferencia estética: **cada frontera está medida**.
Probamos poner el LLM y el modelo entrenado en el lugar del algoritmo exacto y
ambos perdieron. Los experimentos están en la [sección 12.4](#124-los-experimentos-que-perdieron).

---

# 2. El problema

## 2.1 Lo que pide el reto

La ficha del Reto 3 plantea construir un ecosistema de IA agéntica para el ciclo
de ingreso de Integratel, con tres requisitos explícitos:

1. **IA agéntica** — agentes autónomos con *skills* especializados por proceso.
2. **Orquestación** — un agente supervisor que asigna, controla y da seguimiento
   a las actividades de los agentes operadores.
3. **Control de indicadores**, calidad y tiempo del servicio.

Y describe un flujo de tres momentos: asesoría previa a la emisión → ejecución
automatizada de la factura → **rebaja automática post-pago**.

> **Dónde nos concentramos y por qué.** El tercer momento —la rebaja post-pago,
> es decir la conciliación— es donde profundizamos. Dos razones: el equipo de
> Movistar lo señaló como el punto más difícil, y es el único donde los datos
> entregados permitían **medir** de verdad si la solución funciona. La emisión
> automática de facturas requiere integración de escritura con AMDOCS e ISIS,
> que es trabajo de sistemas y no de algoritmo. Está declarado como limitación
> en la [sección 16](#16-limitaciones-honestas).

## 2.2 El cuello de botella, descrito como lo vive una persona

Una empresa cliente paga su factura. El dinero entra a la cuenta de Integratel y
el extracto bancario dice tres cosas:

| Empresa | Monto | Fecha |
|---|---|---|
| CLIENT_00756 | S/ 6,297.10 | 04/06/2026 |

**Y nada más.** No dice qué factura está pagando.

Ese cliente tiene 12 facturas abiertas. ¿Está pagando una entera? ¿Tres juntas?
¿Una parte de la más grande? Alguien tiene que abrir el estado de cuenta, mirar
los saldos, y probar combinaciones hasta que cuadre.

Mientras eso no ocurre:

- El cliente **figura como moroso** aunque pagó.
- **Cobranza lo llama** por una deuda que ya no existe.
- En el límite, **le cortan el servicio** por un error administrativo propio.
- La **provisión de cobranza dudosa** se calcula sobre una deuda ficticia.

## 2.3 Por qué es genuinamente difícil

No es un problema de digitación. Es un problema **combinatorio**.

Con *n* facturas abiertas, el número de subconjuntos posibles es 2ⁿ:

| Facturas abiertas | Combinaciones posibles |
|---|---|
| 5 | 32 |
| 10 | 1,024 |
| **20** | **1,048,576** |
| 24 | 16,777,216 |

En el dataset del reto hay clientes con **24 facturas abiertas** en el momento del
depósito. Diecisiete millones de combinaciones no se revisan a mano.

Y se agrava con cuatro complicaciones que aparecen en cualquier operación B2B
real:

1. **Pagos agrupados.** Un depósito puede cubrir varias facturas. En el dataset,
   1.55 pagos por evento en promedio.
2. **Pagos parciales.** El cliente abona una parte. **169 facturas** del período
   se pagan en cuotas.
3. **Pagos adelantados.** El dinero llega antes de que la factura se emita.
4. **Montos que no coinciden con nada.** Retenciones, detracciones, comisiones
   bancarias, o una factura que no está en el sistema.

---

# 3. Los datos

## 3.1 Qué nos entregaron

Seis tablas en CSV:

| Tabla | Registros | Contenido |
|---|---|---|
| `001_TBL_CLIENTES_B2B` | 1,000 | Razón social, RUC, estado SUNAT |
| `002_TBL_PLANTA_FIJA_B2B` | — | Servicios fijos y su estado |
| `003_TBL_PLANTA_MOVIL_B2B` | — | Líneas móviles y su estado |
| `004_TBL_PAGOS_B2B` | 3,548 | Pagos con fecha, monto y `FACTURA_AFECTADA` |
| `005_TBL_FACTURAS_B2B` | 3,364 | Facturas con emisión, vencimiento y total |
| `006_TBL_NOTAS_CREDITO_B2B` | — | Notas de crédito por factura |

**Ventanas temporales — y esto importa mucho:**

| | Desde | Hasta |
|---|---|---|
| Facturas | 2023-04-18 | 2026-08-05 |
| **Pagos** | **2026-06-01** | **2026-07-31** |

Hay más de tres años de facturas pero **solo dos meses de pagos**. Una factura de
2023 sin pago registrado casi con seguridad se pagó fuera de la ventana de
datos — **no es mora**. El agente de BI acota su análisis a lo emitido dentro de
la ventana precisamente por esto ([sección 9.4](#94-agente-de-inteligencia-de-negocio)).

**Reconstrucción de los depósitos.** Los 3,548 pagos se agrupan en **2,283
eventos** (cliente + día), que es la unidad real: lo que llega del banco es un
depósito, no un pago por factura.

## 3.2 La columna que escondimos

`PAGOS.FACTURA_AFECTADA` dice a qué factura corresponde cada pago.

**Esa columna es la respuesta, no el insumo.** En producción llega vacía: es
exactamente el trabajo que hoy hace un analista a mano. Usarla para construir la
propuesta mediría la calidad del dato, no la capacidad del sistema.

Así que **la escondemos** y solo la usamos para evaluar a posteriori. Toda la
metodología de medición sale de ahí ([sección 11](#11-metodología-de-medición)).

## 3.3 Análisis de procedencia: qué es del negocio y qué del generador

**El dataset del reto es sintético.** Un modelo entrenado sin cuidado aprende los
artefactos del generador y falla en producción de formas difíciles de detectar.

Construimos `procedencia.py` para separar ambas cosas, con cinco pruebas
forenses:

| Prueba | Qué detecta |
|---|---|
| **Ley de Benford** | Distribución del primer dígito de los importes. Datos reales la siguen; datos generados con distribuciones uniformes, no |
| **Repetición de importes** | Un generador reutiliza montos con más frecuencia que la realidad |
| **Montos redondos** | Exceso de cifras terminadas en 00 |
| **Forma del desfase de fechas** | Un adelanto de pago real se concentra en 1-3 días; un artefacto de ciclo se concentra en un valor fijo |
| **Series huérfanas** | Pagos que apuntan a facturas inexistentes |

### El hallazgo que tuvimos que retractar

Detectamos **74 pagos huérfanos por S/ 106,289.40** — dinero cobrado sin factura
en el sistema. Parecía un hallazgo de negocio importante.

**No lo es.** El 92% de esos pagos apunta a series de numeración **válidas del
maestro** pero a números de factura que no existen. Mismo formato, factura
inexistente: es un desacople del generador de datos, no un cobro real sin
respaldo.

> Está documentado aquí porque **el rigor incluye retirar los hallazgos que no
> resisten el escrutinio**, no solo publicar los que sí.

### Otro artefacto identificado

El 5.8% de los pagos llega **antes** de que su factura se emita. En un negocio
real ese desfase se concentraría en 1-3 días (pago anticipado). Aquí se concentra
entre 9 y 15 días, con mediana en 10 — forma de frontera de ciclo del generador.

La **ventana de suspenso de 10 días** que usa el motor es necesaria para procesar
estos datos, pero **en producción hay que recalibrarla** contra el comportamiento
verdadero. Está marcado en el código.

## 3.4 Qué se puede afirmar y qué no

| ✅ Transfiere a producción | ❌ No se debe afirmar |
|---|---|
| La **estructura** del problema: pagos agrupados, parciales, sin etiquetar | «Integratel está en X% de STP» |
| La **metodología**: esconder la respuesta y medir | «Detectamos S/ 106,289 de cobros sin factura» |
| La **arquitectura** y las decisiones de diseño | «El 5.8% de los pagos llega adelantado» |
| Que el modelo **supera a la regla simple** en la misma tarea | Que el 96.6% se replicará idéntico con datos reales |

---

# 4. Estado del arte

## 4.1 El problema tiene nombre

Se llama **cash application**, y es una etapa del ciclo **order-to-cash** (O2C).
Es una categoría madura de software empresarial, no un problema abierto.

**La métrica única de la categoría** es el **STP** — *Straight-Through
Processing*: qué porcentaje de los pagos recibidos se aplica a su factura sin
intervención humana.

## 4.2 Quién lo resuelve y con qué números

| Proveedor | Enfoque |
|---|---|
| **HighRadius** | Líder de la categoría. ML entrenado sobre el historial de remesas por cliente |
| **SAP Cash Application** | Servicio de ML integrado a S/4HANA |
| **Sidetrade** | Plataforma O2C con IA («Aimie») |
| **Serrala** | Automatización de finanzas, fuerte en Europa |

**Referencias públicas de desempeño:**

| Referencia | STP |
|---|---|
| Piso de las herramientas líderes | ~80% |
| Considerado clase mundial | ~95% |
| L'Oréal con HighRadius\* | 96%, con US$ 57M de reducción de riesgo crediticio reportada |

<sub>\* **Advertencia de fuente:** las cifras de casos de éxito son **publicadas
por los propios proveedores**, no por investigación independiente. Sirven para
establecer que el problema tiene solución probada y cuál es el orden de magnitud
del techo — no como línea base auditada.</sub>

## 4.3 Los estudios y técnicas que sustentan cada capa

| Componente | Fundamento teórico |
|---|---|
| **Subset-sum exacto** | Horowitz, E. & Sahni, S. (1974). *Computing Partitions with Applications to the Knapsack Problem*. Journal of the ACM 21(2), 277-292. Origen de la técnica *meet-in-the-middle* |
| **Gradient boosting** | Friedman, J. (2001). *Greedy Function Approximation: A Gradient Boosting Machine*. Annals of Statistics 29(5), 1189-1232 |
| **Escalamiento por incertidumbre** | Chow, C.K. (1970). *On Optimum Recognition Error and Reject Tradeoff*. IEEE Trans. Information Theory 16(1), 41-46. Fundamento de la clasificación selectiva / opción de rechazo |
| **Ordenamiento de candidatas** | Familia *learning-to-rank*: Burges et al. (2006), *Learning to Rank with Nonsmooth Cost Functions*, NIPS. **Nosotros usamos la formulación por ítem**, más simple y con más ejemplos disponibles — ver [7.2](#72-el-planteamiento-correcto) |
| **Implementación de ML** | Pedregosa et al. (2011). *Scikit-learn: Machine Learning in Python*. JMLR 12, 2825-2830 |
| **Validación forense de datos** | Ley de Benford, aplicada a auditoría contable (Nigrini) |
| **Despliegue seguro de modelos** | *Modo sombra* / champion-challenger: el modelo predice en paralelo y se compara contra la decisión humana antes de recibir autoridad. Práctica estándar de MLOps |

## 4.4 Qué tomamos y en qué nos apartamos

| Lo que hace la industria | Lo que hacemos nosotros | Por qué |
|---|---|---|
| ML sobre el historial de remesas **por cliente** | ML sobre patrones **globales** | La mediana del dataset es **2 eventos por cliente**; solo el 4.4% llega a 5. No hay historial individual que aprender. Con los años de Integratel, la misma arquitectura admite el corte por cliente |
| El motor de matching suele ser propietario y opaco | **Algoritmo exacto y auditable** línea por línea | Sobre dinero, poder explicar por qué se aplicó cada pago vale más que un punto de cobertura |
| Nube, datos salen de la red del cliente | **On-premise completo** | Gobierno del dato para una telco. Los datos financieros de sus clientes no salen |
| Licencia anual + implantación de meses | **Cero licencias**, todo software abierto | Ver [sección 14](#14-implementación-costo-requisitos-y-plazos) |

---

# 5. La solución: arquitectura de tres capas

## 5.1 El principio de separación

> **Cada tecnología se pone donde gana, y nada que decida sobre dinero pasa por
> una probabilidad.**

```
                    Depósito bancario
                  (empresa, monto, fecha)
                            │
                            ▼
              ┌─────────────────────────────┐
              │  CAPA 1 · ALGORITMO EXACTO  │
              │  subset-sum combinatorio    │
              └─────────────┬───────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    1 solución        varias soluciones    ninguna
          │                 │                  │
          ▼                 ▼                  ▼
    ┌──────────┐      ┌──────────┐   ┌──────────────────┐
    │ SE APLICA│      │ humano   │   │ CAPA 2 · MODELO  │
    │  70.6%   │      │  elige   │   │ puntúa factura   │
    │          │      │          │   │ por factura      │
    └──────────┘      └────┬─────┘   └────────┬─────────┘
                           │                  │
                           │                  ▼
                           │         ┌──────────────────┐
                           │         │ humano confirma  │
                           │         │ la propuesta     │
                           └────┬────┴──────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ CAPA 3 · LLM (Gemma)  │
                    │ escribe el porqué     │
                    │ en lenguaje natural   │
                    └───────────────────────┘
```

## 5.2 Por qué esta combinación y no otra

Cada frontera de esta arquitectura **está medida**, no supuesta:

| Pregunta | Qué probamos | Resultado |
|---|---|---|
| ¿Y si el LLM elige entre las combinaciones? | `desambiguacion.py` | **Pierde por 7.4 pts** (66.7% vs 74.1%) |
| ¿Y si un modelo entrenado reemplaza la heurística? | `aprendizaje.py` | **Empata** (67.5% ambos) |
| ¿Y si optimizamos globalmente todos los depósitos? | `asignacion.py` (CP-SAT) | **Pierde por 12.9 pts** (62.5% vs 75.4%) |
| ¿Y si el modelo ataca lo que el algoritmo no resuelve? | `asignador.py` | **Gana: 79.4% → 96.6%** |

**Tres de cuatro hipótesis fallaron.** Ese es el motivo por el que el sistema
es liviano: no hay infraestructura pesada porque medimos que no aporta.

---

# 6. Capa 1 · El motor determinista

**Archivo:** `solver.py` · **Consumido por:** `agentes/recaudo.py`

## 6.1 El problema formal

> Dado un conjunto de facturas abiertas con sus saldos, y un monto depositado,
> encontrar qué subconjunto suma exactamente ese monto.

Esto es **subset-sum**, un problema **NP-completo**. La fuerza bruta es O(2ⁿ):
con 30 facturas son mil millones de combinaciones.

## 6.2 La técnica: meet-in-the-middle

**Horowitz & Sahni (1974).** La idea:

1. Partir las *n* facturas en dos mitades de *n/2*.
2. Enumerar **todas** las sumas posibles de cada mitad: 2^(n/2) cada una.
3. Ordenar una de las listas.
4. Para cada suma de la primera mitad, buscar por **bisección** el complemento
   que falta en la segunda.

```
Complejidad:  O(2ⁿ)  →  O(2^(n/2) · n)

2³⁰ = 1,073,741,824  combinaciones
        ↓
2 × 2¹⁵ = 65,536     sumas parciales   →  milisegundos
```

## 6.3 Cuatro decisiones de ingeniería que deciden si funciona

Estas no son detalles: cada una rompía el sistema hasta que se resolvió.

### 1 · Aritmética en céntimos enteros

Con números de punto flotante, `0.1 + 0.2 != 0.3`. En un algoritmo cuyo criterio
es **la igualdad exacta**, eso destruye el resultado. Todo el motor opera en
enteros de céntimos.

### 2 · Saldo, no total

**169 facturas del período se pagan en cuotas.** Si el candidato es el total de
la factura, el segundo pago nunca cuadra contra nada. El monto candidato es el
**saldo**: total menos los pagos estrictamente anteriores a la fecha del depósito.

> El «estrictamente anteriores» importa: incluir el pago actual sería filtrar la
> respuesta dentro del insumo.

### 3 · Ventana de suspenso de 10 días

El 5.8% de los pagos llega antes de que su factura se emita. Sin una ventana que
permita considerar facturas emitidas *después* del depósito, **161 eventos
agrupados se rompen**. El valor de 10 días es el óptimo medido en `barrido.py`.

> En producción **hay que recalibrar** este parámetro: en el dataset el desfase
> parece un artefacto del generador ([sección 3.3](#33-análisis-de-procedencia-qué-es-del-negocio-y-qué-del-generador)).

### 4 · El desempate cuando hay varias soluciones

Cuando existe más de una combinación válida, se ordenan por criterios de negocio
que un analista de recaudo reconoce:

1. **Cercanía al vencimiento** — señal dominante: el cliente paga lo que está por
   vencer
2. **Menos facturas** — la explicación más simple
3. **FIFO** — lo más antiguo primero

## 6.4 La tolerancia, calibrada y no elegida a dedo

¿Cuánta diferencia se acepta como «calza»? Es una perilla con consecuencias
medidas (`barrido.py`):

| Tolerancia | Resuelve solo | **Se equivoca** |
|---|---|---|
| **S/ 0.00** ← operamos aquí | 70.6% | **0.06%** (1 de 1,596) |
| S/ 1.00 | 73.6% | 2.8% |
| S/ 5.00 | 74.5% | 7.5% |

**Aflojar la tolerancia compra 3 puntos de cobertura a cambio de multiplicar el
error por 45.** Sobre dinero, equivocarse cuesta más que escalar a un humano.

---

# 7. Capa 2 · El modelo entrenado

**Archivo:** `asignador.py` · **Artefacto:** `asignador.joblib` (266 KB)

## 7.1 El hallazgo que originó esta capa

Quedan **537 depósitos** donde el algoritmo exacto no encuentra **ninguna**
combinación. Antes de modelar nada, medimos **qué son**:

| Pagó / facturado | Casos | % |
|---|---|---|
| Menos del 50% | 35 | 16% |
| **50 – 80%** | **116** | **54%** |
| 80 – 95% | 24 | 11% |
| 95 – 99.9% | 27 | 13% |
| Exacto | 11 | 5% |

**Mediana: 0.594.**

Esto descarta la hipótesis natural. No son descuentos, retenciones ni
detracciones — eso daría ratios de 95-99%. **Son pagos parciales grandes**: el
cliente debe algo repartido entre varias facturas y abona una parte.

## 7.2 El planteamiento correcto

Nuestro primer razonamiento fue que el ML no tenía nada que hacer ahí, porque
*un ranker necesita una lista que ordenar* y el solver no encontró ninguna.

**Ese razonamiento era un error de planteamiento.** No hay combinaciones, pero sí
hay facturas abiertas, y la pregunta se puede hacer de otra forma:

> ~~¿Cuál combinación es la correcta?~~
> **¿Cuál es la probabilidad de que este depósito esté tocando esta factura?**

Cambiar la unidad de *combinación* a *factura abierta* tiene tres consecuencias:

1. **Multiplica los ejemplos.** Una fila por factura abierta → **5,042 filas**
   sobre 2,221 depósitos, en vez de unos cientos de combinaciones.
2. **Es auditable.** El operador ve la puntuación de cada factura, no un
   conjunto opaco.
3. **Cubre ambas colas difíciles** a la vez: pago parcial e investigar.

## 7.3 De dónde salen los ejemplos de entrenamiento

**De los casos fáciles.** Los **1,612 depósitos que el algoritmo exacto ya
resolvió** son datos etiquetados gratis: enseñan qué forma tiene una asignación
correcta. El modelo aprende de ellos y se evalúa sobre los difíciles.

> En producción no hace falta ese rodeo: Integratel tiene **años** de
> `FACTURA_AFECTADA` en su historial.

## 7.4 Las características del modelo

16 características, todas disponibles **al momento de decidir** (ninguna depende
de la respuesta):

| Grupo | Características |
|---|---|
| **Relación de importes** | `ratio_saldo_deposito`, `cabe_entera`, `sobrante_relativo`, `log_saldo` |
| **Tiempo** | `dias_vto`, `abs_dias_vto`, `dias_desde_emision`, `rank_vto`, `rank_antiguedad` |
| **Contexto de la cartera** | `n_abiertas`, `deposito_sobre_cartera`, `saldo_sobre_cartera`, `es_la_mayor`, `es_la_menor`, `acumulado_fifo` |
| **Estado de la factura** | `parcialmente_pagada` |

`acumulado_fifo` merece explicación: es la suma acumulada de facturas en orden
FIFO hasta esta, dividida por el depósito. Captura el patrón «el depósito alcanza
para las primeras *k* facturas más antiguas».

## 7.5 Validación: separación temporal y verdad escondida

- **Entrena** con los eventos de **junio**
- **Evalúa** con los de **julio**
- La respuesta permanece **escondida** durante toda la resolución

Esto imita el despliegue real —aprender del pasado, predecir el futuro— y evita
el optimismo de una partición aleatoria.

## 7.6 Resultados

| Julio, verdad escondida | Casos | Hoy | Regla simple | **Modelo** |
|---|---|---|---|---|
| Pago parcial | 130 | 76.9% | 75.4% | **96.9%** |
| Investigar | 86 | 0.0% | 95.3% | **97.7%** |
| **Con 2+ facturas abiertas** | **175** | — | **79.4%** | **96.6%** |

### Sobre la elección del baseline

Nuestra primera medición reportaba **+51 puntos**, comparando contra lo que el
sistema hacía antes. **Ese baseline era deshonesto**: la cola *investigar* puntúa
0% porque no proponía nada, no porque se equivocara.

El rival justo es **la regla de una línea que cualquiera escribiría en diez
minutos**: imputar a la factura que vence más cerca. Contra ella la ganancia real
es **+17 puntos**.

También excluimos los 41 casos con **una sola factura abierta** (19%): acertar
ahí no tiene mérito.

## 7.7 La prueba de ablación

`acumulado_fifo` se lleva el **53% de la importancia**. Si el generador hubiera
fabricado los pagos como «las primeras *k* facturas FIFO», ese rasgo sería un
atajo que no existe en producción.

| Configuración | Acierto (2+ abiertas) |
|---|---|
| Modelo completo | 96.6% |
| **Sin `acumulado_fifo`** | **95.4%** (−1.1 pts) |
| Solo `acumulado_fifo` | 62.9% |
| Solo vencimiento | 71.4% |

**Quitarle el rasgo dominante cuesta 1.1 puntos.** La señal está distribuida
entre las características, no concentrada en una llave del generador.

## 7.8 El bucle de aprendizaje

**Archivo:** `realimentacion.py`

Cada caso que un operador resuelve en la torre **es un ejemplo etiquetado**: vio
el depósito, vio las facturas abiertas y eligió. Desde la pestaña Registro
exporta esas decisiones y el modelo se reentrena con ellas.

### Modo sombra

Antes de aprender, el módulo responde la pregunta que importa: **¿el modelo
habría acertado?** Compara lo que proponía contra lo que el humano eligió,
**medido antes de estudiar esas decisiones** — medirlo después sería preguntarle
por lo que se acaba de aprender.

```
sin datos          → heurística (funciona el día uno)
50 decisiones      → modelo en sombra: predice, no decide
evidencia sostenida→ el modelo se gana más peso en la propuesta
```

### Arranque en frío

Sin artefacto entrenado, `proponer()` devuelve el orden heurístico. **El sistema
nunca depende de que el modelo exista.**

### Advertencia sobre este bucle

> El operador también se equivoca. Aprender de sus decisiones **propaga sus
> sesgos**: si acostumbra a imputar siempre a la factura más antigua, el modelo
> aprenderá eso, sea correcto o no. Por eso la auditoría semanal no es opcional
> — es lo que mantiene limpia la fuente de entrenamiento.

---

# 8. Capa 3 · El modelo de lenguaje

**Archivo:** `llm.py` · **Modelo:** Gemma 3 (12B) vía Ollama, on-premise

## 8.1 Qué hace y qué no hace

| ✅ Sí hace | ❌ No hace |
|---|---|
| Redactar la explicación de cada caso escalado, en lenguaje que el operador audita sin abrir otro sistema | Decidir a qué factura va un pago |
| Clasificar los correos entrantes de clientes en cinco categorías | Calcular montos |

## 8.2 Y no es una postura: es una medición

Probamos darle al LLM el trabajo de elegir entre combinaciones ambiguas
(`desambiguacion.py`):

| Estrategia | Acierto |
|---|---|
| LLM eligiendo | 66.7% |
| **Heurística determinista** | **74.1%** |

→ **pierde por 7.4 puntos.**

> **Matiz honesto:** probamos un modelo local de 12B, no «los LLM en general».
> El arnés de medición queda montado y el backend es intercambiable: con una API
> key se corre lo mismo contra un modelo de frontera y se compara.

## 8.3 Arquitectura: backend intercambiable

Tres modos con una sola interfaz, seleccionables con una variable de entorno:

| Modo | Qué usa | Cuándo |
|---|---|---|
| `local` | Ollama en la máquina | **Por defecto.** Los datos no salen de la red interna |
| `claude` | API en la nube | Mejor redacción, requiere API key |
| `off` | Reglas y plantillas | Sin modelo — **el sistema funciona igual** |

**El sistema nunca se cae por falta de backend.** Si el modelo no responde, cada
agente cae a su plantilla y solo cambia la calidad del texto, no los números.

## 8.4 Por qué on-premise es un argumento y no un detalle

Para una telco, los datos de facturación y pagos de sus clientes corporativos son
información sensible. Que el modelo corra **dentro de la máquina** significa que
esa información **no sale a ningún servicio externo**. Es un argumento de
gobierno del dato que ninguna plataforma en la nube puede ofrecer.

---

# 9. Los agentes, uno por uno

## 9.1 El orquestador (agente supervisor)

**Archivo:** `orquestador.py`

Cumple los tres requisitos explícitos de la ficha:

| Requisito | Cómo lo cumple |
|---|---|
| IA agéntica con skills especializados | Cuatro agentes operadores, cada uno con su dominio |
| Orquestación por un supervisor | Asigna trabajo, controla resultados, escala lo no resuelto y **encadena agentes entre sí** |
| Control de indicadores, calidad y tiempo | Cada decisión queda en el log con marca de tiempo; al final reporta KPIs por agente |

### El encadenamiento real entre agentes

Esto es lo que distingue un sistema agéntico de cuatro scripts sueltos:

```
Cobranza clasifica un correo como CONFIRMACION_PAGO
    │
    ├─ ¿Ese cliente tiene depósitos sin conciliar?
    │     SÍ → "traspaso_a_recaudo": Recaudo prioriza el caso
    │     NO → "cerrar_sin_gestion": sacar de la ruta de cobranza,
    │           no volver a llamarlo
    │
BI consume lo que ya calcularon Recaudo y Facturación
    └─ cruza riesgo de impago × servicio sin facturar
       → "URGENTE: visita comercial, no cobranza automática"
```

**El agente de BI no relee los CSV crudos:** consume la salida de los otros dos.
Esa dependencia *es* la coordinación que pide la ficha.

---

## 9.2 Agente de Recaudo

**Archivo:** `agentes/recaudo.py` · **El núcleo del sistema**

### Función

Identificar a qué factura(s) pertenece cada depósito bancario.

### Cómo trabaja

1. Reconstruye los depósitos como llegan del banco: **empresa, día, monto** —
   descartando `FACTURA_AFECTADA`.
2. Para cada uno, obtiene las facturas abiertas del cliente a esa fecha (con su
   **saldo**, y con la ventana de suspenso de 10 días).
3. Ejecuta el **solver exacto**.
4. Clasifica el resultado en una de **cuatro colas** según el tipo de
   incertidumbre.
5. Cuando no hay solución exacta, consulta al **asignador entrenado**.
6. Redacta una explicación auditable de una línea.

### Las cuatro colas

| Cola | Condición | Qué hace la persona | Casos | Seg/caso |
|---|---|---|---|---|
| **AUTO** | Exactamente 1 solución | Nada — se aplica | 1,612 | 0 |
| **CONFIRMAR** | Varias soluciones válidas | Elige de una lista ordenada | 128 | 20 |
| **HIPOTESIS** | Ninguna, pero el depósito cabe en una factura | Aprueba el pago a cuenta | 322 | 60 |
| **INVESTIGAR** | Ninguna y nada lo absorbe | Confirma lo que señala el modelo | 221 | 120 |

> **Por qué colas y no un umbral de confianza.** Un umbral dice «85%, aplícalo» —
> un número sin significado accionable. Clasificar por **qué tipo de
> incertidumbre** hay le dice al operador qué trabajo tiene que hacer. Es la
> aplicación práctica de la clasificación selectiva de Chow (1970).

### Lo que este agente NO hace

**No lee `FACTURA_AFECTADA` para decidir.** Esa columna se usa exclusivamente para
evaluar la propuesta a posteriori.

---

## 9.3 Agente de Facturación

**Archivo:** `agentes/facturacion.py`

### Función

Detectar **fuga de ingresos** y medir la **calidad de emisión**.

### Capacidad 1 — Fuga de ingresos

Cruza la planta activa (fija y móvil) contra la facturación emitida. Un cliente
con **servicio prendido** cuya última factura es demasiado vieja es dinero que se
está escapando.

| Nivel | Condición |
|---|---|
| **CRÍTICO** | Servicio activo y **nunca** facturado |
| **ALTO** | Sin factura hace más de 60 días |
| **NORMAL** | Dentro del ciclo esperado |

**Estimación del impacto en soles:** traduce días sin facturar usando el **ticket
mensual promedio del propio cliente**, con tope de 12 meses de exposición para no
inflar el caso.

### Capacidad 2 — Calidad de emisión

Tasa de notas de crédito: el indicador que la ficha pide reducir.

### Resultados

| | |
|---|---|
| Clientes con fuga (ALTO + CRÍTICO) | **79** |
| Nunca facturados | **1** |
| Impacto estimado | **S/ 22,956.50** |
| Tasa de error de facturación | **5.83%** |

### Decisión de diseño heredada del análisis del equipo

`COD_CUENTA` arrastra la misma inconsistencia de anonimización que el RUC, así que
**el cruce cliente↔factura va siempre por `RAZON_SOCIAL`**.

---

## 9.4 Agente de Inteligencia de Negocio

**Archivo:** `agentes/bi.py`

### Función

Calcular riesgo de cobranza dudosa (PCD), antigüedad de deuda (aging) y
**priorizar a quién cobrar primero**.

### Capacidad 1 — Provisión de cobranza dudosa

Combina dos señales:

| Señal | Puntos |
|---|---|
| Riesgo tributario (SUNAT: NO HABIDO o contribuyente no activo) | +2 |
| Comportamiento de pago (facturas pendientes, tope 5) | +1 a +5 |

→ Niveles BAJO / MEDIO / ALTO.

### Capacidad 2 — Aging

Buckets de antigüedad: Vigente · 0-30 · 31-60 · 61-90 · 90+ días.

### Capacidad 3 — Priorización con estrategia

Cruza PCD con la fuga que detectó Facturación y emite una recomendación
**accionable**, no un puntaje:

| Situación | Estrategia recomendada |
|---|---|
| Riesgo ALTO **y** servicio sin facturar | **URGENTE: visita comercial**, no cobranza automática |
| Riesgo ALTO | Priorizar en la siguiente ronda de cobranza |
| Paga bien pero tiene servicio sin facturar | Corregir antes de que acumule |

### Tres correcciones metodológicas que este agente incorpora

Sobre el prototipo original del equipo:

1. **Ventana temporal.** Una factura de 2023 sin pago registrado no es mora — se
   pagó fuera de la ventana de datos. El análisis se acota a lo emitido dentro de
   la ventana. *El prototipo contaba 23 de esas (S/ 79,116) como deuda.*
2. **Fecha de corte del aging.** El original usaba `max(FECHA_VTO)` = 2026-08-18,
   18 días después del último pago observado, lo que corría todos los buckets.
   Aquí el corte es **el último pago real**.
3. **KPIs separados.** «10 clientes ALTO | deuda total S/ 159,964» en una línea se
   lee mal: esa deuda es de los ~1,000 clientes, no de los 10.

### Resultados

| | |
|---|---|
| Clientes en riesgo ALTO | **4** |
| Deuda de esos 4 | S/ 30,157.14 |
| Deuda pendiente total | S/ 74,822.43 |
| Bucket de mayor concentración | **0-30 días** — S/ 58,696.24 |

---

## 9.5 Agente de Cobranza

**Archivo:** `agentes/cobranza.py`

### Función

Leer y clasificar las comunicaciones entrantes de clientes.

> La ficha señala que hoy **«ningún buzón está centralizado, organizado ni
> respondido automáticamente»**.

### Cinco categorías

`CONFIRMACION_PAGO` · `RECLAMO_MONTO` · `SOLICITUD_DOCUMENTO` ·
`RECLAMO_SERVICIO` · `OTRO`

### Doble motor

| Motor | Cuándo |
|---|---|
| **LLM** (Gemma) | Por defecto. Confianza 0.9 |
| **Reglas por palabra clave** | Si no hay backend o la respuesta no es válida |

**Validación estricta:** al LLM se le pide **solo un número** de una lista
cerrada, y la respuesta se valida contra esa lista. Nunca se confía en el texto
crudo.

### Lo más importante: el traspaso a Recaudo

Cada correo clasificado como `CONFIRMACION_PAGO` **se contrasta contra lo que
Recaudo ya sabe** de ese cliente. Ahí se cierra el ciclo entre dos agentes
([ver 9.1](#91-el-orquestador-agente-supervisor)).

### Resultados

10 correos procesados · **4 confirmaciones de pago** · 3 reclamos de monto ·
2 solicitudes de documento · 1 reclamo de servicio.

---

## 9.6 Módulos de apoyo

| Módulo | Función |
|---|---|
| `agentes/explicador.py` | Redacta con el LLM el motivo por el que un caso se escaló. Cae a plantilla sin backend |
| `agentes/correos.py` | Corpus de correos sintéticos para la demo |
| `contrato.py` | **La frontera con los sistemas de Integratel.** Declara qué columnas necesita cada tabla y para qué; autodetecta formatos de fecha, incluido el mixto entre AMDOCS e ISIS |
| `datos.py` | Carga y normalización, con soporte de alias de columnas |
| `auditoria.py` | Muestreo de control y su **poder de detección** |
| `procedencia.py` | Las cinco pruebas forenses sobre el dataset |
| `torre.py` | Genera `torre.html`, la interfaz completa |

---

# 10. El puesto humano

## 10.1 El principio de diseño

> **La persona confirma, no calcula.**

Cada caso llega con la propuesta hecha, la suma ya resuelta y el motivo escrito
en una frase. El operador no abre otro sistema para verificar.

## 10.2 La interfaz

**Un solo archivo: `torre.html`.** Doble clic, sin servidor, sin internet, sin
instalar nada. Se puede enviar por correo tal cual.

| Pestaña | Trabajo | Quién · cada cuánto |
|---|---|---|
| **Resumen** | Cómo va todo, el desglose del trabajo, qué requiere atención | Todos · al entrar |
| **Asignar depósitos** | Buscar empresa y resolver sus casos | Analista · a diario |
| **Cartera** | Fuga de ingresos, riesgo de impago, correos | Jefatura · semanal |
| **Auditar** | Revisar muestra de lo aplicado automáticamente | Contraloría · semanal |
| **Registro** | Todo lo decidido con hora y motivo · descargas | Contraloría · al cerrar |

**Priorización por urgencia.** La lista de las 440 empresas con casos pendientes
se ordena poniendo primero a quienes **escribieron diciendo que pagaron**, luego
a los de **riesgo alto de impago**, luego los de mayor monto.

## 10.3 La auditoría

**No son casos sospechosos** — son justamente aquellos de los que el sistema
estaba **seguro**. Se revisa una muestra de lo que se aplicó sin que nadie lo
mirara, porque eso es lo único que nadie más va a revisar.

### El poder de detección de la muestra, medido

| Si la tasa real de error fuera… | La muestra lo detecta |
|---|---|
| 2% | 48% de las veces |
| **5%** | **81%** |
| 10% | 97% |

> **Honestidad sobre el instrumento:** la muestra sirve para **cachear que algo se
> rompió** (≥5% se detecta 4 de cada 5 veces), **no** para confirmar la tasa base.
> Eso lo hace el backtest sobre el ground truth.

## 10.4 Trazabilidad

Toda decisión queda registrada con **hora, autor y motivo**, y es **reversible**.
El registro se descarga en CSV.

---

# 11. Metodología de medición

## 11.1 El principio: esconder la respuesta

Para cada evento (cliente + día) le damos al motor **solo lo que tendría en
producción**:

- el monto total depositado
- las facturas del cliente abiertas a esa fecha

Y comparamos su propuesta contra la respuesta escondida.

> **Por qué importa.** Si dejáramos `FACTURA_AFECTADA` visible, el número saldría
> más alto — pero estaríamos midiendo el trabajo manual que queremos reemplazar,
> no la capacidad del sistema.

## 11.2 Dos métricas distintas que conviene no mezclar

| Métrica | Qué mide | Valor |
|---|---|---|
| **STP** | Cuántos depósitos se aplican **solos** (una única solución exacta) | **70.6%** |
| **Precisión de la propuesta** | Cuántas propuestas aciertan, **incluidas las que van a revisión** | **78.4%** |

## 11.3 El techo alcanzable

Un diagnóstico que separa el límite del algoritmo del límite de los datos: si
alguna factura de la respuesta no está entre las candidatas, **ningún** solver
puede acertar.

| Tipo de pago | Evaluables | Techo alcanzable |
|---|---|---|
| Agrupados | 586 | **87.0%** (76 con facturas fuera del universo) |
| Simples | 1,636 | **99.9%** (1 fuera del universo) |

## 11.4 Separación temporal

Para todo lo aprendido: **entrenar con junio, evaluar con julio**. Imita el
despliegue real y evita el optimismo de una partición aleatoria.

## 11.5 Reproducibilidad

**Cada cifra de este documento tiene un comando que la produce:**

| Afirmación | Comando |
|---|---|
| El 70.6% y la precisión | `python backtest.py` |
| Las cuatro colas y la carga humana | `python triaje.py` |
| El modelo entrenado y su ablación | `python asignador.py` |
| Que el LLM pierde | `python desambiguacion.py` |
| Que CP-SAT pierde | `python asignacion.py` |
| Qué es artefacto del generador | `python procedencia.py` |
| La calibración de tolerancia y ventana | `python barrido.py` |
| Que corre sobre otros datos | `python contrato.py <ruta>` |

---

# 12. Resultados

## 12.1 Recaudo — el núcleo

| Indicador | Valor |
|---|---|
| Depósitos procesados | 2,283 |
| **Aplicados sin intervención** | **1,612 · 70.6%** |
| Monto aplicado solo | S/ 194,482.48 |
| **Tasa de error en la banda automática** | **1 de 1,596 · 0.06%** |
| En cola de confirmar | 128 |
| En cola de pago a cuenta | 322 |
| En cola de investigar | 221 |

## 12.2 La carga humana

| | Antes de conectar el modelo | Ahora |
|---|---|---|
| Minutos por día hábil | 34.2 | **18.8** |
| FTE | 0.081 | **0.045** |

**Desglose:**

| Grupo | Casos | Min/día |
|---|---|---|
| Aplicado solo | 1,612 | 0.0 |
| Elegir entre opciones | 128 | 1.0 |
| Pago a cuenta | 322 | 7.5 |
| Sin calce exacto | 221 | 10.3 |
| **Total** | **2,283** | **18.8** |

> Los segundos por caso son **supuestos de diseño**, no cronometrados con un
> operador real. Están en una sola constante del código; cronometrar y ajustarla
> recalcula el personal en todos los reportes.

## 12.3 Los otros tres agentes

| Agente | Resultados |
|---|---|
| **Facturación** | 79 clientes con fuga · 1 nunca facturado · S/ 22,956.50 de impacto · 5.83% tasa de nota de crédito |
| **BI** | 4 clientes en riesgo alto (S/ 30,157.14) · deuda total S/ 74,822.43 · concentración en 0-30 días |
| **Cobranza** | 10 correos · 4 confirmaciones de pago detectadas y traspasadas a Recaudo |

## 12.4 Los experimentos que perdieron

Los reportamos porque **explican por qué el sistema es liviano**:

| Hipótesis | Resultado |
|---|---|
| Un LLM elige mejor entre combinaciones ambiguas | **−7.4 pts** (66.7% vs 74.1%) |
| Un modelo entrenado supera a la heurística en la cola *confirmar* | **empate** (67.5% ambos) |
| Asignación global óptima con CP-SAT | **−12.9 pts** (62.5% vs 75.4%) |
| La confianza del modelo sirve como puerta de auto-aplicación | **invertida** — 77.8% al margen 0.30, 47.1% al 0.90 |

### El hallazgo más interesante

En la cola *confirmar*, el modelo entrenado asignó **0.741 de importancia** a
`dias_vto_max`. **Aprendiendo desde cero, redescubrió la regla de negocio** que la
heurística ya codificaba: la cercanía al vencimiento.

Misma señal, mismo resultado. **Reemplazar una regla que funciona por un modelo
que la iguala no aporta nada** — y sí quita auditabilidad. Por eso ahí no está
conectado.

---

# 13. Comparación con cómo lo hacen otras empresas

## 13.1 Punto por punto

| Dimensión | HighRadius / SAP / Sidetrade | SON-IA |
|---|---|---|
| **Motor de matching** | Propietario, opaco | Algoritmo exacto **auditable línea por línea** |
| **Aprendizaje** | Por cliente, sobre años de historial | Global; por cliente cuando haya historial |
| **Dónde corren los datos** | Nube del proveedor | **On-premise** — no salen de la red |
| **Modelo de costo** | Licencia anual + implantación | **Cero licencias**, software abierto |
| **Tiempo a producción** | Meses | Semanas (limitado por integración, no por el algoritmo) |
| **Alcance** | Cash application | Cash application **+ facturación + cobranza + BI coordinados** |
| **Explicabilidad al operador** | Puntaje de confianza | Frase en lenguaje natural, generada localmente |
| **STP reportado** | 80% piso / 95% clase mundial | **70.6%** sobre el dataset del reto |

## 13.2 Lectura honesta de esa última fila

**No afirmamos ser mejores que HighRadius.** Están en 80-95% con años de
historial por cliente y equipos dedicados; nosotros en 70.6% con **dos meses de
datos sintéticos**.

Lo que sí afirmamos:

1. El **mecanismo** es el mismo que usa la industria.
2. La **brecha hacia el 95% es de datos, no de arquitectura** — y esos datos
   Integratel ya los tiene.
3. Corre **dentro de su infraestructura, sin licencias**, que es algo que ninguna
   de esas plataformas ofrece.

## 13.3 Lo que tomamos de la industria y lo que aportamos

| De la industria | Nuestro aporte |
|---|---|
| La categoría, la métrica STP y la validación de que el problema tiene solución | La **formulación por factura** para los casos sin calce exacto |
| El uso de ML sobre el historial de remesas | **Medir cada frontera** en vez de suponerla — incluidos los tres experimentos que perdimos |
| La arquitectura de colas con revisión humana | El **bucle de realimentación** desde el trabajo del operador |
| — | El **análisis de procedencia** que separa hallazgo de negocio de artefacto del generador |

---

# 14. Implementación: costo, requisitos y plazos

> **Advertencia:** las cifras de esta sección son **órdenes de magnitud**
> fundamentados en la arquitectura construida, no una cotización. El componente
> dominante —la integración— depende de los sistemas de Integratel, que no
> conocemos.

## 14.1 Costo de software: cero

| Componente | Licencia |
|---|---|
| Python, pandas, NumPy | Libre (BSD) |
| scikit-learn | Libre (BSD) |
| Ollama + Gemma 3 | Libre |
| El código de SON-IA | Del proyecto |

**No hay ninguna licencia que renovar.** Este es el punto donde la diferencia con
una plataforma comercial es de órdenes de magnitud, no de porcentajes.

## 14.2 Costo de infraestructura

| Escenario | Hardware | Costo aproximado |
|---|---|---|
| **Mínimo** | Una laptop corporativa existente. Sin GPU el LLM cae a plantillas o corre lento | **S/ 0** (ya lo tienen) |
| **Recomendado** | Un servidor con GPU de 12-16 GB para que Gemma corra completo en tarjeta | US$ 1,500 – 3,000 por única vez |
| **Alternativa** | VM en la nube privada de Movistar | Según su tarifa interna |

**Cómputo recurrente:** ≈ US$ 10/mes equivalente. Y **no crece con el volumen de
depósitos** — crece solo con los casos difíciles, que son los que consultan al LLM.

## 14.3 El costo real: la integración

Esto es trabajo de sistemas y es donde está el 90% del esfuerzo:

| Frente | Esfuerzo estimado | Dificultad |
|---|---|---|
| **Lectura** — conectores a AMDOCS e ISIS para las seis tablas | 2 – 4 semanas-persona | Media |
| **Escritura** — aplicar la conciliación de vuelta en el ERP | 3 – 6 semanas-persona | **Alta** ← el punto crítico |
| Despliegue e infraestructura | 1 – 2 semanas-persona | Baja |
| Operación en paralelo (modo sombra) | 4 – 8 semanas calendario, bajo esfuerzo | Baja |
| Capacitación de usuarios | 2 – 3 días | Baja |

**Total estimado: 6 – 12 semanas-persona de TI, en un calendario de 3 a 4 meses**
contando la operación en paralelo.

> **La escritura de vuelta es el punto crítico.** Leer datos es fácil; aplicar
> asientos contra un ERP en producción exige permisos, control de duplicados,
> reversibilidad y visto bueno de Contabilidad. Ver [sección 15](#15-dificultad-y-riesgo).

## 14.4 Costo de operación

| Concepto | Valor |
|---|---|
| Analista revisando la cola | **20 minutos/día** — 0.045 FTE |
| Contraloría auditando la muestra | ~15 minutos/semana |
| Reentrenamiento del modelo | Un comando, mensual o trimestral |

## 14.5 Qué necesitamos de Integratel

1. **Lectura** de las seis tablas (o sus equivalentes en AMDOCS / ISIS).
2. **El histórico de `FACTURA_AFECTADA`.** Aquí el modelo aprendió de dos meses;
   ustedes tienen años. Es lo que habilita aprender el comportamiento **por
   cliente**, que es donde esta categoría llega al 95%.
3. **Un analista, 20 minutos al día.**
4. **Decisión de Contabilidad** sobre el alcance de la escritura automática.

## 14.6 Comparación de costo total

| | Plataforma comercial | SON-IA |
|---|---|---|
| Licencia | Anual, recurrente | **S/ 0** |
| Implantación | Meses, con consultores del proveedor | Semanas, con TI interno |
| Infraestructura | Nube del proveedor | Suya |
| Costo marginal por volumen | Suele escalar con transacciones | **Casi plano** |

---

# 15. Dificultad y riesgo

## 15.1 Dificultad por componente

| Componente | Dificultad | Estado |
|---|---|---|
| Motor determinista | **Media** — el algoritmo es conocido; las decisiones de ingeniería (céntimos, saldo, ventana) son lo difícil | ✅ Construido y medido |
| Modelo entrenado | **Media** | ✅ Construido, medido y con ablación |
| Integración del LLM | **Baja** | ✅ Funcionando, con backend intercambiable |
| Interfaz de operación | **Baja-Media** | ✅ Construida |
| **Lectura desde AMDOCS/ISIS** | **Media** | ⬜ Pendiente — `contrato.py` deja la frontera lista |
| **Escritura de vuelta al ERP** | **Alta** | ⬜ Pendiente |
| Emisión automática de facturas | **Alta** | ❌ Fuera de alcance declarado |

## 15.2 Registro de riesgos

### 🔴 Riesgo alto

**1 · El número no transfiere igual a datos reales**

- *Qué es:* el 70.6% y el 96.6% se midieron sobre un dataset **sintético**. La
  distribución de casos difíciles real puede ser distinta.
- *Probabilidad:* Alta · *Impacto:* Medio
- *Mitigación:* lo que transfiere es **la metodología**, no la cifra. Correr
  `backtest.py` sobre datos reales da el número verdadero **antes** de desplegar
  nada. Y `procedencia.py` ya identificó qué patrones son artefactos.

**2 · Escritura de vuelta al ERP**

- *Qué es:* aplicar una conciliación equivocada en producción tiene consecuencias
  contables reales.
- *Probabilidad:* Media · *Impacto:* **Alto**
- *Mitigación:* (a) **modo sombra** — el sistema propone y un humano aplica,
  durante 4-8 semanas; (b) toda decisión reversible y registrada; (c) tolerancia
  en S/ 0.00, la configuración más conservadora; (d) auditoría semanal.

### 🟡 Riesgo medio

**3 · El modelo aprende los sesgos del operador**

- *Qué es:* el bucle de realimentación entrena con decisiones humanas, que pueden
  estar mal.
- *Mitigación:* la auditoría semanal mantiene limpia la fuente. El modo sombra
  detecta divergencias antes de que se consoliden.

**4 · Deriva del modelo**

- *Qué es:* si cambia el comportamiento de pago de los clientes, el modelo se
  degrada silenciosamente.
- *Mitigación:* reentrenamiento periódico con un comando; el modo sombra actúa
  como monitor permanente.

**5 · Adopción por parte del operador**

- *Qué es:* si el analista no confía en la propuesta, la ignora y no hay ahorro.
- *Mitigación:* cada caso llega con su **motivo escrito** y su nivel de confianza;
  nada es una caja negra. La interfaz nunca dice «100% de confianza».

**6 · Calidad y consistencia de los datos fuente**

- *Qué es:* `COD_CUENTA` y el RUC ya mostraron inconsistencias de anonimización;
  las fechas vienen en formatos mezclados entre AMDOCS e ISIS.
- *Mitigación:* `contrato.py` valida columna por columna y autodetecta formatos,
  incluido el mixto. Falla ruidosamente, no silenciosamente.

### 🟢 Riesgo bajo

**7 · Dependencia del LLM** — si Ollama no corre, el sistema cae a plantillas y
sigue funcionando. Los números no dependen del modelo de lenguaje.

**8 · Escalabilidad** — el solver es milisegundos por depósito. El volumen no es
un problema.

## 15.3 La estrategia de despliegue que reduce casi todo el riesgo

```
Fase 1 · Validación         → correr backtest.py sobre datos reales
  (2 semanas)                 Salida: el número verdadero, antes de invertir

Fase 2 · Lectura            → conectores a AMDOCS/ISIS
  (3-4 semanas)               El sistema corre en paralelo a la operación

Fase 3 · Modo sombra        → propone; el analista sigue aplicando a mano
  (4-8 semanas)               Se mide la concordancia día a día

Fase 4 · Escritura acotada  → auto-aplicar SOLO la banda de solución única
  (2-4 semanas)               Con reversibilidad y auditoría semanal

Fase 5 · Ampliación         → según lo que muestren los indicadores
```

**Ninguna fase compromete la siguiente.** Si la fase 1 muestra que el número no
transfiere, se detiene ahí habiendo gastado dos semanas.

---

# 16. Limitaciones honestas

**1 · No emitimos facturas.** La ficha describe un flujo de tres momentos y
nosotros cubrimos a fondo el tercero (rebaja post-pago) y parcialmente el primero
(detectamos qué no se está facturando). La **ejecución automatizada de la
emisión** requiere integración de escritura con AMDOCS e ISIS.

**2 · El dataset es sintético.** Toda cifra describe el comportamiento del motor
sobre estos datos, no la operación de Integratel.

**3 · No conocemos su línea base.** No podemos afirmar cuánto mejora respecto a
hoy porque no sabemos en qué porcentaje de STP está Integratel.

**4 · Los tiempos por caso son supuestos.** Los 20/60/120 segundos son estimación
de diseño, no cronometraje con un operador real.

**5 · El aprendizaje por cliente no es demostrable aquí.** La mediana es de 2
eventos por cliente y solo el 4.4% llega a 5. Con datos reales de varios años, la
misma arquitectura admite el corte individual.

**6 · Probamos un LLM de 12B local**, no «los LLM en general». El arnés queda
montado para repetir la comparación con otro modelo.

## Tres cosas que no diremos nunca

1. **«Integratel está en X% de STP»** — no lo sabemos.
2. **«Detectamos S/ 106,289 de cobros sin factura»** — es un artefacto del
   generador, ya retractado.
3. **«El 5.8% de los pagos llega adelantado»** — eso describe al generador, no al
   negocio.

---

# 17. Hoja de ruta

## Inmediato — validación con datos reales

| Acción | Comando |
|---|---|
| Validar el contrato de datos | `python contrato.py <ruta>` |
| Medir el STP verdadero | `python backtest.py` |
| Reentrenar con su historial | `python asignador.py --datos <ruta>` |
| Regenerar la interfaz | `python torre.py` |

## Corto plazo — lo que habilita el histórico real

- **Aprendizaje por cliente.** «Esta empresa paga por lotes los martes», «esa otra
  descuenta retenciones del 3%». Es lo que HighRadius explota y es donde está la
  brecha hacia el 95%.
- **Predicción de deducciones.** Con retenciones y detracciones reales,
  aprenderlas por cliente convierte casos de *investigar* en calces exactos.
- **Recalibración de la ventana de suspenso** contra el comportamiento verdadero.

## Mediano plazo

- **Escritura de vuelta al ERP**, por fases.
- **Cobranza proactiva:** redactar el borrador de respuesta al cliente que
  escribe «ya pagué» — el sistema ya sabe la respuesta, el LLM solo la escribe.
- **Cerrar el primer momento del flujo:** asesoría previa a la emisión.

---

# 18. Anexos

## 18.1 Mapa de archivos

```
sonia/
├── torre.html              ← LO ÚNICO QUE SE ABRE
├── torre.py                genera la interfaz
│
├── agentes/
│   ├── recaudo.py          conciliación · el núcleo
│   ├── facturacion.py      fuga de ingresos y calidad
│   ├── cobranza.py         clasificación de correos
│   ├── bi.py               PCD, aging y priorización
│   ├── explicador.py       redacción de motivos con LLM
│   └── correos.py          corpus de demo
│
├── orquestador.py          el agente supervisor
│
├── solver.py               subset-sum meet-in-the-middle
├── asignador.py            modelo entrenado (capa 2)
├── realimentacion.py       bucle de aprendizaje y modo sombra
├── llm.py                  capa de lenguaje intercambiable
│
├── contrato.py             frontera con los sistemas de Integratel
├── datos.py                carga y normalización
│
├── backtest.py             medición contra ground truth
├── triaje.py               desglose de colas y carga humana
├── aprendizaje.py          experimento: ML sobre combinaciones
├── asignacion.py           experimento: CP-SAT global
├── desambiguacion.py       experimento: LLM eligiendo
├── procedencia.py          análisis forense del dataset
├── auditoria.py            muestreo y poder de detección
├── barrido.py              calibración de tolerancia y ventana
├── benchmark.py            posicionamiento contra la industria
├── diagnostico.py          análisis del universo de candidatas
└── verificar.py            verificación de cifras del contexto
```

## 18.2 Glosario

| Término | Significado |
|---|---|
| **STP** | *Straight-Through Processing* — % de pagos aplicados sin intervención humana |
| **Cash application** | Aplicar los pagos recibidos a las facturas que corresponden |
| **Order-to-cash (O2C)** | El ciclo desde el pedido hasta el cobro |
| **Subset-sum** | Problema de hallar un subconjunto que sume un valor dado. NP-completo |
| **Meet-in-the-middle** | Técnica que parte el problema en dos mitades para bajar la complejidad |
| **Gradient boosting** | Familia de modelos que combina árboles de decisión secuencialmente |
| **Modo sombra** | El modelo predice en paralelo sin autoridad, para medirlo antes de confiarle decisiones |
| **Ablación** | Quitar un componente para medir cuánto aportaba |
| **PCD** | Provisión de cobranza dudosa |
| **Aging** | Antigüedad de la deuda por tramos |
| **FTE** | *Full-Time Equivalent* — una persona a tiempo completo |
| **Ventana de suspenso** | Plazo en que se acepta un pago que llegó antes de su factura |

## 18.3 Referencias

**Académicas**

1. Horowitz, E. & Sahni, S. (1974). *Computing Partitions with Applications to
   the Knapsack Problem*. Journal of the ACM, 21(2), 277-292.
2. Friedman, J.H. (2001). *Greedy Function Approximation: A Gradient Boosting
   Machine*. The Annals of Statistics, 29(5), 1189-1232.
3. Chow, C.K. (1970). *On Optimum Recognition Error and Reject Tradeoff*. IEEE
   Transactions on Information Theory, 16(1), 41-46.
4. Burges, C., Ragno, R. & Le, Q. (2006). *Learning to Rank with Nonsmooth Cost
   Functions*. NIPS.
5. Pedregosa, F. et al. (2011). *Scikit-learn: Machine Learning in Python*.
   JMLR, 12, 2825-2830.

**De industria** *(publicadas por proveedores — no investigación independiente)*

6. HighRadius — casos de cash application automation, incluido L'Oréal.
7. SAP Cash Application — documentación de producto.
8. Sidetrade, Serrala — material de posicionamiento O2C.

**Del reto**

9. Ficha oficial del Desafío SON-IA, Movistar × Universidad de Lima.
10. `CONTEXTO_RETO3_SONIA.md` — análisis del contexto y los datos entregados.

## 18.4 Documentos complementarios

| Documento | Contenido |
|---|---|
| `README.md` | Visión general y resultados |
| `ARQUITECTURA.md` | Detalle de diseño y decisiones técnicas |
| `MANUAL.md` | Cómo usar el sistema, comando por comando |
| `PITCH_3MIN.md` | Guion de presentación cronometrado |
| **`DOCUMENTO_TECNICO.md`** | **Este documento** |

---

<sub>Todas las cifras de este documento son reproducibles con los comandos
indicados en la sección 11.5, sobre los datos entregados por los organizadores.</sub>
