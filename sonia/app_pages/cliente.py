"""Cliente — todo lo que el sistema sabe de una empresa, en una pantalla.

Para quien atiende el teléfono. La llamada típica es «me cortaron y yo ya
pagué»: hace falta ver, sin navegar entre pantallas, si sus depósitos están
aplicados, qué debe, si escribió, y si tiene servicio sin facturar.
"""

import pandas as pd
import streamlit as st

import carga

ETIQUETA = {"AUTO": "Aplicado automáticamente", "CONFIRMAR": "Esperando elegir entre opciones",
            "HIPOTESIS": "Esperando aprobar pago parcial", "INVESTIGAR": "En investigación"}

d = carga.todo()
clasificados, _ = carga.correos_clasificados()
decisiones, detalle = d["decisiones"], d["detalle"]

st.title("Cliente")
st.caption("Todo lo que sabemos de una empresa, para responder en la llamada")

empresas = sorted(decisiones.cliente.unique())
cliente = st.selectbox("Buscar empresa", empresas, index=None,
                       placeholder="Escriba el nombre de la empresa…")

if not cliente:
    st.info("Seleccione una empresa para ver su situación completa.",
            icon=":material/search:")
    st.stop()

suyos = decisiones[decisiones.cliente == cliente].sort_values("fecha", ascending=False)
pendientes = suyos[suyos.cola != "AUTO"]
pcd = d["pcd"][d["pcd"].RAZON_SOCIAL == cliente]
fuga = d["impacto"][d["impacto"].RAZON_SOCIAL == cliente]
correos_suyos = [c for c in clasificados if c["cliente"] == cliente]

# --- Respuesta rápida ---------------------------------------------------------
with st.container(border=True):
    if pendientes.empty and len(suyos):
        st.success(f"**Todos sus depósitos están aplicados.** {len(suyos)} depósito(s) por "
                   f"S/ {suyos.monto.sum():,.2f} conciliados. Si figura como moroso, no es "
                   f"por falta de identificación del pago.", icon=":material/check_circle:")
    elif not pendientes.empty:
        st.warning(f"**Tiene {len(pendientes)} depósito(s) sin aplicar** por "
                   f"S/ {pendientes.monto.sum():,.2f}. Puede estar figurando como moroso "
                   f"aunque haya pagado — priorizar su conciliación.",
                   icon=":material/priority_high:")
    else:
        st.info("No registra depósitos en el período.", icon=":material/info:")

# --- Situación ----------------------------------------------------------------
with st.container(horizontal=True):
    st.metric("Depósitos recibidos", f"{len(suyos)}",
              f"S/ {suyos.monto.sum():,.2f}" if len(suyos) else "—",
              delta_color="off", border=True)
    st.metric("Sin aplicar", f"{len(pendientes)}",
              f"S/ {pendientes.monto.sum():,.2f}" if len(pendientes) else "todo aplicado",
              delta_color="off", border=True)
    if len(pcd):
        r = pcd.iloc[0]
        st.metric("Riesgo de impago", r.nivel_pcd,
                  f"debe S/ {r.deuda_pendiente:,.2f}", delta_color="off", border=True)
    if len(fuga):
        st.metric("Servicio sin facturar", fuga.iloc[0].nivel_riesgo,
                  f"S/ {fuga.iloc[0].impacto_soles:,.2f} estimado",
                  delta_color="off", border=True)

# --- Sus depósitos ------------------------------------------------------------
if len(suyos):
    st.subheader("Sus depósitos en el período")
    vista = suyos[["fecha", "monto", "cola", "explicacion"]].copy()
    vista["cola"] = vista.cola.map(ETIQUETA)
    st.dataframe(
        vista, hide_index=True, width="stretch",
        column_config={
            "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "monto": st.column_config.NumberColumn("Monto", format="S/ %.2f"),
            "cola": "Estado",
            "explicacion": st.column_config.TextColumn("Detalle", width="large"),
        },
    )

    aplicados = suyos[suyos.cola == "AUTO"]
    if len(aplicados):
        with st.expander(f"Ver a qué facturas se aplicaron ({len(aplicados)})"):
            filas = []
            for c in aplicados.itertuples():
                for nro in c.facturas_propuestas:
                    filas.append({"Fecha del pago": c.fecha, "Factura": nro,
                                  "Importe": detalle[nro]["total"],
                                  "Vencía": detalle[nro]["vto"]})
            st.dataframe(
                pd.DataFrame(filas), hide_index=True, width="stretch",
                column_config={
                    "Fecha del pago": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Vencía": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Importe": st.column_config.NumberColumn(format="S/ %.2f")},
            )

# --- Lo que escribió ----------------------------------------------------------
if correos_suyos:
    st.subheader("Comunicaciones recibidas")
    for c in correos_suyos:
        with st.container(border=True):
            st.markdown(f"**{c['asunto']}** · clasificado como `{c['categoria']}` "
                        f"(confianza {c['confianza']})")
            st.caption(c["cuerpo"])

# --- Contexto de riesgo -------------------------------------------------------
if len(pcd) and pcd.iloc[0].nivel_pcd != "BAJO":
    r = pcd.iloc[0]
    st.subheader("Recomendación de gestión")
    prio = d["prioridad"][d["prioridad"].RAZON_SOCIAL == cliente]
    if len(prio):
        st.info(prio.iloc[0].estrategia, icon=":material/lightbulb:")
    st.caption(f"Facturas pendientes: {int(r.facturas_pendientes)} · "
               f"puntaje de riesgo {int(r.puntaje_riesgo)}")
