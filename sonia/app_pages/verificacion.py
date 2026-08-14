"""Pantalla 2 — la estación del operador.

Principio: el operador CONFIRMA, no CALCULA. Se le muestra un caso a la vez con
la aritmética resuelta y el motivo en una línea. Si tuviera que sumar o buscar
facturas en otro sistema, haría falta un analista senior y cada caso costaría
minutos; confirmando una propuesta, el trabajo lo hace un asistente en segundos.
"""

import datetime as dt

import pandas as pd
import streamlit as st

import carga
from agentes import recaudo

ETIQUETA = {"CONFIRMAR": "Elegir entre opciones",
            "HIPOTESIS": "Aprobar pago parcial",
            "INVESTIGAR": "Investigar"}
MOTIVOS = ["La combinación no corresponde", "El cliente reclamó este cobro",
           "Falta una factura en el sistema", "Es pago de otra empresa del grupo",
           "Otro (anotar en observación)"]

st.session_state.setdefault("decisiones", {})
st.session_state.setdefault("historial", [])


def registrar(caso_id, accion, cola, monto, motivo=""):
    st.session_state.decisiones[caso_id] = {
        "accion": accion, "cola": cola, "monto": monto, "motivo": motivo,
        "ts": dt.datetime.now().isoformat(timespec="seconds")}
    st.session_state.historial.append(caso_id)


def deshacer():
    if st.session_state.historial:
        st.session_state.decisiones.pop(st.session_state.historial.pop(), None)


d = carga.todo()
decisiones, detalle = d["decisiones"], d["detalle"]
pendientes = decisiones[decisiones.cola != "AUTO"]

st.title("Estación de verificación")
st.caption("Agente de Recaudo — el operador confirma, el motor calcula")

# --- Dónde estoy: la cola completa antes de ver un caso ----------------------
revisados_ids = set(st.session_state.decisiones)
sin_revisar = pendientes[
    ~pendientes.apply(lambda r: f"{r.cliente}|{r.fecha}" in revisados_ids, axis=1)]

with st.container(border=True):
    st.markdown("**Tu cola de hoy**")
    with st.container(horizontal=True):
        for cola in ("CONFIRMAR", "HIPOTESIS", "INVESTIGAR"):
            n = len(sin_revisar[sin_revisar.cola == cola])
            mins = n * recaudo.SEGUNDOS_POR_CASO[cola] / 60 / recaudo.DIAS_HABILES_VENTANA
            st.metric(ETIQUETA[cola], f"{n:,}", f"{mins:.0f} min/día",
                      delta_color="off", border=True)
        st.metric("Revisados en esta sesión", f"{len(st.session_state.decisiones):,}",
                  border=True)
    st.caption(f"Los otros {len(decisiones) - len(pendientes):,} depósitos "
               f"({d['k_recaudo']['stp_pct']}%) se aplicaron solos y no llegan aquí.")

with st.sidebar:
    st.subheader("Cola de trabajo")
    cola = st.segmented_control("Tipo de caso", options=list(ETIQUETA),
                                format_func=ETIQUETA.get, default="CONFIRMAR")
    orden = st.selectbox("Ordenar por", ["Monto (mayor primero)", "Fecha (más antiguo)"])
    st.divider()
    st.button("Deshacer última decisión", icon=":material/undo:", on_click=deshacer,
              disabled=not st.session_state.historial, width="stretch")
    if st.session_state.decisiones:
        aud = pd.DataFrame([{"caso": k, **v} for k, v in st.session_state.decisiones.items()])
        st.download_button("Descargar auditoría", aud.to_csv(index=False).encode("utf-8"),
                           file_name=f"auditoria_{dt.date.today():%Y%m%d}.csv",
                           mime="text/csv", icon=":material/download:", width="stretch")

if not cola:
    st.info("Elige una cola de trabajo en el panel lateral.")
    st.stop()

actual = sin_revisar[sin_revisar.cola == cola]
actual = (actual.sort_values("monto", ascending=False) if orden.startswith("Monto")
          else actual.sort_values("fecha"))

if actual.empty:
    st.success(f"Cola **{ETIQUETA[cola].lower()}** al día. No queda nada por revisar.")
    st.stop()

caso = actual.iloc[0]
caso_id = f"{caso.cliente}|{caso.fecha}"

st.subheader(f"Caso 1 de {len(actual):,} · {ETIQUETA[cola].lower()}")

izq, der = st.columns([3, 2])

with izq:
    with st.container(border=True):
        st.markdown("**Depósito recibido del banco**")
        with st.container(horizontal=True):
            st.metric("Empresa", caso.cliente, border=True)
            st.metric("Monto", f"S/ {caso.monto:,.2f}", border=True)
            st.metric("Fecha", f"{caso.fecha:%d/%m/%Y}", border=True)

    with st.container(border=True):
        if caso.cola == "CONFIRMAR":
            st.markdown("**Propuesta del agente**")
            st.dataframe(
                pd.DataFrame([{"Factura": n, "Vence": detalle[n]["vto"],
                               "Importe": detalle[n]["total"]}
                              for n in caso.facturas_propuestas]),
                hide_index=True, width="stretch",
                column_config={"Vence": st.column_config.DateColumn(format="DD/MM/YYYY"),
                               "Importe": st.column_config.NumberColumn(format="S/ %.2f")},
            )
            suma = sum(detalle[n]["total"] for n in caso.facturas_propuestas)
            st.markdown(f"Suma **S/ {suma:,.2f}** · Depósito **S/ {caso.monto:,.2f}** · " +
                        (":green[calza exacto]" if abs(suma - caso.monto) < 0.005
                         else f":orange[diferencia S/ {suma - caso.monto:,.2f}]"))

        elif caso.cola == "HIPOTESIS":
            sug = caso.parcial_sugerido
            st.markdown("**Pago parcial propuesto**")
            st.markdown(
                f"El depósito no alcanza a cubrir ninguna factura completa. La más probable "
                f"es la que vence más cerca del pago:"
            )
            with st.container(horizontal=True):
                st.metric("Factura", sug["factura"], border=True)
                st.metric("Importe total", f"S/ {sug['importe']:,.2f}", border=True)
                st.metric("Se aplica", f"S/ {caso.monto:,.2f}", border=True)
                st.metric("Quedaría pendiente", f"S/ {sug['saldo_restante']:,.2f}",
                          border=True)
            st.markdown(f":orange[La factura queda parcialmente pagada. El saldo de "
                        f"**S/ {sug['saldo_restante']:,.2f}** sigue en cobranza.]")

        else:  # INVESTIGAR — no hay propuesta: el operador arma la respuesta
            st.markdown("**Nada encaja — arma la aplicación a mano**")
            st.markdown(f"El cliente tiene **{caso.n_candidatas}** factura(s) abierta(s) ese día "
                        f"y ninguna combinación suma S/ {caso.monto:,.2f}.")
            abiertas = {a["factura"]: a for a in caso.abiertas}
            elegidas = st.multiselect(
                "Marca las facturas que crees que cubre este depósito",
                options=sorted(abiertas, key=lambda n: -abiertas[n]["importe"]),
                format_func=lambda n: f"{n} — S/ {abiertas[n]['importe']:,.2f}",
                key=f"sel_{caso_id}",
            )
            if elegidas:
                suma = sum(abiertas[n]["importe"] for n in elegidas)
                dif = suma - caso.monto
                st.markdown(f"Seleccionado **S/ {suma:,.2f}** · Depósito "
                            f"**S/ {caso.monto:,.2f}** · " +
                            (":green[cuadra]" if abs(dif) < 0.005
                             else f":orange[diferencia S/ {dif:,.2f}]"))
            else:
                st.caption("Sin selección todavía. Si el depósito no es de este cliente, "
                           "recházalo con el motivo correspondiente.")

        st.info(caso.explicacion, icon=":material/lightbulb:")

with der:
    with st.container(border=True):
        st.markdown("**Decisión**")

        if caso.cola == "CONFIRMAR":
            st.button("Confirmar propuesta", icon=":material/check:", type="primary",
                      width="stretch", on_click=registrar,
                      args=(caso_id, "CONFIRMADO", caso.cola, float(caso.monto)))
        elif caso.cola == "HIPOTESIS":
            st.button("Aplicar como pago parcial", icon=":material/check:", type="primary",
                      width="stretch", on_click=registrar,
                      args=(caso_id, "PARCIAL_APLICADO", caso.cola, float(caso.monto),
                            f"a {caso.parcial_sugerido['factura']}, queda "
                            f"S/ {caso.parcial_sugerido['saldo_restante']:,.2f}"))
        else:
            elegidas = st.session_state.get(f"sel_{caso_id}", [])
            st.button(f"Aplicar a {len(elegidas)} factura(s)", icon=":material/check:",
                      type="primary", width="stretch", disabled=not elegidas,
                      on_click=registrar,
                      args=(caso_id, "RESUELTO_MANUAL", caso.cola, float(caso.monto),
                            ", ".join(elegidas)))

        motivo = st.selectbox("Motivo del rechazo", MOTIVOS, key="motivo")
        st.button("Rechazar y escalar", icon=":material/flag:", width="stretch",
                  on_click=registrar,
                  args=(caso_id, "RECHAZADO", caso.cola, float(caso.monto), motivo))
        st.button("Saltar por ahora", icon=":material/skip_next:", width="stretch",
                  on_click=registrar, args=(caso_id, "POSPUESTO", caso.cola, float(caso.monto)))

    if caso.cola == "CONFIRMAR" and caso.alternativas:
        with st.expander(f"Ver {len(caso.alternativas)} combinación(es) alternativa(s)"):
            for i, alt in enumerate(caso.alternativas, 2):
                total = sum(detalle[n]["total"] for n in alt)
                st.markdown(f"**Opción {i}** — {len(alt)} factura(s), S/ {total:,.2f}")
                st.caption(" · ".join(alt))

    if caso.cola == "INVESTIGAR":
        with st.expander(f"Ver las {caso.n_candidatas} facturas abiertas del cliente"):
            st.dataframe(
                pd.DataFrame(caso.abiertas).sort_values("importe", ascending=False),
                hide_index=True, width="stretch",
                column_config={"factura": "Factura",
                               "vence": st.column_config.DateColumn("Vence", format="DD/MM/YYYY"),
                               "importe": st.column_config.NumberColumn("Importe",
                                                                        format="S/ %.2f")},
            )

if st.session_state.decisiones:
    with st.expander(f"Registro de auditoría de esta sesión "
                     f"({len(st.session_state.decisiones)} decisiones)"):
        st.dataframe(
            pd.DataFrame([{"caso": k, **v} for k, v in st.session_state.decisiones.items()]),
            hide_index=True, width="stretch")
