"""SON-IA — conciliación de depósitos B2B.

    streamlit run app.py

Las páginas están organizadas por trabajo a realizar, no por agente, y agrupadas
por quién las usa:

  OPERACIÓN        Hoy        qué hay que hacer y cómo va (aterrizaje)
                   Conciliar  la cola: un depósito a la vez
  ANÁLISIS         Cartera    fuga de ingresos, riesgo de impago, correos
  ADMINISTRACIÓN   Control    muestreo de auditoría y trazabilidad
                   Datos      cargar los archivos del período

El informe para proyectar o enviar se genera aparte con `python torre.py`.
"""

import streamlit as st

import llm

st.set_page_config(page_title="SON-IA · Conciliación", page_icon=":material/hub:",
                   layout="wide")

# Estado del sistema, visible en todas las pantallas: de dónde salen los datos y
# qué motor de lenguaje está activo. Sin esto, alguien puede estar mirando la
# cartera sin saber qué período tiene delante.
with st.sidebar:
    subidos = st.session_state.get("subidos", {})
    if subidos:
        st.success(f"Datos: {len(subidos)} archivo(s) cargados en esta sesión",
                   icon=":material/cloud_upload:")
    else:
        st.info("Datos: los archivos de la carpeta del sistema",
                icon=":material/folder:")
    st.caption(f"Redacción y clasificación: {llm.etiqueta()}")
    st.divider()

nav = st.navigation({
    "Operación": [
        st.Page("app_pages/hoy.py", title="Hoy",
                icon=":material/today:", default=True),
        st.Page("app_pages/conciliar.py", title="Conciliar",
                icon=":material/fact_check:"),
        st.Page("app_pages/cliente.py", title="Cliente",
                icon=":material/person_search:"),
    ],
    "Análisis": [
        st.Page("app_pages/cartera.py", title="Cartera",
                icon=":material/analytics:"),
    ],
    "Administración": [
        st.Page("app_pages/control.py", title="Control",
                icon=":material/verified_user:"),
        st.Page("app_pages/datos_fuente.py", title="Datos",
                icon=":material/upload_file:"),
    ],
})

# Quién usa cada grupo: con diez áreas involucradas, decirlo evita que cada una
# tenga que descubrirlo navegando.
with st.sidebar:
    st.divider()
    with st.expander("¿Qué pantalla me toca?"):
        st.markdown(
            "**Operación** — Cobranzas, Facturación\n\n"
            "**Cliente** — Atención al Cliente, Ventas\n\n"
            "**Análisis** — Control de Gestión, Contabilidad, Finanzas, "
            "Inteligencia de Negocio, Planificación Comercial\n\n"
            "**Administración** — Contraloría y TI"
        )

nav.run()
