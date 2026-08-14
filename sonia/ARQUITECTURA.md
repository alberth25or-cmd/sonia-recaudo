# Arquitectura — cómo funciona y por qué está hecho así

Este documento explica los métodos. El [README](README.md) dice qué hace el sistema
y el [MANUAL](MANUAL.md) cómo usarlo.

---

## 1. El problema no es uno, son cuatro

Lo que parece "conciliar pagos" son cuatro problemas distintos, cada uno con su
nombre formal y su solución conocida. Separarlos es la decisión de diseño más
importante del proyecto, porque cada uno pide una herramienta diferente.

| Sub-problema | Nombre formal | Cómo lo resolvemos |
|---|---|---|
| ¿Este cliente es el mismo que aquel? | Record linkage | No hace falta: `RAZON_SOCIAL` es llave exacta (3,383 de 3,383) |
| ¿Qué facturas suman este monto? | Subset-sum | Algoritmo exacto, `solver.py` |
| ¿Cuándo decido solo y cuándo escalo? | Selective classification | Cuatro colas por tipo de incertidumbre |
| ¿Cómo le explico esto a un humano? | Generación de lenguaje | Modelo local, `llm.py` |

**El error que evita esta separación:** tratarlo como un solo problema y lanzarle
un modelo de IA encima. Eso produce un sistema que a veces acierta y nunca puedes
auditar.

---

## 2. El núcleo: subset-sum exacto

### El problema

Llega un depósito de S/ 6,297.10 de un cliente que tiene 20 facturas abiertas.
¿Cuáles pagó? Formalmente: encontrar los subconjuntos cuya suma sea el depósito.

### Por qué no se le pregunta a un modelo

Con 20 facturas hay 2²⁰ ≈ **1,048,576 combinaciones**. Un LLM no las enumera:
estima. Y estimando produce respuestas que suenan razonables, no son
reproducibles, y no se pueden auditar. Sobre dinero eso es inaceptable.

Es un problema de aritmética combinatoria, y la aritmética se resuelve con código.

### Cómo lo resolvemos: meet-in-the-middle

Enumerar el millón de combinaciones es viable pero se vuelve inviable rápido
(2³⁰ ya es mil millones). El truco:

1. Partir las facturas en dos mitades, A y B
2. Calcular **todas** las sumas de A (2¹⁵ = 32,768) y todas las de B
3. Ordenar las de B
4. Para cada suma `a` de A, buscar por bisección `deposito − a` en B

Pasas de 2³⁰ operaciones a 2 × 2¹⁵ más búsquedas logarítmicas. **De mil millones
a sesenta y cinco mil.** Corre en milisegundos.

```python
# solver.py — el corazón, en cuatro líneas conceptuales
izq = todas_las_sumas(facturas[:mitad])
der = todas_las_sumas(facturas[mitad:])   # ordenadas
for suma_izq, ids in izq:
    falta = deposito - suma_izq
    # bisección: ¿existe un subconjunto de B que sume exactamente 'falta'?
```

### Dos detalles que parecen menores y no lo son

**Todo en céntimos enteros.** Los importes se convierten a `int` antes de sumar.
Con `float`, `0.1 + 0.2 != 0.3` y un calce exacto se pierde por error de
representación. Sobre dinero eso es un bug silencioso.

**El monto candidato es el SALDO, no el total.** 169 facturas del dataset se pagan
en cuotas. Si buscas combinaciones que sumen el *total* de facturas parcialmente
pagadas, no encuentras nada. Hay que restar lo ya pagado antes de esa fecha.

---

## 3. Construir el universo de candidatas

Antes de resolver hay que decidir **contra qué facturas** se busca. Esa decisión
pesa tanto como el algoritmo.

```
facturas del cliente
    │
    ├── emitidas después de la ventana de suspenso  → fuera
    ├── ya saldadas antes de esta fecha             → fuera
    └── el resto, con su SALDO como monto           → candidatas
```

### La ventana de suspenso

El 5.8% de los pagos llega **antes** de que su factura se emita. Filtrando por
fecha de emisión, esas facturas quedan fuera y se rompen 161 eventos agrupados.

En *cash application* real esto tiene nombre: el depósito entra en una **cuenta en
suspenso** y se aplica cuando la factura aparece. Modelamos eso con una ventana de
10 días hacia adelante.

**El valor no se eligió a ojo.** `barrido.py` prueba 0, 5, 10, 15, 20, 30, 45 y 61
días y mide el resultado neto: ampliar sube el techo alcanzable pero mete
candidatas espurias que generan combinaciones falsas. 10 es el óptimo medido.

> Sobre datos sintéticos ese desfase se concentra en 9–15 días, lo que parece
> frontera de ciclo del generador más que anticipo real. La ventana es necesaria
> para procesar *estos* datos; en producción habría que recalibrarla.

---

## 4. Elegir cuando hay varias respuestas válidas

A veces el solver encuentra **varias** combinaciones que suman exacto. Todas son
matemáticamente correctas; solo una ocurrió.

Ejemplo real: `CLIENT_00002` depositó S/ 80.43 y tiene dos facturas de S/ 80.43
exactas. Una venció hace 4 días, otra vence en 26.

### La heurística, y por qué esos criterios

```python
def clave(solucion):
    cercania = media(|vencimiento − fecha_pago|)   # criterio dominante
    return (cercania, cuántas_facturas, más_antigua)
```

1. **Cercanía al vencimiento.** La mediana de pago cae 1 día antes del vencimiento:
   las empresas pagan lo que está por vencer, no lo que vence en un mes.
2. **Menos facturas.** El pago típico agrupa pocas.
3. **FIFO.** Imputar primero lo más antiguo es el estándar en cobranza.

No son reglas inventadas: son criterios de negocio que un analista de recaudo
reconoce, y por eso el operador puede auditar la propuesta.

---

## 5. Las cuatro colas: escalamiento por tipo de incertidumbre

Aquí está la diferencia con un sistema que usa un umbral de confianza. Un umbral
dice *"85%, aplícalo"* — un número sin significado. Nosotros clasificamos por
**qué tipo de incertidumbre** hay, que es información accionable.

| Cola | Condición | Qué significa | Quién resuelve |
|---|---|---|---|
| **AUTO** | Exactamente 1 solución | No hay ambigüedad | Nadie — se aplica |
| **CONFIRMAR** | Varias soluciones | Demasiadas respuestas válidas | Humano elige de una lista |
| **HIPOTESIS** | Ninguna, pero el depósito cabe en una factura | Probable pago parcial | Humano aprueba |
| **INVESTIGAR** | Ninguna, y nada lo absorbe | Falta información | Humano investiga |

**Lo importante:** el ML no entra "donde el solver falla". Donde el solver falla de
verdad (colas 3 y 4) no hay candidatas que puntuar — un ranker necesita una lista
que ordenar. El ML competiría en la cola 2, y ahí lo medimos y empató.

### La tolerancia de calce, calibrada

Cuánta diferencia se acepta como "calza" es una perilla con consecuencias medidas:

| Tolerancia | Resuelve solo | **Se equivoca** |
|---|---|---|
| S/ 0.00 | 75.4% | **0.06%** |
| S/ 1.00 | 78.4% | 2.8% |
| S/ 5.00 | 79.3% | 7.5% |

Opera en **S/ 0.00**. Aflojarla compra tres puntos de cobertura a cambio de
multiplicar el error por 45. Sobre dinero, equivocarse cuesta más que escalar.

---

## 6. Cómo se mide: esconder la respuesta

Este es el método que sostiene todas las cifras, y es lo que distingue una
medición de una demo.

`PAGOS.FACTURA_AFECTADA` dice qué factura paga cada pago. **Esa columna es la
respuesta** — es el trabajo manual que un analista ya hizo. Usarla como insumo
mide la calidad del dato, no la capacidad del sistema.

```
Simulación (backtest.py):
    1. Agrupar los pagos en depósitos: cliente + día + monto
    2. ESCONDER FACTURA_AFECTADA
    3. Darle al motor solo lo que tendría en producción
    4. Comparar su propuesta contra la respuesta escondida
```

Además se mide el **techo alcanzable**: si la factura correcta ni siquiera está
entre las candidatas, ningún algoritmo puede acertar. Eso separa el límite del
universo de candidatas del límite del algoritmo — sin ese diagnóstico habríamos
optimizado el ranking cuando el problema estaba en la construcción del universo.

---

## 7. Lo que probamos y descartamos

Tres hipótesis razonables, tres mediciones, tres rechazos. El método siempre el
mismo: implementar, medir contra ground truth, comparar con lo que ya hay.

| Hipótesis | Cómo se probó | Resultado |
|---|---|---|
| Un LLM elige mejor entre ambiguas | 108 casos, Gemma 3 12B vs heurística | **−7.4 pts** (66.7% vs 74.1%) |
| Un modelo entrenado supera la heurística | Gradient boosting, split temporal junio→julio | **Empate** (67.5% ambos) |
| La asignación global le gana al secuencial | CP-SAT por cliente, 2,222 eventos | **−12.9 pts** (62.5% vs 75.4%) |

**Por qué falló cada una:**

- **El LLM** reconstruye desde el prompt un criterio que la heurística ya tiene
  codificado exactamente. Reconstruir es peor que tener.
- **El modelo entrenado** asignó 0.741 de importancia a `dias_vto_max` —
  redescubrió la regla de vencimiento. Mismo señal, mismo resultado. No hay más
  señal que extraer: la mediana es 2 eventos por cliente.
- **La asignación global** maximiza *depósitos resueltos*, que no es lo mismo que
  *acertar*. Encuentra combinaciones que cuadran el conjunto pero no ocurrieron.
  Optimalidad matemática ≠ corrección.

---

## 8. Dónde sí entra el modelo de lenguaje

Nada que decida sobre dinero pasa por un modelo. El LLM hace dos cosas donde no
hay regla que aplicar:

**Explicar.** El solver ya decidió; falta que un humano entienda la propuesta en
cinco segundos. El caso es la única fuente de verdad del prompt: el modelo
interpreta, no inventa.

**Clasificar correos.** Texto sin estructura entrando por un buzón. Ahí no hay
aritmética; hay lenguaje.

Corre **on-premise** (Ollama + Gemma 3 12B) con backend intercambiable. Sin modelo,
todo funciona con plantillas y reglas: la demo nunca depende de la red.

---

## 9. El recorrido de un depósito

```
   Extracto bancario:  CLIENT_00756 · S/ 6,297.10 · 04/06/2026
            │
            ▼
   ┌──────────────────────────────────────────┐
   │ Construir candidatas                     │
   │   facturas del cliente                   │
   │   − emitidas fuera de la ventana         │
   │   − ya saldadas                          │
   │   = 12 facturas con su SALDO             │
   └──────────────────┬───────────────────────┘
                      ▼
   ┌──────────────────────────────────────────┐
   │ Solver — meet-in-the-middle              │
   │   2^6 + 2^6 sumas, bisección             │
   │   → 1 combinación exacta                 │
   └──────────────────┬───────────────────────┘
                      ▼
              ┌───────┴────────┐
         1 solución        varias / ninguna
              │                 │
              ▼                 ▼
            AUTO          cola humana
              │                 │
              │                 ▼
              │        LLM redacta el motivo
              │                 │
              │                 ▼
              │        Operador confirma (20 s)
              ▼                 ▼
        ┌─────────────────────────────┐
        │ Log de auditoría            │
        │ quién, cuándo, por qué      │
        │ reversible                  │
        └─────────────────────────────┘
                      │
                      ▼
        Muestreo del 2% semanal sobre la banda AUTO
```

---

## 10. Los cuatro agentes y el supervisor

`orquestador.py` no es un adorno: asigna, controla el resultado, escala lo que no
se resuelve solo, y **encadena a los agentes entre sí**.

```
                  SUPERVISOR
      asigna · controla · escala · mide KPIs
                      │
   ┌──────────┬───────┴───────┬──────────┐
   ▼          ▼               ▼          ▼
RECAUDO   FACTURACIÓN    COBRANZA       BI
concilia  detecta fuga   clasifica   PCD, aging,
depósitos de ingresos     correos    priorización
   ▲                          │          ▲
   └──────────────────────────┘          │
     "ya pagué" → Recaudo prioriza       │
                                          │
   Recaudo + Facturación ─────────────────┘
     BI consume sus resultados
```

**El encadenamiento real, no dibujado:**

- Cobranza detecta un correo *"ya pagué"* → busca los depósitos sin conciliar de
  ese cliente → si tiene, Recaudo prioriza el caso; si ya están aplicados, se saca
  al cliente de la ruta de cobranza para no volver a llamarlo.
- BI no relee los CSV: consume los resultados de Recaudo y Facturación. Esa
  dependencia es la coordinación que pide la ficha del reto.

Cada paso queda en el log con marca de tiempo, agente, acción y detalle.

---

## 11. La frontera con los sistemas reales

`contrato.py` declara qué columnas hacen falta y **para qué**, valida una fuente
antes de procesar, y detecta solo el formato de fecha de cada columna — incluida
`FECHA_VTO`, que mezcla `YYYY-MM-DD` (AMDOCS) y `YYYYMMDD` (ISIS) en la misma
columna.

Conectar datos reales es apuntar una ruta y, si los nombres difieren, mapearlos:

```python
datos.facturas(ruta="/export/sap/facturas.csv",
               alias={"RAZON_SOCIAL": "NOMBRE_CLIENTE"})
```

---

## En una frase

**Un algoritmo exacto resuelve la aritmética, una heurística de negocio decide
entre empates, cuatro colas clasifican la incertidumbre por tipo, un modelo de
lenguaje explica, y un humano confirma — con todo medido escondiendo la
respuesta.**
