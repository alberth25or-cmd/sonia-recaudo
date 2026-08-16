# El pitch

Siete minutos. Comprimible a cinco quitando la sección 6.

---

## La tesis, en una frase

> **Sus clientes ya están pagando. El problema es que identificar ese dinero
> cuesta un día de trabajo diario, y mientras tanto el cliente figura como moroso.
> Esto lo resuelve solo en el 70% de los casos, corriendo en una laptop.**

## Cómo hay que hablar

Tres reglas que ordenan todo el discurso:

- **Hablar de su operación, no de nuestra ingeniería.** Ellos no compran
  arquitectura, compran que el problema deje de doler.
- **No mencionar a otros equipos ni compararse.** No aporta y gasta tiempo.
- **Apoyarse en que esto ya funciona en otras empresas.** Es una categoría
  probada con casos públicos, no un experimento de estudiantes.

Lo que hicimos de riguroso **no se presume: se usa cuando preguntan.** Está en la
sección de preguntas difíciles.

---

## El arco

### 1 · Su problema, en su lenguaje · 60 s

Empezar por una persona, no por una arquitectura.

> «Una empresa cliente pagó su factura hace dos semanas. Sigue apareciendo como
> morosa, le siguen llegando llamadas de cobranza, y en algún momento le van a
> cortar el servicio. No porque no haya pagado — porque nadie ha logrado
> averiguar cuál de sus veinte facturas abiertas estaba pagando.»

Y el costo, en los dos frentes que les duelen:

> «Eso son dos cosas a la vez: un día de trabajo diario en identificar depósitos a
> mano, y una relación con el cliente que se rompe por un error nuestro.»

### 2 · Esto ya está resuelto en el mundo · 45 s

Es la sección que da confianza. **No es una idea nueva — es una categoría madura.**

> «Esto tiene nombre: *cash application*, dentro de order-to-cash. HighRadius, SAP
> y Sidetrade lo resuelven hace años, y la industria lo mide con un solo
> indicador: qué porcentaje de los pagos se aplica sin que nadie los toque.
>
> Los casos publicados por esos proveedores hablan de ochenta por ciento como piso
> y noventa y cinco como referencia alta. L'Oréal reporta noventa y seis por
> ciento con HighRadius y una reducción de riesgo crediticio de cincuenta y siete
> millones de dólares.
>
> O sea: el problema tiene solución probada. Lo que no existe es una implementación
> sobre los sistemas de Integratel.»

### 3 · Lo que hicimos con sus datos · 90 s

**Mostrar:** la torre. Un caso real en *Asignar depósitos*.

> «Del banco llega esto: empresa, monto, fecha. Nada más. Y ese cliente tiene
> veinte facturas abiertas — más de un millón de combinaciones posibles.
>
> El sistema las resuelve todas en milisegundos. Cuando hay una sola respuesta
> exacta, la aplica y nadie la ve. Cuando hay varias, se las pasa a una persona
> con la propuesta ya hecha.»

Mostrar el encadenamiento entre agentes, que es lo que la ficha pide:

> «Y los agentes se hablan. Cobranza lee un correo que dice "ya pagué", busca los
> depósitos sin asignar de ese cliente y le dice a Recaudo que priorice el caso.
> Si ya estaban aplicados, saca al cliente de la ruta de cobranza para que no lo
> vuelvan a llamar.»

El diseño del puesto humano:

> «Fíjense en lo que hace la persona: **confirma, no calcula**. Ve el depósito, la
> propuesta con la suma resuelta, y el motivo en una frase. Veinte segundos.»

### 4 · Qué mejora respecto a hoy · 90 s

**El corazón del pitch.** Concreto, en su unidad de medida.

> «Setenta coma seis por ciento de los depósitos se aplican solos. Sobre los datos
> que ustedes nos dieron, eso son **mil seiscientos doce depósitos que hoy alguien
> abre uno por uno, y que nadie volvería a abrir**.
>
> Lo que queda son seiscientos setenta y uno que sí necesitan criterio. Pero no
> llegan en blanco: llegan con la propuesta hecha y el motivo escrito. Diecinueve
> minutos de trabajo al día.»

Y el caso más caro, que es donde está la segunda mejora:

> «Los más difíciles son doscientos veintiuno donde ninguna combinación cuadra.
> Esos hoy arrancan de cero. Ahí entra un modelo entrenado que puntúa factura por
> factura: en las pruebas señala la correcta el noventa y siete por ciento de las
> veces. Cinco minutos de investigación se vuelven dos de confirmación — y esa
> sola pieza baja el trabajo diario de treinta y cuatro minutos a diecinueve.»

Y el riesgo, antes de que lo pregunten:

> «En lo que se aplica solo nos equivocamos una vez de cada mil quinientas noventa
> y seis. Y es una perilla: si quisieran cubrir tres puntos más, el error se
> multiplica por cuarenta y cinco. Elegimos el ajuste conservador porque sobre
> dinero equivocarse cuesta más que revisar.»

### 5 · Cada pieza donde sirve · 60 s

**No como demostración de rigor, sino como la razón por la que el sistema es
barato de operar.** El mensaje es: probamos, y pusimos cada herramienta donde
gana.

> «Probamos poner un modelo a elegir entre las combinaciones que el algoritmo ya
> resuelve. Perdió. También optimización global sobre todos los depósitos a la
> vez: perdió. En el setenta por ciento fácil, la aritmética exacta es
> imbatible — y eso es bueno para ustedes, porque **no necesitan infraestructura
> pesada**: corre en una laptop y se audita línea por línea.
>
> Donde el modelo sí gana es en los casos que el algoritmo no resuelve, y ahí lo
> conectamos: pasa de ochenta a noventa y siete por ciento de acierto.
>
> Y hay una tercera pieza: **el sistema aprende de su propia gente**. Cada caso
> que un analista resuelve queda como ejemplo. El modelo se reentrena con eso y
> propone mejor la próxima vez, sin que nadie tenga que etiquetar nada aparte.»

### 6 · Qué cuesta operarlo · 45 s

> «Un analista, diecinueve minutos al día. No es un puesto nuevo — es un rato de
> su mañana.
>
> El modelo de lenguaje corre **dentro de la máquina**: los datos financieros de
> sus clientes no salen a ningún servicio externo. Diez dólares al mes de cómputo,
> y no crece con el volumen: crece con los casos difíciles. Si duplican clientes,
> el costo casi no se mueve.»

### 7 · Cómo se conecta y qué sigue · 45 s

**Mostrar:** terminal, `python contrato.py`.

> «Conectarlo a sus sistemas es apuntar una ruta. Esto valida sus tablas y dice en
> diez segundos si el sistema corre sobre ellas — detecta solo los formatos de
> fecha, incluido el que viene mezclado entre AMDOCS e ISIS.
>
> Y el modelo se reentrena con un comando sobre los datos de ustedes. Aquí
> aprendió de dos meses; ustedes tienen años guardados, y además el modelo
> aprende del comportamiento de cada cliente en particular, que es donde esta
> categoría llega al noventa y cinco.»

---

## Las tres preguntas difíciles

**«¿Y si se equivoca?»**

> «Tres respuestas. Una: el error está medido, no supuesto — uno de cada mil
> quinientos noventa y seis. Dos: toda decisión es reversible y queda registrada
> con hora, autor y motivo. Tres: cada semana se audita una muestra de lo que se
> aplicó solo, y la pantalla dice explícitamente qué puede y qué no puede detectar
> esa muestra.»

**«¿De dónde sale ese setenta por ciento?»**

*Aquí sí se explica el método, porque lo preguntaron.*

> «Escondimos la columna que dice a qué factura corresponde cada pago —que es la
> que hoy llena a mano un analista— y reconstruimos cada depósito como llega del
> banco. El motor resolvió sin verla, y recién después comparamos. Si la
> hubiéramos dejado, el número saldría más alto, pero estaríamos midiendo el
> trabajo manual que queremos reemplazar.»

**«¿El modelo decide sobre el dinero?»**

> «No. El modelo solo actúa donde el algoritmo exacto no encuentra respuesta, y
> ahí **propone, no aplica**: siempre hay una persona que confirma. Lo que se
> aplica solo es únicamente lo que tiene una única solución matemática exacta.
> Nunca sale plata por una probabilidad.»

**«¿Y cómo saben que ese modelo sirve?»**

> «Lo comparamos contra la regla obvia —imputar a la factura que vence más
> cerca— sobre los mismos casos, entrenando con junio y evaluando con julio, con
> la respuesta escondida. La regla acierta ochenta; el modelo, noventa y siete.
> Y descartamos que dependa de un solo dato: quitándole el más importante, pierde
> un punto.»

**«¿Esto no lo hace HighRadius ya?»**

> «Sí, y por eso sabemos que funciona. La diferencia es que esto corre sobre sus
> datos, dentro de su infraestructura, y coordina recaudo con facturación y
> cobranza. Una plataforma comercial es un proyecto de meses y licencias; esto es
> el mismo mecanismo, funcionando, en su estructura de archivos.»

---

## Lo que NO se dice

1. **No decir «Integratel está en X% de STP».** Los datos son sintéticos. Lo
   medible es lo que este motor logra sobre estos datos.
2. **No presentar los S/ 106,289 de huérfanos como dinero real.** El 92% apunta a
   series válidas inexistentes: es un desacople del generador de datos.
3. **No comparar el 70.6% con ninguna cifra de la operación actual de ellos** —
   no la conocemos.

Regla general: **presentar la estructura del problema, no los soles.** Los
importes describen el dataset, no la caja de Integratel.

---

## Qué mostrar, en qué orden

| Momento | En pantalla |
|---|---|
| 1 | Nada — que miren a quien habla |
| 2 | Nada, o una lámina con los nombres de la categoría |
| 3 | La torre: *Asignar depósitos* → *Resumen* → «Requiere atención» |
| 4 | La dona del 70.6% y las cuatro tarjetas |
| 5 | Un caso de *investigar* con el bloque de facturas sugeridas |
| 6 | *Registro* — trazabilidad y descarga |
| 7 | Terminal: `python contrato.py` |

**Antes de empezar:** verificar que Ollama corre y que la torre está generada. Si
el modelo no está, el sistema funciona igual con plantillas — conviene saberlo
antes, no descubrirlo en vivo.

---

## Si solo hay cinco minutos

Quitar la sección 5 y comprimir la 7 a una frase. **No tocar la 2 ni la 4**: la 2
da confianza en que el problema tiene solución, y la 4 es la mejora concreta.
