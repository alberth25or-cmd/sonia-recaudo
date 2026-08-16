"""Carga cacheada que comparten las páginas de la app.

Todo el trabajo pesado (procesar los 2,283 depósitos) ocurre una vez y queda en
caché: cambiar de pestaña no vuelve a calcular nada.
"""

import pandas as pd
import streamlit as st

import datos
from agentes import bi, cobranza, correos, facturacion, recaudo


def _fuente(tabla):
    """Archivo cargado en esta sesión, si lo hay; si no, el de la carpeta."""
    return st.session_state.get("subidos", {}).get(tabla)


@st.cache_data(ttl="2h", show_spinner="Procesando los depósitos del banco…")
def todo():
    # La caché se limpia explícitamente al cargar o descartar archivos
    # (ver app_pages/datos_fuente.py), por eso puede leerse el origen aquí.
    opciones = {"sep": st.session_state.get("sep", "|"),
                "encoding": st.session_state.get("enc", "latin-1")}
    if st.session_state.get("subidos"):
        f = datos.facturas(_fuente("facturas"), **opciones)
        p = datos.pagos(_fuente("pagos"), **opciones)
        ncs = datos.notas_credito(_fuente("notas_credito"), **opciones)
        clientes = datos.clientes(_fuente("clientes"), **opciones)
        fija = datos.planta_fija(_fuente("fija"), **opciones)
        movil = datos.planta_movil(_fuente("movil"), **opciones)
    else:
        f, p, ncs = datos.facturas(), datos.pagos(), datos.notas_credito()
        clientes, fija, movil = datos.clientes(), datos.planta_fija(), datos.planta_movil()

    decisiones = recaudo.procesar(f, p)
    fuga = facturacion.detectar_fuga(fija, movil, f)
    impacto = facturacion.estimar_impacto(fuga, f)
    cal = facturacion.calidad(f, ncs)
    pcd = bi.calcular_pcd(clientes, f, p)
    aging = bi.calcular_aging(f, p)

    return {
        "facturas": f,
        "decisiones": decisiones,
        "detalle": {r.NRO_DOC_FISCAL: {"total": r.total, "vto": r.fecha_vto}
                    for r in f.itertuples()},
        "k_recaudo": recaudo.kpis(decisiones),
        "carga": recaudo.carga_humana(decisiones),
        "fuga": fuga,
        "impacto": impacto,
        "k_facturacion": facturacion.kpis(fuga, impacto, cal),
        "calidad": cal,
        "pcd": pcd,
        "aging": aging,
        "prioridad": bi.priorizar(pcd, fuga),
        "k_bi": bi.kpis(pcd, aging),
    }


@st.cache_data(ttl="2h", show_spinner="Clasificando correos con el modelo…")
def correos_clasificados():
    clasificados = cobranza.clasificar_lote(correos.CORREOS)
    return clasificados, cobranza.kpis(clasificados)


def tabla_colas(decisiones):
    filas = []
    for cola, desc in recaudo.COLAS.items():
        sub = decisiones[decisiones.cola == cola]
        seg = recaudo.SEGUNDOS_POR_CASO[cola]
        filas.append({
            "Cola": cola,
            "Qué hace el humano": desc,
            "Casos": len(sub),
            "% del total": len(sub) / len(decisiones),
            "Monto": sub.monto.sum(),
            "Min/día hábil": round(len(sub) * seg / 60 / recaudo.DIAS_HABILES_VENTANA),
        })
    return pd.DataFrame(filas)
