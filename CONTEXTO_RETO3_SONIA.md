# Reto 3 — SON-IA · Documento de contexto del equipo

> **Para qué sirve este documento:** es el briefing completo del reto. Está escrito para que cualquier persona del equipo —o cualquier asistente de IA— entienda el problema, los datos y los hallazgos sin tener que revisar los archivos desde cero.
>
> **Cómo usarlo con tu IA:** pégalo completo al inicio de la conversación y dile *"este es el contexto del reto, no inventes datos fuera de aquí"*. Contiene los nombres exactos de columnas, las trampas de los datos y los números ya verificados.
>
> **Estado:** análisis exploratorio completado el 13/08/2026. Todas las cifras de este documento fueron calculadas sobre los CSV entregados y son reproducibles.

---

## 1. El reto en una página

**Nombre oficial:** SON-IA — Sinergia Operativa del Negocio · Integratel Agéntica
**Organizan:** Movistar y Universidad de Lima — Hackatón "AI Telecom Challenge"
**Empresa del caso:** Integratel, el brazo de Movistar que vende telecomunicaciones a empresas (B2B) en Perú.

### Qué piden construir

Un **equipo de agentes de IA** para el ciclo completo del ingreso: facturación, cobranzas y recaudo.

La ficha del desafío es explícita en tres puntos, y estos son los criterios que hay que cumplir sí o sí:

1. **IA agéntica** — agentes autónomos con skills especializados por proceso.
2. **Orquestación** — un agente supervisor que asigna, controla y da seguimiento a las actividades de los agentes operadores.
3. **Control de indicadores**, calidad y tiempo del servicio.

> ⚠️ **No es un chatbot ni una automatización suelta.** Lo que se evalúa es la arquitectura de equipo: varios agentes especializados + un supervisor que coordina. Una solución que resuelva bien el problema pero sin esa estructura no responde al reto.

### Los tres frentes del negocio

| Frente | Situación actual | Lo que se espera de la IA |
|---|---|---|
| **Facturación** | Validaciones manuales, revisión de múltiples archivos, coordinación entre áreas (postventa, implantación, ingeniería, comercial). Información dispersa en varios sistemas, sin trazabilidad de la oportunidad inicial. | Extraer y validar la información que arma el PxQ (precio por cantidad), preparar los formatos para el cliente, emitir sin intervención humana, y dejar trazado quién emitió, cuándo, cuánto y cuándo se pagó. |
| **Cobranzas y recaudación** | Gestión tercerizada vía correos y llamadas. **Ningún buzón está centralizado, organizado ni respondido automáticamente.** | Centralizar, controlar y analizar todas las comunicaciones con clientes, clasificándolas por tipo de mensaje —especialmente las que indican pagos— para conciliaciones, armado de ficheros de rebaja y aseguramiento de partidas bancarias. |
| **Inteligencia de negocio (BI)** | — | Análisis avanzado: hallazgo de oportunidades de recupero, provisión de cobranza dudosa, adelanto operativo de caja, quiebres con clientes, y estrategias ad-hoc para iniciar la ejecución. |

### El flujo objetivo que describe la ficha

1. **Asesoría previa a la emisión** — el agente extrae y valida la información del PxQ, prepara los formatos, los envía al cliente para su conformidad. Todo bajo criterios de auditoría, guardando registro de cada tarea. Si hay quiebres durante la ejecución, el agente **alerta al equipo de facturación**.
2. **Ejecución automatizada** — con la aprobación del cliente en la plataforma de autogestión, el agente recoge el insumo validado y emite el documento sin intervención humana. La factura se visualiza en la plataforma para que el cliente pague.
3. **Rebaja automática post-pago** — confirmado el pago, el sistema actualiza el estado del documento automáticamente, quedando todo trazado.

### Indicadores que se busca mejorar

- **Facturación:** aseguramiento de ingresos por facturación oportuna y de calidad; escalera de facturación; tiempo de disponibilidad de facturas hacia el cliente; **reducción de notas de crédito por refacturación por error operativo**.
- **Cobranzas:** ratio cobrado/facturado a 30 días; periodo medio de cobro hacia el vencimiento; provisión de cobranza dudosa (PCD).
- **Recaudo:** **tiempos de identificación de depósitos**; reducción de cuentas por cobrar en los sistemas; reducción de tiempos en conciliaciones bancarias; mejora de los algoritmos de aplicación.

### Usuarios involucrados

Facturación, Cobranzas, TI, Planificación Comercial, Control de Gestión, Contabilidad, Finanzas, Inteligencia de Negocio (BBII), Ventas y Atención al Cliente.

### Contexto técnico declarado por la empresa

Sistemas comerciales y de facturación, SQL Server, Teradata, ETLs, plataformas propias, servidores Linux y Python para RPAs.

---

## 2. El problema explicado sin tecnicismos

Integratel le factura a mil empresas cada mes y hace casi todo a mano.

**Antes de facturar,** alguien arma la cuenta de cada cliente: qué servicios tiene, a qué precio, qué descuentos le tocan. Esa información está regada en varios sistemas. Una persona los abre, los compara, pregunta por correo a otra área, espera respuesta, arma un formato, lo manda al cliente. Días. Y como es manual, sale mal: se factura de menos (fuga de ingresos), de más (el cliente reclama, hay que anular con nota de crédito y refacturar), o tarde.

**Después de facturar,** hay que cobrar. Hoy lo hace un proveedor externo mandando correos y llamando. El detalle: nadie lee el buzón donde el cliente responde. Ahí llegan mensajes mezclados —"ya pagué, adjunto voucher", "no estoy de acuerdo con el monto", "reenvíeme la factura"— sin nadie que los clasifique. Un cliente puede haber pagado hace dos semanas y seguir figurando como moroso.

**Y al final hay que cuadrar.** El dinero llega al banco como una lista de depósitos, sin etiqueta. Hay que averiguar qué depósito corresponde a qué factura de qué cliente. También a mano.

### La diferencia entre cobranza y recaudo (importante)

- **Cobranza** = perseguir al cliente para que pague. Problema de constancia y volumen.
- **Recaudo** = averiguar, después de que pagó, **de quién es la plata y a qué factura va**.

Recaudo es el más difícil porque el dinero no llega identificado. Llega un depósito de S/ 8,432 de una empresa que tiene 20 facturas abiertas y pagó una parte de varias. O paga un monto que no coincide con ninguna factura porque descontó algo que estaba reclamando. Hasta que alguien resuelva ese rompecabezas, **el cliente sigue apareciendo como moroso aunque ya pagó** — y le siguen llegando cartas de cobranza. Eso genera reclamos, cortes indebidos y una foto financiera falsa.

> 💡 **Dato del equipo de Movistar:** nos indicaron que **recaudo es el área más difícil y el mayor cuello de botella**. El análisis de datos de la sección 5 lo confirma.

---

## 3. Inventario de datos

Seis archivos CSV entregados. Todos comparten el mismo formato técnico:

- **Separador:** `|` (pipe), **no** coma.
- **Codificación:** `latin-1`. Si se lee como UTF-8 las tildes salen rotas (`Dúo` → `D�o`, `Activación` → `Activaci�n`).
- Los nombres de las empresas están anonimizados como `CLIENT_00001` … `CLIENT_01000`.

| # | Archivo | Filas | Qué contiene |
|---|---|---|---|
| 001 | `001_TBL_CLIENTES_B2B.csv` | 1,000 | Maestra de clientes con su situación ante SUNAT y ubicación |
| 002 | `002_TBL_PLANTA_FIJA_B2B.csv` | 943 | Servicios fijos: voz, internet, TV |
| 003 | `003_TBL_PLANTA_MOVIL_B2B.csv` | 1,798 | Líneas móviles, planes y permanencia |
| 004 | `004_TBL_PAGOS_B2B.csv` | 3,548 | Pagos recibidos, con la factura que afectan |
| 005 | `005_TBL_FACTURAS_B2B.csv` | 3,364 | Facturas emitidas |
| 006 | `006_TBL_NOTAS_CREDITO_B2B.csv` | 196 | Anulaciones y correcciones de facturas |

### Cómo se relacionan

```
CLIENTES (001)
    │  se une por RAZON_SOCIAL  ⚠️ (no por RUC — ver sección 4)
    ├──> PLANTA FIJA (002)   ─┐
    ├──> PLANTA MOVIL (003)  ─┤  qué le vendimos
    │                          │
    └──> FACTURAS (005) ────────┘  cuánto le cobramos
             │ NRO_DOC_FISCAL
             ├──< PAGOS (004).FACTURA_AFECTADA          cuánto pagó
             └──< NOTAS_CREDITO (006).FACTURA_AFECTADA  qué se corrigió
```

---

## 4. Diccionario de datos

### 001 — CLIENTES (1,000 filas × 9 columnas)

| Columna | Descripción | Valores / notas |
|---|---|---|
| `SEGMENTO_PAIS` | Segmento comercial | SEGMENTO_004 (926), SEGMENTO_002 (68), SEGMENTO_003 (5), SEGMENTO_001 (1) |
| `TIPO_DOCUMENTO` | Tipo de documento fiscal | Siempre `RUC` |
| `NUMERO_IDENTIFICACION_FISCAL` | RUC, 10 dígitos | ⚠️ **No usar como llave** — ver sección 5 |
| `RAZON_SOCIAL` | Nombre anonimizado | 1,000 únicos. **Esta es la llave confiable** |
| `SUNAT_ESTADO_RUC` | Estado del RUC en SUNAT | HABIDO (982), NO HABIDO (18) |
| `SUNAT_ESTADO_CONTRIBUYENTE` | Situación del contribuyente | ACTIVO (918), BAJA DE OFICIO (55), SUSPENSION TEMPORAL (22), BAJA PROV. POR OFICI (3), BAJA DEFINITIVA (2) |
| `SUNAT_DEPARTAMENTO` / `SUNAT_PROVINCIA` / `SUNAT_DISTRITO` | Ubicación | 24 departamentos, 66 provincias, 158 distritos |

> 🎯 **Señal de riesgo lista para usar:** 18 clientes NO HABIDOS y 82 con el RUC de baja o suspendido. Un cliente en esa situación tiene probabilidad de impago muy superior. Es un insumo directo para scoring de cobranza dudosa (PCD).

### 002 — PLANTA FIJA (943 filas × 23 columnas)

Cubre 553 clientes, 842 códigos de cliente y 924 cuentas.

| Columna | Descripción | Notas |
|---|---|---|
| `SEGMENTO_PAIS`, `NUMERO_IDENTIFICACION_FISCAL`, `RAZON_SOCIAL` | Identificación | |
| `COD_CLIENTE`, `COD_CUENTA` | Códigos internos | `COD_CUENTA` cruza con facturas y pagos |
| `CICLO` | Ciclo de facturación | 8 ciclos distintos. **Clave para predecir cuándo se emite cada factura** |
| `FECHAALTA` | Alta del servicio | Formato `YYYY-MM-DD HH:MM:SS`. Hay fechas absurdas: la más antigua es 1967 |
| `STATUS_DESC` | Estado de la cuenta | Active / otro |
| `LN_PLAN_DESC`, `LN_SUBSCRIBER_STATUS_DESC` | Línea de voz (plan y estado) | 382 nulos = sin voz |
| `INT_PLAN_DESC`, `INT_ORIGINAL_ACTIVATION_DATE`, `INT_SUBSCRIBER_STATUS_DESC` | Internet | 190 nulos. Ojo: hay fechas `1970-01-01` (valor centinela, no es real) |
| `TV_PLAN_DESC`, `TV_ORIGINAL_ACTIVATION_DATE`, `TV_TECNOLOGIA`, `TV_SERVICE_TECHNOLOGY`, `TV_SUBSCRIBER_STATUS_DESC` | Televisión | 672 nulos = sin TV. Tecnologías: DTH, otras |
| `SUB_MAIN_OFFER_DESC` | Oferta principal | 82 valores distintos |
| `SUB_MAIN_OFFER_TRIODUO` | Empaquetamiento | MonoInt, Duos BA, Trio, etc. |
| `ES_MOVISTARTOTAL` | Bandera Movistar Total | 0 / 1 |
| `DESCUENTO_PROMOCION_PRODUCTO_DESC` | Promoción vigente | 738 nulos. 62 promociones distintas |
| `DECOS_CANTIDAD` | Decodificadores TV | 679 nulos |

### 003 — PLANTA MÓVIL (1,798 filas × 19 columnas)

Cubre 426 clientes, 478 códigos de cliente y 807 cuentas. **Cada fila es una línea móvil.**

| Columna | Descripción | Notas |
|---|---|---|
| `SEGMENTO_PAIS`, `NUMERO_IDENTIFICACION_FISCAL`, `RAZON_SOCIAL` | Identificación | |
| `COD_CLIENTE`, `COD_CUENTA` | Códigos internos | 2 nulos en `COD_CUENTA` |
| `FLAG_STAFF` | Línea de personal | Siempre `N` |
| `PRODUCTO` | Tipo de producto | Movil Abierto y 4 más |
| `FECHA_ALTA` | Alta de la línea | ⚠️ Formato `DD/MM/YYYY` — **distinto al de planta fija** |
| `ESTADO_LINEA` | Estado | Activo y 2 más |
| `ESTADO_TELEFONO_RAZON` | Motivo del estado | 19 valores (Pedido de Cliente, etc.) |
| `TIPO_LINEA` | Tipo | M4 y otro |
| `PRODUCT_DESC`, `PLAN_PRINCIPAL` | Producto y plan | 192 planes distintos. 15 nulos en plan |
| `CANT_PROMOCIONES`, `PROM_DSCTO` | Promociones y descuento | 1,119 nulos = sin promoción |
| `PLAN_ROAMING_DATOS` | Roaming | 356 nulos |
| `Fecha_Inicio_Permanencia`, `Fecha_Fin_Permanencia`, `Meses_Permanencia` | Contrato de permanencia | 866 sin fecha fin. Formato `DD/MM/YYYY` |

> 🎯 **Uso para el reto:** planta fija + planta móvil = lo que el cliente *debería* estar pagando. Comparado contra lo facturado, permite detectar **fuga de ingresos** (servicio activo no facturado), que la ficha menciona explícitamente como consecuencia actual del problema.

### 004 — PAGOS (3,548 filas × 12 columnas)

| Columna | Descripción | Notas |
|---|---|---|
| `TIPO_DOCUMENTO` | Siempre `Pago` | |
| `NRO_IDENTIFICACION_FISCAL` | RUC | 🚨 **3,548 valores únicos en 3,548 filas** — es decir, un RUC distinto por fila. Está completamente aleatorizado. **Inservible** |
| `RAZON_SOCIAL` | Cliente | 1,000 únicos — coincide con la maestra. **Llave válida** |
| `COD_CLIENTE`, `COD_CUENTA` | Códigos internos | 1,258 y 1,674 únicos |
| `SISTEMA` | Sistema origen | AMDOCS (3,481), ISIS (67) |
| `FACTURA_AFECTADA` | Factura que paga | Cruza con `FACTURAS.NRO_DOC_FISCAL`. 3,372 facturas distintas |
| `FECHA_PAGO` | Fecha del pago | `YYYY-MM-DD HH:MM:SS`. Rango: **01/06/2026 al 31/07/2026** (61 días) |
| `MONEDA_FACTURA` | Moneda | PEN (3,527), **USD (21)** ⚠️ |
| `SUBTOTAL`, `IGV`, `MONTO_PAGADO` | Importes | Consistentes: subtotal + IGV = monto en el 100% de las filas |

### 005 — FACTURAS (3,364 filas × 13 columnas)

| Columna | Descripción | Notas |
|---|---|---|
| `NUMERO_IDENTIFICACION_FISCAL` | RUC | ⚠️ 999 únicos, pero inconsistente con la maestra (sección 5) |
| `RAZON_SOCIAL` | Cliente | 999 únicos. **Llave válida** |
| `COD_CLIENTE`, `COD_CUENTA` | Códigos internos | 1,257 y 1,672 únicos |
| `NRO_DOC_FISCAL` | Número de factura | 3,364 únicos, sin duplicados. Formato `XXXX-NNNNNNNNNN`. Series: S9AA (1,142), S1AA (668), S5AA (520), S3AA (413), S7AA (268), S8AA (186), S4AA (96), S300 (37) |
| `FUENTE` | Origen | FACTURACION CICLICA (3,343), FACTURACION ACICLICA (21) |
| `SISTEMA` | Sistema | AMDOCS (3,307), ISIS (57) |
| `FECHA_EMISION` | Emisión | Formato `YYYYMMDD` (siempre 8 dígitos). Rango: **18/04/2023 al 05/08/2026** |
| `FECHA_VTO` | Vencimiento | 🚨 **DOS formatos mezclados:** `YYYY-MM-DD` en AMDOCS (3,307 filas) y `YYYYMMDD` en ISIS (57 filas) |
| `MONEDA` | Moneda | PEN. **1 valor nulo** |
| `CHARGE_NET_AMOUNT`, `CHARGE_IGV_INVOICE`, `CHARGE_TOTAL_AMOUNT` | Importes | 8 filas donde neto + IGV ≠ total |

**Distribución de montos:** mínimo S/ 0.00 · mediana S/ 62.93 · promedio S/ 133.16 · máximo S/ 55,718.00
**Concentración:** los 10 clientes más grandes representan el **40.7%** del monto facturado.
**Volumen por mes de emisión:** mar-26: 14 · abr-26: 50 · may-26: 609 · **jun-26: 1,555** · **jul-26: 1,036** · ago-26: 47

### 006 — NOTAS DE CRÉDITO (196 filas × 13 columnas)

| Columna | Descripción | Notas |
|---|---|---|
| `NUMERO_IDENTIFICACION_FISCAL`, `RAZON_SOCIAL` | Cliente | 162 clientes distintos |
| `COD_CLIENTE`, `COD_CUENTA` | Códigos internos | |
| `NRO_DOC_FISCAL` | Número de la NC | 196 únicos. Serie `SJFE-` |
| `FUENTE` | Siempre `NOTA DE CREDITO` | |
| `SISTEMA` | Siempre `AMDOCS` | |
| `FACTURA_AFECTADA` | Factura que corrige | ✅ **196 de 196 cruzan** con facturas existentes |
| `FECHAEMISION` | Emisión | `YYYYMMDD`. Solo 10 fechas distintas |
| `MONEDA` | PEN | |
| `MONTO_SIN_IGV`, `SUBTOTAL`, `MONTO` | Importes | ⚠️ Nombres engañosos: `SUBTOTAL` contiene el IGV, no el subtotal. `MONTO_SIN_IGV` + `SUBTOTAL` = `MONTO` |

> 🎯 **Uso para el reto:** la ficha pide reducir las notas de crédito por refacturación por error operativo. Estas 196 NC son la línea base contra la cual medir esa mejora.

---

## 5. 🚨 Trampas de los datos — leer antes de programar

Estos hallazgos rompen cualquier análisis que se construya encima. Están verificados.

### 5.1 El RUC no sirve como llave de unión

El dato fue anonimizado archivo por archivo, de forma inconsistente:

- **450 de 999 razones sociales** tienen un RUC distinto en `FACTURAS` que en `CLIENTES`. Casi la mitad.
- En `PAGOS` es peor: hay **3,548 RUCs únicos en 3,548 filas** — un RUC diferente por cada pago. Está aleatorizado por completo.

**Consecuencia:** si unes las tablas por `NUMERO_IDENTIFICACION_FISCAL`, cruzas las facturas de una empresa con los datos de otra, y los resultados serán basura convincente.

**Solución:** unir por **`RAZON_SOCIAL`** (cruza 999/999 con la maestra) o por **`COD_CUENTA`** para el detalle de cuenta.

| Ejemplo | RUC en facturas | RUC en clientes |
|---|---|---|
| CLIENT_00887 | 2084347031 | 2002459973 |
| CLIENT_00133 | 2089275916 | 2027996349 |
| CLIENT_00212 | 2030405929 | 2033150864 |

### 5.2 Fechas en tres formatos distintos

| Campo | Archivo | Formato |
|---|---|---|
| `FECHA_EMISION` | Facturas | `YYYYMMDD` |
| `FECHA_VTO` | Facturas | **`YYYY-MM-DD` (AMDOCS) y `YYYYMMDD` (ISIS), en la misma columna** |
| `FECHA_PAGO` | Pagos | `YYYY-MM-DD HH:MM:SS` |
| `FECHAALTA` | Planta fija | `YYYY-MM-DD HH:MM:SS` |
| `FECHA_ALTA` | Planta móvil | **`DD/MM/YYYY`** |

Si se parsea mal, los días de mora salen incorrectos y todo el análisis de cobranza se cae.

### 5.3 Otros puntos a considerar

- **Codificación latin-1.** Leerlo como UTF-8 rompe todas las tildes.
- **21 pagos en USD** contra facturas registradas en PEN. No hay tipo de cambio en los datos: hay que decidir un supuesto y documentarlo.
- **1 factura sin moneda** y **8 facturas donde neto + IGV ≠ total**.
- **Fechas centinela:** `1970-01-01` en activación de internet y altas de 1967 en planta fija. No son reales.
- **Ventana temporal desbalanceada:** hay facturas desde abril 2023 pero pagos solo de junio–julio 2026. Una factura de 2023 sin pago registrado **no necesariamente está impaga** — probablemente se pagó fuera de la ventana. **Para análisis de cobranza y recaudo, acotarse a facturas emitidas en jun–jul 2026 (2,591 facturas), que es donde la foto está completa.**

---

## 6. Diagnóstico: por qué recaudo es el cuello de botella

Todas las cifras salen de cruzar `FACTURAS` × `PAGOS` × `NOTAS_CREDITO`.

### 6.1 Solo el 80% de las facturas calzan limpio

De 3,364 facturas, **2,709 tienen un pago que coincide exactamente** con el monto. El resto es trabajo manual de investigación:

| Situación | Cantidad | Monto |
|---|---|---|
| Calce exacto ✅ | 2,709 | — |
| Pago parcial (pagó menos de lo facturado) | 605 | S/ 161,485 de brecha |
| Sobrepago (pagó de más) | 8 | — |
| Sin ningún pago registrado | 57 | — |
| **Pagos que no corresponden a ninguna factura conocida** | **74** | **S/ 106,289** |

### 6.2 Las notas de crédito casi no explican los descalces

La hipótesis natural es que el cliente pagó menos porque tenía una nota de crédito a favor. **Los datos dicen que no:**

- De las 605 facturas con pago parcial, solo **69 tienen nota de crédito**.
- Y la NC deja el calce exacto en apenas **3 casos**.
- Quedan **581 facturas con S/ 159,964 de diferencia sin explicación documentada**.

Desglose de esas 581 por tamaño de la diferencia:

- **41 casos** por debajo del 1% del valor de la factura → centavos, redondeo. Automatizable con tolerancia.
- **282 casos** entre 1% y 50% → pago parcial real, requiere criterio.
- **258 casos** por encima del 50% → el cliente pagó una fracción pequeña. Requiere investigación.

Diferencia mediana: S/ 23.46. Máxima: S/ 55,718.

### 6.3 La mitad del dinero entra en pagos agrupados

Este es el hallazgo más importante para diseñar la solución:

- **634 eventos** en los que un cliente paga **varias facturas el mismo día**.
- El máximo observado: **20 facturas en un solo día** por un mismo cliente.
- Ese modo de pago mueve **S/ 189,859 de los S/ 392,837 cobrados — el 48% del dinero**.

Cada uno de esos eventos es un rompecabezas: llegó un monto, hay N facturas candidatas, y hay que decidir qué parte va a cuál. **Ahí es exactamente donde se pierde el tiempo operativo.**

Además, **169 facturas se pagan en cuotas** (hasta 4 pagos para una misma factura), lo que multiplica las combinaciones posibles.

### 6.4 El volumen es de trabajo diario continuo

- **82 pagos por día hábil** en la ventana de junio–julio 2026.
- Repartidos en **1,674 cuentas distintas**.
- Llegando desde **dos sistemas** (AMDOCS e ISIS) que ni siquiera escriben las fechas igual.

### 6.5 El problema no es que los clientes no paguen

Un matiz que conviene tener claro para no diagnosticar mal:

- La **mediana** de pago es **1 día antes del vencimiento**. La mayoría de clientes es puntual.
- Un **42.8%** paga tarde, pero el promedio (4.3 días) está inflado por una cola larga: hay facturas cobradas hasta **1,163 días después** del vencimiento.

**Conclusión:** el cuello de botella no es la voluntad de pago del cliente. Es que **la empresa no logra procesar e identificar a tiempo el dinero que sí le están pagando.**

### 6.6 Benchmark internacional — dónde estamos parados

Esto no es una categoría nueva. En el primer mundo se llama **cash application automation** (dentro de *order-to-cash*), y tiene proveedores maduros: **HighRadius** (EE.UU., líder), **SAP Cash Application** (Alemania), **Sidetrade** (Francia, con su agente de IA "Aimee"), **Serrala**, **Billtrust**, **Esker**, **Blackline**.

La industria mide esto con un indicador: **STP (straight-through processing)** — el porcentaje de pagos que se aplican solos, sin intervención humana.

| Referencia | STP |
|---|---|
| Piso de las herramientas líderes | 80% |
| Estándar de clase mundial | 95%+ |
| L'Oréal (con HighRadius) | **96%** — redujo su riesgo crediticio en USD 57 millones |
| Johnsonville | 95% |
| **Integratel hoy** | **80.5%** (2,709 calces exactos de 3,364 facturas) |

> 🎯 **El argumento central del proyecto:** Integratel está exactamente en el piso de la industria y a **15 puntos** del estándar mundial. Cerrar esa brecha significa **487 facturas más resueltas automáticamente** en la ventana de dos meses.

**Lo que valida nuestra arquitectura:** todas esas plataformas usan el mismo esquema — motor determinista de matching, capa de aprendizaje para los casos ambiguos, y cola de excepciones para humanos. HighRadius reporta 90%+ de STP procesando remesas desde **correo, portales y archivos bancarios**, que es el mismo problema multicanal del buzón sin leer de Integratel.

**Dónde podemos ir más lejos:** la mayoría de esas plataformas son machine learning clásico, no sistemas agénticos. Clasifican y puntúan, pero no razonan sobre un caso ni explican su decisión. Nuestro posicionamiento: *"esto ya se resuelve a 95% con ML tradicional; nosotros proponemos la siguiente generación — agentes que explican, escalan y coordinan"*.

⚠️ **Cómo usarlo en el pitch:** como validación y benchmark, **nunca como competencia**. Si preguntan "¿esto no lo hace HighRadius ya?", la respuesta es: *"sí, y por eso sabemos que funciona — nosotros mostramos cómo hacerlo con agentes y sobre los datos reales de ustedes"*.

Fuentes: [HighRadius — Automated Cash Application](https://www.highradius.com/resources/Blog/8-benefits-automating-cash-application-process/) · [HighRadius — Cash Application Software](https://www.highradius.com/product/cash-application-automation/) · [HighRadius — Order to Cash 2026 Guide](https://www.highradius.com/resources/Blog/order-to-cash-automation-processes-benefits-and-industry-insights/)

### 6.7 Resumen del caso de negocio

| Concepto | Monto |
|---|---|
| Total facturado (todo el periodo) | S/ 447,964 |
| Total cobrado (jun–jul 2026) | S/ 392,837 |
| **Dinero en depósitos sin identificar** | **S/ 106,289** |
| **Dinero en descalces sin explicar** | **S/ 159,964** |
| **Total en juego por problemas de recaudo** | **≈ S/ 266,000** |

---

## 7. Enfoque recomendado

### La propuesta: recaudo al centro, agentes alrededor

Poner el **agente de recaudo y conciliación como corazón de la solución**, y que los demás lo rodeen:

```
                    ┌─────────────────────┐
                    │  AGENTE SUPERVISOR  │
                    │ asigna · controla · │
                    │ escala · mide KPIs  │
                    └──────────┬──────────┘
         ┌─────────────┬───────┴───────┬──────────────┐
         ▼             ▼               ▼              ▼
   ┌───────────┐ ┌──────────┐  ┌─────────────┐ ┌──────────┐
   │FACTURACIÓN│ │ RECAUDO  │  │  COBRANZA   │ │    BI    │
   │ arma PxQ  │ │ concilia │  │ prioriza y  │ │ recupero │
   │ valida    │ │ pagos ⭐ │  │ comunica    │ │ PCD·caja │
   │ detecta   │ │ identifi-│  │ clasifica   │ │ quiebres │
   │ fuga      │ │ ca depó- │  │ correos     │ │          │
   │           │ │ sitos    │  │             │ │          │
   └───────────┘ └──────────┘  └─────────────┘ └──────────┘
```

- **Recaudo** identifica y aplica los pagos.
- **Cobranza** usa lo que recaudo confirma, para dejar de molestar a quien ya pagó.
- **BI** analiza lo que queda sin cobrar y propone estrategias.
- **Facturación** cierra el ciclo y recibe alertas de quiebres.
- **Supervisor** coordina, mide y escala a humano lo que el agente no resuelve solo.

### Por qué recaudo y no otro frente

1. **El dolor es medible en soles.** S/ 266 mil concretos, no una mejora abstracta de productividad.
2. **Los datos alcanzan de verdad.** Tenemos facturas, pagos y notas de crédito con sus vínculos. En los otros frentes hay que suponer mucho más.
3. **La IA tiene ventaja real y explicable.** No se resuelve con una fórmula fija: es un problema de combinaciones con casos ambiguos, tolerancias y decisiones del tipo *"esto probablemente es esto, pero que lo confirme un humano"*. Justo donde un agente aporta más que un programa tradicional.
4. **Se ve funcionando en una demo.** Se le puede mostrar al jurado un depósito huérfano entrando y el agente resolviendo a qué facturas pertenece, con su nivel de confianza y su explicación.
5. **Es el problema que el propio cliente señaló como el más difícil.** Resolverlo demuestra que se escuchó al negocio.

### Cómo cumple los tres requisitos de la ficha

| Requisito | Cómo se cumple |
|---|---|
| IA agéntica con skills especializados | Cuatro agentes operadores, cada uno con su dominio y sus herramientas |
| Orquestación por un supervisor | El supervisor asigna casos, controla resultados, escala excepciones a humano y da seguimiento |
| Control de indicadores, calidad y tiempo | Cada caso resuelto registra tiempo, nivel de confianza y si requirió intervención humana → alimenta los KPIs de la ficha |

### Riesgo a manejar

El reto pide cubrir **los tres frentes**. Concentrar todo el esfuerzo en recaudo y descuidar facturación y BI puede leerse como respuesta incompleta. La recomendación es: **profundidad en recaudo, cobertura funcional demostrable en los otros tres**.

---

## 8. Cómo cargar los datos correctamente

Código de referencia para que todos partan de la misma base:

```python
import pandas as pd

def cargar(nombre):
    """Carga un CSV del reto con el separador y encoding correctos."""
    return pd.read_csv(nombre, sep='|', dtype=str, encoding='latin-1')

clientes = cargar('001_TBL_CLIENTES_B2B.csv')
fija     = cargar('002_TBL_PLANTA_FIJA_B2B.csv')
movil    = cargar('003_TBL_PLANTA_MOVIL_B2B.csv')
pagos    = cargar('004_TBL_PAGOS_B2B.csv')
facturas = cargar('005_TBL_FACTURAS_B2B.csv')
ncs      = cargar('006_TBL_NOTAS_CREDITO_B2B.csv')

# --- Fechas: cada campo tiene su formato ---
# FECHA_VTO mezcla YYYY-MM-DD y YYYYMMDD -> se quitan los guiones y se unifica
facturas['fecha_vto']     = pd.to_datetime(facturas.FECHA_VTO.str.replace('-', ''),
                                           format='%Y%m%d', errors='coerce')
facturas['fecha_emision'] = pd.to_datetime(facturas.FECHA_EMISION,
                                           format='%Y%m%d', errors='coerce')
pagos['fecha_pago']       = pd.to_datetime(pagos.FECHA_PAGO.str[:10])
movil['fecha_alta']       = pd.to_datetime(movil.FECHA_ALTA, format='%d/%m/%Y',
                                           errors='coerce')

# --- Importes: vienen como texto ---
facturas['total']   = facturas.CHARGE_TOTAL_AMOUNT.astype(float)
pagos['monto']      = pagos.MONTO_PAGADO.astype(float)
ncs['monto']        = ncs.MONTO.astype(float)

# --- Uniones: SIEMPRE por RAZON_SOCIAL, NUNCA por RUC ---
base = facturas.merge(clientes, on='RAZON_SOCIAL', how='left')

# Pagos y notas de crédito se unen por el número de documento
pagos_x_factura = pagos.groupby('FACTURA_AFECTADA').monto.sum()
ncs_x_factura   = ncs.groupby('FACTURA_AFECTADA').monto.sum()
```

---

## 9. Glosario

| Término | Qué significa |
|---|---|
| **Integratel** | La empresa del caso: el brazo B2B de Movistar en Perú |
| **B2B** | *Business to business* — venta a empresas, no a personas |
| **Recaudo** | Identificar el dinero que entró y aplicarlo a la factura correcta |
| **Cobranza** | Gestionar al cliente para que pague |
| **Conciliación bancaria** | Cuadrar los depósitos del banco contra las facturas del sistema |
| **PxQ** | Precio por cantidad — el cálculo base de lo que se le factura al cliente |
| **Nota de crédito (NC)** | Documento que anula o reduce una factura ya emitida |
| **Refacturación** | Volver a emitir una factura porque la anterior salió mal |
| **PCD** | Provisión de cobranza dudosa — reserva contable por deuda que probablemente no se cobre |
| **Periodo medio de cobro (PMC)** | Días promedio que tarda un cliente en pagar |
| **Aging** | Clasificación de la deuda por antigüedad (0-30 días, 31-60, etc.) |
| **Fuga de ingresos** | Servicio que está activo pero no se está facturando |
| **Planta** | El parque de servicios instalados (fija = internet/voz/TV, móvil = líneas) |
| **Ciclo** | Grupo de facturación; determina en qué fecha del mes se emite la factura |
| **AMDOCS / ISIS** | Los dos sistemas de facturación de la empresa |
| **SUNAT** | Autoridad tributaria peruana |
| **RUC** | Registro Único de Contribuyentes — identificador fiscal de una empresa peruana |
| **HABIDO / NO HABIDO** | Estado SUNAT: si la empresa es ubicable en su domicilio fiscal |
| **IGV** | Impuesto General a las Ventas (18% en Perú) |
| **Movistar Total** | Paquete que combina servicios fijos y móviles |
| **Agente de IA** | Asistente que no solo responde, sino que ejecuta tareas encadenadas y usa herramientas |
| **Orquestación** | Coordinación de varios agentes por parte de un supervisor |

---

## 10. Preguntas abiertas del equipo

Cosas por decidir o consultar a los organizadores:

1. **Tipo de cambio** para los 21 pagos en USD — no viene en los datos.
2. **Reglas de aplicación de pago** que usa hoy la empresa: cuando llega un pago parcial, ¿se aplica a la factura más antigua, a la de mayor monto, proporcionalmente?
3. **Tolerancia aceptable** para dar un calce por bueno automáticamente (¿S/ 1? ¿0.5%?).
4. **Los correos de clientes** que menciona la ficha no están en los datos entregados. Si se quiere demostrar el agente que clasifica mensajes, hay que generar ejemplos sintéticos realistas.
5. **Qué pasa con las 57 facturas sin pago** — ¿son mora real o solo caen fuera de la ventana de datos?
6. **Formato de entrega** esperado: ¿prototipo funcional, presentación, o ambos? ¿Hay límite de tiempo para la demo?

---

*Documento generado a partir de `03. Desafío SON-IA_VF.pdf` y los 6 archivos CSV del reto. Todas las cifras fueron calculadas directamente sobre los datos entregados.*
