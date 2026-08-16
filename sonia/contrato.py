"""Contrato de datos — qué necesita el sistema para correr sobre datos reales.

Este módulo es la frontera entre SON-IA y los sistemas de Integratel. Declara
qué columnas hace falta, con qué significado, y valida que una fuente cumpla
antes de procesar nada. Conectar datos reales debería ser apuntar una ruta, no
editar código.

    python contrato.py                      # valida los CSV del reto
    python contrato.py C:\\ruta\\a\\sus\\datos  # valida una carpeta propia

Si sus tablas usan otros nombres de columna, se mapean con `alias` sin tocar
el resto del sistema:

    datos.facturas(ruta="export_sap.csv", alias={"RAZON_SOCIAL": "NOMBRE_CLIENTE"})
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent

# Formatos de fecha observados. FECHA_VTO mezcla dos en la misma columna, así que
# se prueban en orden y se acepta el que parsee más filas.
FORMATOS_FECHA = ["%Y%m%d", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"]

ESQUEMA = {
    "facturas": {
        "archivo": "005_TBL_FACTURAS_B2B.csv",
        "para": "Saber qué se le cobró a cada cliente y cuándo vence",
        "columnas": {
            "NRO_DOC_FISCAL": (False, "Número de factura — identificador único"),
            "RAZON_SOCIAL": (False, "Cliente. LLAVE DE CRUCE — nunca usar el RUC"),
            "FECHA_EMISION": (True, "Fecha de emisión"),
            "FECHA_VTO": (True, "Fecha de vencimiento"),
            "CHARGE_TOTAL_AMOUNT": (False, "Importe total con IGV"),
        },
        "montos": ["CHARGE_TOTAL_AMOUNT"],
    },
    "pagos": {
        "archivo": "004_TBL_PAGOS_B2B.csv",
        "para": "Los depósitos que llegan del banco",
        "columnas": {
            "RAZON_SOCIAL": (False, "Cliente que depositó"),
            "FECHA_PAGO": (True, "Fecha del depósito"),
            "MONTO_PAGADO": (False, "Importe depositado"),
            "FACTURA_AFECTADA": (False, "SOLO PARA ENTRENAR Y MEDIR — la resolución "
                                        "manual histórica. En producción llega vacía"),
        },
        "montos": ["MONTO_PAGADO"],
    },
    "notas_credito": {
        "archivo": "006_TBL_NOTAS_CREDITO_B2B.csv",
        "para": "Correcciones que reducen lo facturado",
        "columnas": {
            "FACTURA_AFECTADA": (False, "Factura que corrige"),
            "FECHAEMISION": (True, "Fecha de emisión"),
            "MONTO": (False, "Importe de la nota. OJO: la columna SUBTOTAL "
                             "contiene el IGV, no el subtotal"),
        },
        "montos": ["MONTO"],
    },
    "clientes": {
        "archivo": "001_TBL_CLIENTES_B2B.csv",
        "para": "Señales de riesgo tributario para el scoring de cobranza dudosa",
        "columnas": {
            "RAZON_SOCIAL": (False, "Cliente"),
            "SUNAT_ESTADO_RUC": (False, "HABIDO / NO HABIDO"),
            "SUNAT_ESTADO_CONTRIBUYENTE": (False, "ACTIVO / BAJA / SUSPENSIÓN"),
        },
        "montos": [],
    },
    "fija": {
        "archivo": "002_TBL_PLANTA_FIJA_B2B.csv",
        "para": "Detectar servicio activo sin facturar (fuga de ingresos)",
        "columnas": {
            "RAZON_SOCIAL": (False, "Cliente"),
            "STATUS_DESC": (False, "Estado de la cuenta — 'Active' cuenta como activo"),
            "FECHAALTA": (True, "Alta del servicio. Hay centinelas: 1967, 1970-01-01"),
        },
        "montos": [],
    },
    "movil": {
        "archivo": "003_TBL_PLANTA_MOVIL_B2B.csv",
        "para": "Igual que planta fija, para líneas móviles",
        "columnas": {
            "RAZON_SOCIAL": (False, "Cliente"),
            "ESTADO_LINEA": (False, "Estado — 'Activo' cuenta como activo"),
            "FECHA_ALTA": (True, "Alta de la línea"),
        },
        "montos": [],
    },
}


def a_fecha(serie):
    """Parsea fechas probando los formatos conocidos; devuelve (serie, formato, fallidas).

    Para columnas que mezclan formatos (FECHA_VTO trae 'YYYY-MM-DD' y 'YYYYMMDD'),
    se quitan los separadores y se reintenta.
    """
    s = serie.astype(str).str.strip()
    mejor, mejor_fmt, menos_nulos = None, None, len(s) + 1

    for fmt in FORMATOS_FECHA:
        parsed = pd.to_datetime(s, format=fmt, errors="coerce")
        nulos = parsed.isna().sum()
        if nulos < menos_nulos:
            mejor, mejor_fmt, menos_nulos = parsed, fmt, nulos
        if nulos == 0:
            return parsed, fmt, 0

    # Formatos mezclados: normalizar quitando separadores y reintentar
    if menos_nulos:
        limpia = s.str.replace(r"[-/\s:]", "", regex=True).str[:8]
        parsed = pd.to_datetime(limpia, format="%Y%m%d", errors="coerce")
        if parsed.isna().sum() < menos_nulos:
            return parsed, "%Y%m%d (formatos mezclados, normalizados)", int(parsed.isna().sum())

    return mejor, mejor_fmt, int(menos_nulos)


def leer(ruta, sep="|", encoding="latin-1"):
    return pd.read_csv(ruta, sep=sep, dtype=str, encoding=encoding)


def validar(tabla, ruta=None, alias=None, sep="|", encoding="latin-1"):
    """Comprueba que una fuente cumpla el contrato. Devuelve (ok, informe, df).

    `ruta` acepta una ruta en disco o un archivo ya abierto (por ejemplo el que
    devuelve un formulario de carga), para que subir un CSV desde la interfaz
    pase por exactamente la misma validación que leerlo del disco.
    """
    spec = ESQUEMA[tabla]
    alias = alias or {}
    informe = []

    subido = ruta is not None and not isinstance(ruta, (str, Path))
    if not subido:
        ruta = Path(ruta) if ruta else RAIZ / spec["archivo"]
        if not ruta.exists():
            return False, [f"✗ No existe el archivo: {ruta}"], None
        nombre = ruta.name
    else:
        nombre = getattr(ruta, "name", "archivo cargado")
        if hasattr(ruta, "seek"):
            ruta.seek(0)

    try:
        df = leer(ruta, sep, encoding)
    except Exception as ex:
        return False, [f"✗ No se pudo leer ({type(ex).__name__}): {ex}",
                       "  Revisar el separador y el encoding."], None

    df = df.rename(columns={v: k for k, v in alias.items()})
    informe.append(f"  archivo   {nombre}  ·  {len(df):,} filas × {len(df.columns)} columnas")

    ok = True
    for col, (es_fecha, descripcion) in spec["columnas"].items():
        if col not in df.columns:
            informe.append(f"  ✗ FALTA  {col}  — {descripcion}")
            ok = False
            continue
        vacias = df[col].isna().sum()
        detalle = f"{vacias} vacías" if vacias else "completa"
        if es_fecha:
            _, fmt, fallidas = a_fecha(df[col])
            detalle = (f"formato {fmt}" +
                       (f", {fallidas} sin parsear" if fallidas else ", todas parseadas"))
            if fallidas > len(df) * 0.05:
                informe.append(f"  ⚠ {col:<28} {detalle}  ← más del 5% no parsea")
                ok = False
                continue
        informe.append(f"  ✓ {col:<28} {detalle}")

    for col in spec["montos"]:
        if col in df.columns:
            malos = pd.to_numeric(df[col], errors="coerce").isna().sum()
            if malos:
                informe.append(f"  ⚠ {col:<28} {malos} valores no numéricos")
                ok = False

    return ok, informe, df


def cargar(tabla, ruta=None, alias=None, sep="|", encoding="latin-1"):
    """Carga una tabla ya validada y normalizada. Lanza si no cumple el contrato."""
    ok, informe, df = validar(tabla, ruta, alias, sep, encoding)
    if not ok:
        raise ValueError(f"La fuente '{tabla}' no cumple el contrato:\n" + "\n".join(informe))

    spec = ESQUEMA[tabla]
    for col, (es_fecha, _) in spec["columnas"].items():
        if es_fecha:
            df[f"_fecha_{col}"] = a_fecha(df[col])[0]
    for col in spec["montos"]:
        df[f"_monto_{col}"] = pd.to_numeric(df[col], errors="coerce")
    return df


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    origen = base or RAIZ

    print("=" * 76)
    print(f"CONTRATO DE DATOS  ·  validando {origen}")
    print("=" * 76)

    todo_ok = True
    for tabla, spec in ESQUEMA.items():
        ruta = (base / spec["archivo"]) if base else None
        ok, informe, _ = validar(tabla, ruta)
        estado = "CUMPLE" if ok else "NO CUMPLE"
        print(f"\n[{estado}]  {tabla.upper()}  —  {spec['para']}")
        for linea in informe:
            print(linea)
        todo_ok &= ok

    print("\n" + "=" * 76)
    if todo_ok:
        print("  Todas las fuentes cumplen. El sistema puede correr sobre estos datos:")
        print("      python orquestador.py")
    else:
        print("  Hay fuentes que no cumplen. Opciones:")
        print("      · mapear nombres distintos con alias={'ESPERADO': 'EL_SUYO'}")
        print("      · ajustar sep= y encoding= si el archivo no es '|' y latin-1")
    print("\n  Para ENTRENAR la capa de aprendizaje hace falta además que PAGOS traiga")
    print("  FACTURA_AFECTADA resuelta históricamente: es el criterio de sus analistas,")
    print("  y es lo que el modelo aprende. En producción esa columna llega vacía.")
    print("=" * 76)


if __name__ == "__main__":
    main()
