"""Correos sintéticos de clientes.

El dataset del reto NO incluye correos (pregunta abierta #4 del documento de
contexto). Estos replican los tres tipos que la propia ficha describe: "ya
pagué, adjunto voucher", "no estoy de acuerdo con el monto", "reenvíeme la
factura".

Están escritos contra clientes que SÍ existen en los datos reales, para que la
confirmación de pago que detecta Cobranza pueda entregarse a Recaudo y este
busque de verdad los depósitos de ese cliente. Sin eso el traspaso entre
agentes sería decorativo.

Base: prototipo de Agentes 1551 (correos_sinteticos.py).
"""

CORREOS = [
    {"cliente": "CLIENT_00133", "asunto": "Comprobante de pago factura S8AA-0008006986",
     "cuerpo": "Buenas tardes, adjunto el voucher de la transferencia que hice ayer por la "
               "factura S8AA-0008006986. Quedo atento a la confirmación."},
    {"cliente": "CLIENT_00890", "asunto": "No estoy de acuerdo con el monto cobrado",
     "cuerpo": "Hola, revisé mi factura S9AA-0083236130 y el monto no coincide con lo que "
               "veníamos pagando. Necesito que me expliquen el aumento antes de pagar."},
    {"cliente": "CLIENT_00445", "asunto": "Reenvío de factura por favor",
     "cuerpo": "Buenos días, no encuentro la factura del mes pasado en mi correo, "
               "¿me la pueden reenviar? Gracias."},
    {"cliente": "CLIENT_00705", "asunto": "Consulta por corte de servicio",
     "cuerpo": "Nuestro servicio de internet está siendo suspendido pero no tenemos deuda "
               "pendiente que sepamos. Favor revisar."},
    {"cliente": "CLIENT_00680", "asunto": "Ya realicé el pago",
     "cuerpo": "Estimados, ya cancelé el total pendiente vía Yape el día de hoy. "
               "Envío captura de pantalla como comprobante."},
    {"cliente": "CLIENT_00930", "asunto": "Reclamo por cobro duplicado",
     "cuerpo": "Nos está llegando el mismo cargo dos veces en el estado de cuenta. Por favor "
               "revisar y corregir, no vamos a pagar dos veces por el mismo servicio."},
    {"cliente": "CLIENT_00541", "asunto": "Voucher adjunto",
     "cuerpo": "Buenas, aquí el comprobante del depósito que hicimos esta semana. "
               "Cualquier consulta me escriben."},
    {"cliente": "CLIENT_00347", "asunto": "Solicitud de refacturación",
     "cuerpo": "El monto de la factura de julio está mal calculado, se cobró un servicio que "
               "ya habíamos dado de baja el mes pasado. Solicito nota de crédito."},
    {"cliente": "CLIENT_00756", "asunto": "Pago realizado - favor confirmar",
     "cuerpo": "Hola, hicimos el pago correspondiente el lunes. Agradeceríamos la confirmación "
               "para evitar que nos sigan llamando de cobranza."},
    {"cliente": "CLIENT_00204", "asunto": "Necesito copia de mi última factura",
     "cuerpo": "¿Podrían mandarme la última factura en PDF? La necesito para mi contabilidad."},
]
