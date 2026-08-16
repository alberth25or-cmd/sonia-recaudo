"""Control — verificar la parte automática y revisar lo decidido a mano.

Dos trabajos distintos que comparte la misma persona: comprobar por muestreo que
lo aplicado sin supervisión sigue bien, y poder rendir cuentas de cada decisión
que tomó un analista.
"""

import datetime as dt

import pandas as pd
import streamlit as st

import auditoria
import carga

st.session_state.setdefault("audit", {})

d = carga.todo()
decisiones = d["decisiones"]
auto = decisiones[decisiones.cola == "AUTO"]
detalle = d["detalle"]

st.title("Control")
st.caption("Verificar la parte automática y revisar lo que se decidió a mano")

hoy = dt.date.today()
periodo = f"{hoy.year}-S{hoy.isocalendar().week:02d}"

muestreo, trazabilidad = st.tabs(["Muestreo de la banda automática",
                                  "Decisiones de esta sesión"])

# =============================================================== MUESTREO
with muestreo:
    with st.sidebar:
        st.subheader("Periodo auditado")
        st.metric("Semana", periodo, border=True)
        pct = st.slider("Tamaño de la muestra", 0.01, 0.10, auditoria.PORCENTAJE,
                        step=0.01, format="%.0f%%")
        st.caption("La muestra es reproducible: la semilla sale del periodo, así que "
                   "auditar la misma semana dos veces devuelve los mismos casos.")

    m = auditoria.muestra(decisiones, periodo, pct)
    revisados = {k: v for k, v in st.session_state.audit.items()
                 if k in set(f"{r.cliente}|{r.fecha}" for r in m.itertuples())}
    errores = sum(1 for v in revisados.values() if v["veredicto"] == "INCORRECTO")

    with st.container(horizontal=True):
        st.metric("Aplicados sin revisión", f"{len(auto):,}", border=True)
        st.metric("Muestra", f"{len(m)}", f"{len(m) * 20 / 60:.0f} min de trabajo",
                  delta_color="off", border=True)
        st.metric("Revisados", f"{len(revisados)}/{len(m)}", border=True)
        st.metric("Errores encontrados", f"{errores}",
                  delta_color="inverse" if errores else "off", border=True)

    estado, mensaje = auditoria.evaluar(len(revisados), errores)
    {"ok": st.success, "atencion": st.warning, "alerta": st.error,
     "pendiente": st.info}[estado](mensaje, icon=":material/verified:")

    with st.expander("Qué puede detectar esta muestra — leer antes de sacar conclusiones"):
        st.markdown(
            f"Muestrear {len(m)} casos **no mide** una tasa del 0.06%: se esperarían "
            f"{len(m) * 0.0006:.2f} errores. Sirve para **detectar una regresión** — que "
            f"algo se rompió y la tasa saltó."
        )
        st.dataframe(
            pd.DataFrame([{"Si la tasa real fuera": f"{p:.2%}",
                           "La muestra la detecta": poder}
                          for p, poder in auditoria.poder_de_deteccion(len(m))]),
            hide_index=True, width="stretch",
            column_config={"La muestra la detecta": st.column_config.ProgressColumn(
                format="percent", min_value=0, max_value=1)},
        )
        st.caption("Este control detecta que algo cambió. No sustituye a la validación "
                   "periódica del motor contra casos ya resueltos.")

    st.subheader("Revisión de la muestra")
    por_revisar = [r for r in m.itertuples() if f"{r.cliente}|{r.fecha}" not in revisados]

    if not por_revisar:
        st.success(f"Muestra completa: {len(m)} casos revisados, {errores} error(es).",
                   icon=":material/task_alt:")
        if st.button("Registrar la tanda", icon=":material/save:", type="primary"):
            auditoria.registrar_tanda(periodo, len(revisados), errores)
            st.success(f"Tanda {periodo} registrada.")
    else:
        caso = por_revisar[0]
        caso_id = f"{caso.cliente}|{caso.fecha}"
        st.caption(f"Caso {len(revisados) + 1} de {len(m)}")

        izq, der = st.columns([3, 2])
        with izq:
            with st.container(border=True):
                st.markdown("**Lo que el sistema aplicó solo**")
                with st.container(horizontal=True):
                    st.metric("Empresa", caso.cliente, border=True)
                    st.metric("Depósito", f"S/ {caso.monto:,.2f}", border=True)
                    st.metric("Fecha", f"{caso.fecha:%d/%m/%Y}", border=True)
                st.dataframe(
                    pd.DataFrame([{"Factura": n, "Vence": detalle[n]["vto"],
                                   "Importe": detalle[n]["total"]}
                                  for n in caso.facturas_propuestas]),
                    hide_index=True, width="stretch",
                    column_config={
                        "Vence": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Importe": st.column_config.NumberColumn(format="S/ %.2f")},
                )
                st.caption(f"Tenía {caso.n_candidatas} factura(s) abierta(s) ese día y "
                           f"esta fue la única combinación que sumaba exacto.")

        with der:
            with st.container(border=True):
                st.markdown("**¿La aplicación fue correcta?**")

                def marcar(veredicto):
                    st.session_state.audit[caso_id] = {
                        "veredicto": veredicto, "monto": float(caso.monto),
                        "ts": dt.datetime.now().isoformat(timespec="seconds")}

                st.button("Correcta", icon=":material/check:", type="primary",
                          width="stretch", on_click=marcar, args=("CORRECTO",))
                st.button("Incorrecta — revertir", icon=":material/undo:",
                          width="stretch", on_click=marcar, args=("INCORRECTO",))
                st.caption("Marcar incorrecta revierte la aplicación y devuelve el "
                           "depósito a la cola de trabajo.")

    if revisados:
        with st.expander(f"Detalle de lo revisado ({len(revisados)})"):
            st.dataframe(pd.DataFrame([{"caso": k, **v} for k, v in revisados.items()]),
                         hide_index=True, width="stretch")

    hist = auditoria.historial()
    if len(hist):
        st.subheader("Tendencia entre periodos")
        st.dataframe(hist, hide_index=True, width="stretch")

# =========================================================== TRAZABILIDAD
with trazabilidad:
    tomadas = st.session_state.get("decisiones", {})

    if not tomadas:
        st.info("Todavía no se ha resuelto ningún caso en esta sesión. Las decisiones "
                "que se tomen en **Conciliar** aparecerán aquí con su hora y motivo.",
                icon=":material/history:")
    else:
        reg = pd.DataFrame([{"caso": k, **v} for k, v in tomadas.items()])
        conteo = reg.accion.value_counts()

        with st.container(horizontal=True):
            st.metric("Decisiones", f"{len(reg):,}", border=True)
            st.metric("Monto resuelto", f"S/ {reg.monto.sum():,.2f}", border=True)
            st.metric("Rechazados", f"{int(conteo.get('RECHAZADO', 0))}",
                      "vuelven a la cola", delta_color="off", border=True)

        st.dataframe(
            reg, hide_index=True, width="stretch",
            column_config={
                "caso": "Caso", "accion": "Acción", "cola": "Tipo",
                "monto": st.column_config.NumberColumn("Monto", format="S/ %.2f"),
                "motivo": st.column_config.TextColumn("Motivo", width="large"),
                "ts": "Hora"},
        )
        st.download_button(
            "Descargar registro", reg.to_csv(index=False).encode("utf-8"),
            file_name=f"decisiones_{dt.date.today():%Y%m%d}.csv", mime="text/csv",
            icon=":material/download:")
