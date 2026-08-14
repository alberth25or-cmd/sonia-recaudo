"""Carga de datos para SON-IA.

Delega la validación y el parseo de fechas a contrato.py, que es la frontera con
los sistemas de Integratel. Aquí solo se les pone a las columnas los nombres
cortos que usa el resto del código.

Sobre los CSV del reto no hace falta pasar nada:

    facturas()

Sobre datos reales, se apunta la ruta y, si los nombres difieren, se mapean:

    facturas(ruta="/export/sap/facturas.csv",
             alias={"RAZON_SOCIAL": "NOMBRE_CLIENTE"},
             sep=";", encoding="utf-8")

Reglas que el contrato hace cumplir (ver CONTEXTO_RETO3_SONIA.md secciones 5 y 8):
  - unir SIEMPRE por RAZON_SOCIAL, NUNCA por RUC (el RUC está aleatorizado)
  - FECHA_VTO mezcla dos formatos en la misma columna: se detectan solos
"""

import contrato


def _cargar(tabla, ruta=None, alias=None, **opciones):
    return contrato.cargar(tabla, ruta=ruta, alias=alias, **opciones)


def facturas(ruta=None, alias=None, **opciones):
    f = _cargar("facturas", ruta, alias, **opciones)
    f["fecha_emision"] = f["_fecha_FECHA_EMISION"]
    f["fecha_vto"] = f["_fecha_FECHA_VTO"]
    f["total"] = f["_monto_CHARGE_TOTAL_AMOUNT"]
    return f


def pagos(ruta=None, alias=None, **opciones):
    p = _cargar("pagos", ruta, alias, **opciones)
    p["fecha_pago"] = p["_fecha_FECHA_PAGO"].dt.normalize()
    p["monto"] = p["_monto_MONTO_PAGADO"]
    return p


def notas_credito(ruta=None, alias=None, **opciones):
    n = _cargar("notas_credito", ruta, alias, **opciones)
    n["fecha_emision"] = n["_fecha_FECHAEMISION"]
    n["monto"] = n["_monto_MONTO"]
    return n


def clientes(ruta=None, alias=None, **opciones):
    return _cargar("clientes", ruta, alias, **opciones)


def planta_fija(ruta=None, alias=None, **opciones):
    pf = _cargar("fija", ruta, alias, **opciones)
    pf["fecha_alta"] = pf["_fecha_FECHAALTA"]  # ojo: centinelas 1967 y 1970-01-01
    return pf


def planta_movil(ruta=None, alias=None, **opciones):
    pm = _cargar("movil", ruta, alias, **opciones)
    pm["fecha_alta"] = pm["_fecha_FECHA_ALTA"]
    return pm
