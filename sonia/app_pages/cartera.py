"""Cartera — la capa analítica: qué no se está cobrando y a quién perseguir.

Separada de la operación a propósito. Aquí no hay nada que resolver caso a caso;
son tres lecturas del estado de las cuentas por cobrar, para decidir dónde poner
el esfuerzo comercial.
"""

import pandas as pd
import streamlit as st

import carga

d = carga.todo()
clasificados, k_cob = carga.correos_clasificados()
k_fac, k_bi = d["k_facturacion"], d["k_bi"]

st.title("Cartera")
st.caption("Fuga de ingresos, riesgo de impago y comunicaciones de clientes")

facturar, cobrar, correos_tab = st.tabs(
    ["Sin facturar", "Riesgo de impago", "Correos de clientes"])

# --- Fuga de ingresos ---------------------------------------------------------
with facturar:
    with st.container(horizontal=True):
        st.metric("Con servicio activo sin facturar", f"{k_fac['clientes_con_fuga']}",
                  border=True)
        st.metric("Nunca facturados", f"{k_fac['nunca_facturados']}", border=True)
        st.metric("Impacto estimado", f"S/ {k_fac['impacto_estimado_soles']:,.0f}",
                  border=True)
        st.metric("Facturas con nota de crédito", f"{k_fac['tasa_error_facturacion_pct']}%",
                  "indicador a reducir", delta_color="off", border=True)

    st.markdown("**Clientes con servicio activo y facturación atrasada**")
    st.dataframe(
        d["impacto"].head(15)[["RAZON_SOCIAL", "tiene_fija", "tiene_movil",
                               "dias_sin_facturar", "nivel_riesgo", "impacto_soles"]],
        hide_index=True, width="stretch",
        column_config={
            "RAZON_SOCIAL": "Cliente", "tiene_fija": "Fijo activo",
            "tiene_movil": "Móvil activo", "dias_sin_facturar": "Días sin facturar",
            "nivel_riesgo": "Riesgo",
            "impacto_soles": st.column_config.NumberColumn("Impacto estimado",
                                                           format="S/ %.2f"),
        },
    )
    st.caption(f"{d['calidad']['facturas_con_nota_credito']} de "
               f"{d['calidad']['total_facturas']:,} facturas requirieron nota de crédito.")

# --- Riesgo de impago ---------------------------------------------------------
with cobrar:
    with st.container(horizontal=True):
        st.metric("Riesgo alto", f"{k_bi['clientes_riesgo_alto']}", "clientes",
                  delta_color="off", border=True)
        st.metric("Lo que deben", f"S/ {k_bi['deuda_de_los_riesgo_alto_soles']:,.0f}",
                  border=True)
        st.metric("Deuda pendiente total", f"S/ {k_bi['deuda_pendiente_total_soles']:,.0f}",
                  "toda la cartera", delta_color="off", border=True)
        st.metric("Mayor concentración", k_bi["bucket_mayor_concentracion"],
                  f"S/ {k_bi['monto_bucket_mayor_soles']:,.0f}",
                  delta_color="off", border=True)

    izq, der = st.columns([3, 2])
    with izq:
        st.markdown("**A quién cobrar primero, y por qué**")
        st.dataframe(
            d["prioridad"][["RAZON_SOCIAL", "nivel_pcd", "facturas_pendientes",
                            "deuda_pendiente", "estrategia"]],
            hide_index=True, width="stretch",
            column_config={
                "RAZON_SOCIAL": "Cliente", "nivel_pcd": "Riesgo",
                "facturas_pendientes": "Facturas",
                "deuda_pendiente": st.column_config.NumberColumn("Deuda", format="S/ %.2f"),
                "estrategia": st.column_config.TextColumn("Estrategia sugerida",
                                                          width="large"),
            },
        )
    with der:
        st.markdown("**Antigüedad de la deuda**")
        st.bar_chart(d["aging"], x="bucket", y="monto_pendiente", height=300)

# --- Correos ------------------------------------------------------------------
with correos_tab:
    with st.container(horizontal=True):
        st.metric("Correos procesados", f"{k_cob['correos_procesados']}", border=True)
        st.metric("Confirman pago", f"{k_cob['confirmaciones_de_pago']}",
                  "pasan a conciliación", delta_color="off", border=True)
        st.metric("Clasificados con", k_cob["motor"], border=True)

    st.dataframe(
        pd.DataFrame(clasificados)[["cliente", "asunto", "categoria", "confianza"]],
        hide_index=True, width="stretch",
        column_config={"cliente": "Cliente", "asunto": "Asunto",
                       "categoria": "Categoría", "confianza": "Confianza"},
    )

    st.markdown("**Qué se hizo con los que confirman pago**")
    for c in clasificados:
        if c["categoria"] != "CONFIRMACION_PAGO":
            continue
        suyos = d["decisiones"][d["decisiones"].cliente == c["cliente"]]
        pend = suyos[suyos.cola != "AUTO"]
        if len(pend):
            st.warning(f"**{c['cliente']}** — {len(pend)} depósito(s) sin conciliar por "
                       f"S/ {pend.monto.sum():,.2f}. Se priorizó en la cola.",
                       icon=":material/priority_high:")
        else:
            st.success(f"**{c['cliente']}** — sus depósitos ya están aplicados. "
                       f"Sacar de la ruta de cobranza.", icon=":material/check_circle:")
