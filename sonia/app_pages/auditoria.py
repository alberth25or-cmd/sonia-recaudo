"""Pantalla 3 — muestreo de auditoría sobre la banda automática.

Responde la pregunta del contralor: "¿cómo saben que lo que se aplica solo no
está equivocado?". Se revisa una muestra del 2% y se registra el resultado.
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

st.title("Muestreo de auditoría")
st.caption("Control sobre los depósitos que se aplican sin que nadie los mire")

hoy = dt.date.today()
periodo = f"{hoy.year}-S{hoy.isocalendar().week:02d}"

with st.sidebar:
    st.subheader("Periodo")
    st.metric("Semana auditada", periodo, border=True)
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

# --- Qué puede y qué no puede detectar ---------------------------------------
with st.expander("Qué puede detectar esta muestra — leer antes de sacar conclusiones"):
    st.markdown(
        f"Muestrear {len(m)} casos **no mide** una tasa del 0.06%: se esperarían "
        f"{len(m) * 0.0006:.2f} errores. Sirve para **detectar una regresión** — que algo "
        f"se rompió y la tasa saltó."
    )
    st.dataframe(
        pd.DataFrame([{"Si la tasa real fuera": f"{p:.2%}",
                       "La muestra la detecta": poder}
                      for p, poder in auditoria.poder_de_deteccion(len(m))]),
        hide_index=True, width="stretch",
        column_config={"La muestra la detecta": st.column_config.ProgressColumn(
            format="percent", min_value=0, max_value=1)},
    )
    st.caption("La tasa base se mide con `python backtest.py` contra el ground truth, "
               "no con este muestreo.")

# --- Revisión caso por caso --------------------------------------------------
st.subheader("Revisión de la muestra")

pendientes = [r for r in m.itertuples() if f"{r.cliente}|{r.fecha}" not in revisados]

if not pendientes:
    st.success(f"Muestra completa: {len(m)} casos revisados, {errores} error(es).")
    if st.button("Registrar la tanda", icon=":material/save:", type="primary"):
        auditoria.registrar_tanda(periodo, len(revisados), errores)
        st.success(f"Tanda {periodo} registrada en `auditorias.csv`.")
else:
    caso = pendientes[0]
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
                column_config={"Vence": st.column_config.DateColumn(format="DD/MM/YYYY"),
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

            st.button("Correcta", icon=":material/check:", type="primary", width="stretch",
                      on_click=marcar, args=("CORRECTO",))
            st.button("Incorrecta — revertir", icon=":material/undo:", width="stretch",
                      on_click=marcar, args=("INCORRECTO",))
            st.caption("Marcar incorrecta revierte la aplicación y devuelve el depósito "
                       "a la cola humana.")

if revisados:
    with st.expander(f"Detalle de lo revisado ({len(revisados)})"):
        st.dataframe(pd.DataFrame([{"caso": k, **v} for k, v in revisados.items()]),
                     hide_index=True, width="stretch")

hist = auditoria.historial()
if len(hist):
    st.subheader("Tendencia entre periodos")
    st.dataframe(hist, hide_index=True, width="stretch")
