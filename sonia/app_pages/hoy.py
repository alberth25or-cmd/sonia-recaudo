"""Aterrizaje — qué hay que hacer hoy y cómo va la conciliación.

Es la primera pantalla porque responde la pregunta con la que alguien abre la
herramienta: ¿qué me toca? Lo analítico vive en Cartera; aquí solo va lo que
exige una acción o explica el estado del día.
"""

import pandas as pd
import streamlit as st

import carga
from agentes import recaudo

ETIQUETA = {"CONFIRMAR": "Elegir entre opciones",
            "HIPOTESIS": "Aprobar pago parcial",
            "INVESTIGAR": "Investigar"}

d = carga.todo()
clasificados, k_cob = carga.correos_clasificados()
decisiones, k_rec, carga_h = d["decisiones"], d["k_recaudo"], d["carga"]
pendientes = decisiones[decisiones.cola != "AUTO"]

st.title("Hoy")
st.caption("Conciliación de depósitos — Integratel B2B")

# --- Cómo va ------------------------------------------------------------------
with st.container(horizontal=True):
    st.metric("Aplicados sin intervención", f"{k_rec['stp_pct']}%",
              f"{k_rec['aplicados_sin_intervencion']:,} de {len(decisiones):,} depósitos",
              delta_color="off", border=True)
    st.metric("Conciliado solo", f"S/ {k_rec['monto_aplicado_solo_soles']:,.0f}",
              "sin que nadie lo revise", delta_color="off", border=True)
    st.metric("Esperando decisión", f"{len(pendientes):,}",
              f"S/ {pendientes.monto.sum():,.0f}", delta_color="off", border=True)
    st.metric("Trabajo estimado", f"{carga_h['minutos_por_dia_habil']:.0f} min",
              "por día hábil", delta_color="off", border=True)

st.divider()

# --- Qué me toca --------------------------------------------------------------
izq, der = st.columns([3, 2])

with izq:
    st.subheader("Tu cola")
    if pendientes.empty:
        st.success("No queda nada por revisar: todos los depósitos están aplicados.",
                   icon=":material/task_alt:")
    else:
        for cola in ("CONFIRMAR", "HIPOTESIS", "INVESTIGAR"):
            sub = pendientes[pendientes.cola == cola]
            if sub.empty:
                continue
            mins = len(sub) * recaudo.SEGUNDOS_POR_CASO[cola] / 60 / recaudo.DIAS_HABILES_VENTANA
            with st.container(border=True):
                a, b = st.columns([3, 1])
                a.markdown(f"**{ETIQUETA[cola]}**")
                a.caption(recaudo.COLAS[cola])
                b.metric("casos", f"{len(sub):,}", f"{mins:.0f} min",
                         delta_color="off", label_visibility="collapsed")
        st.page_link("app_pages/conciliar.py", label="Empezar a conciliar",
                     icon=":material/play_arrow:")

with der:
    st.subheader("Requiere atención")
    avisos = 0

    for c in clasificados:
        if c["categoria"] != "CONFIRMACION_PAGO":
            continue
        suyos = decisiones[decisiones.cliente == c["cliente"]]
        pend = suyos[suyos.cola != "AUTO"]
        if len(pend):
            avisos += 1
            st.warning(f"**{c['cliente']}** avisa que pagó y tiene {len(pend)} depósito(s) "
                       f"sin conciliar por S/ {pend.monto.sum():,.2f}",
                       icon=":material/priority_high:")

    criticos = d["impacto"][d["impacto"].nivel_riesgo == "CRITICO"]
    if len(criticos):
        avisos += 1
        st.warning(f"**{len(criticos)} cliente(s)** con servicio activo que nunca han sido "
                   f"facturados — S/ {criticos.impacto_soles.sum():,.0f} sin cobrar",
                   icon=":material/receipt_long:")

    alto = d["pcd"][d["pcd"].nivel_pcd == "ALTO"]
    if len(alto):
        avisos += 1
        st.info(f"**{len(alto)} cliente(s)** en riesgo alto de impago deben "
                f"S/ {alto.deuda_pendiente.sum():,.0f}", icon=":material/trending_down:")

    if not avisos:
        st.success("Nada urgente.", icon=":material/check_circle:")

    st.page_link("app_pages/cartera.py", label="Ver el detalle de cartera",
                 icon=":material/arrow_forward:")

# --- Los más grandes ----------------------------------------------------------
if not pendientes.empty:
    st.divider()
    st.subheader("Los depósitos de mayor monto en cola")
    st.dataframe(
        pendientes.nlargest(8, "monto")[
            ["cliente", "fecha", "monto", "cola", "n_candidatas", "explicacion"]],
        hide_index=True, width="stretch",
        column_config={
            "cliente": "Cliente",
            "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "monto": st.column_config.NumberColumn("Depósito", format="S/ %.2f"),
            "cola": st.column_config.TextColumn("Requiere"),
            "n_candidatas": st.column_config.NumberColumn("Facturas abiertas"),
            "explicacion": st.column_config.TextColumn("Situación", width="large"),
        },
    )
