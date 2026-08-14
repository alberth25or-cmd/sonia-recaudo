"""Pantalla 1 — el informe. Todo visible de corrido, sin interacción necesaria."""

import pandas as pd
import streamlit as st

import carga
import llm

d = carga.todo()
clasificados, k_cob = carga.correos_clasificados()

k_rec, k_fac, k_bi = d["k_recaudo"], d["k_facturacion"], d["k_bi"]
decisiones = d["decisiones"]
pendientes = decisiones[decisiones.cola != "AUTO"]

st.title("SON-IA · equipo de agentes para el ciclo de ingreso")
st.caption(
    f"Reto 3 · Integratel B2B — corrida completa sobre el dataset del reto "
    f"({len(d['facturas']):,} facturas · {len(decisiones):,} depósitos). "
    f"Motor de lenguaje: {llm.etiqueta()}."
)

# --- Indicadores -------------------------------------------------------------
with st.container(horizontal=True):
    st.metric("STP", f"{k_rec['stp_pct']}%", "aplicados sin intervención humana",
              delta_color="off", border=True)
    st.metric("Aplicado solo", f"S/ {k_rec['monto_aplicado_solo_soles']:,.0f}",
              f"{k_rec['aplicados_sin_intervencion']:,} depósitos",
              delta_color="off", border=True)
    st.metric("Error en banda automática", "1 de 1,596", "0.06%",
              delta_color="off", border=True)
    st.metric("Cola humana", f"{len(pendientes):,}",
              f"{d['carga']['minutos_por_dia_habil']:.0f} min/día · "
              f"{d['carga']['fte']} FTE", delta_color="off", border=True)

with st.container(horizontal=True):
    st.metric("Fuga de ingresos", f"{k_fac['clientes_con_fuga']}",
              "clientes con servicio activo sin facturar", delta_color="off", border=True)
    st.metric("Notas de crédito", f"{k_fac['tasa_error_facturacion_pct']}%",
              "línea base a reducir", delta_color="off", border=True)
    st.metric("Riesgo alto de impago", f"{k_bi['clientes_riesgo_alto']}",
              f"deben S/ {k_bi['deuda_de_los_riesgo_alto_soles']:,.0f}",
              delta_color="off", border=True)
    st.metric("Correos que confirman pago",
              f"{k_cob['confirmaciones_de_pago']}/{k_cob['correos_procesados']}",
              "van al Agente de Recaudo", delta_color="off", border=True)

st.info(
    "**Cómo se midió.** El dataset del reto es **sintético**. Para medir de verdad escondimos "
    "`FACTURA_AFECTADA` —la respuesta que hoy produce a mano un analista— y reconstruimos cada "
    "depósito como llega del banco: empresa, monto y fecha. El motor resuelve sin verla; esa "
    "columna solo se usa después, para calificar la propuesta. Por eso **no decimos "
    "\"Integratel está en X%\"**: lo medible es lo que este motor logra sobre estos datos.",
    icon=":material/science:",
)

# --- Colas -------------------------------------------------------------------
st.subheader("Las cuatro colas — dónde entra el humano")
st.dataframe(
    carga.tabla_colas(decisiones), hide_index=True, width="stretch",
    column_config={
        "% del total": st.column_config.NumberColumn(format="percent"),
        "Monto": st.column_config.NumberColumn(format="S/ %.2f"),
        "Casos": st.column_config.NumberColumn(format="%d"),
    },
)

# --- Los cuatro agentes ------------------------------------------------------
st.subheader("Los cuatro agentes operadores")
recaudo_tab, fact_tab, bi_tab, cob_tab = st.tabs(
    ["Recaudo", "Facturación", "Inteligencia de negocio", "Cobranza"])

with recaudo_tab:
    st.markdown("**Casos escalados de mayor monto** — lo que ve el operador en su cola")
    muestra = pendientes.nlargest(12, "monto")[
        ["cliente", "fecha", "monto", "cola", "n_candidatas", "explicacion"]]
    st.dataframe(
        muestra, hide_index=True, width="stretch",
        column_config={
            "cliente": "Cliente", "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "monto": st.column_config.NumberColumn("Depósito", format="S/ %.2f"),
            "cola": "Cola", "n_candidatas": "Facturas abiertas",
            "explicacion": st.column_config.TextColumn("Por qué se escaló", width="large"),
        },
    )

with fact_tab:
    st.markdown("**Clientes con servicio activo y facturación atrasada**")
    st.dataframe(
        d["impacto"].head(12)[["RAZON_SOCIAL", "tiene_fija", "tiene_movil",
                               "dias_sin_facturar", "nivel_riesgo", "impacto_soles"]],
        hide_index=True, width="stretch",
        column_config={
            "RAZON_SOCIAL": "Cliente", "tiene_fija": "Fijo activo", "tiene_movil": "Móvil activo",
            "dias_sin_facturar": "Días sin facturar", "nivel_riesgo": "Riesgo",
            "impacto_soles": st.column_config.NumberColumn("Impacto estimado", format="S/ %.2f"),
        },
    )
    st.caption(f"Tasa de notas de crédito: {d['calidad']['tasa_error_pct']}% "
               f"({d['calidad']['facturas_con_nota_credito']} de "
               f"{d['calidad']['total_facturas']:,}) — el indicador que la ficha pide reducir.")

with bi_tab:
    izq, der = st.columns([3, 2])
    with izq:
        st.markdown("**A quién cobrar primero, y por qué**")
        st.dataframe(
            d["prioridad"][["RAZON_SOCIAL", "nivel_pcd", "facturas_pendientes",
                            "deuda_pendiente", "estrategia"]],
            hide_index=True, width="stretch",
            column_config={
                "RAZON_SOCIAL": "Cliente", "nivel_pcd": "Riesgo",
                "facturas_pendientes": "Facturas", "estrategia": st.column_config.TextColumn(
                    "Estrategia sugerida", width="large"),
                "deuda_pendiente": st.column_config.NumberColumn("Deuda", format="S/ %.2f"),
            },
        )
    with der:
        st.markdown("**Antigüedad de la deuda**")
        st.bar_chart(d["aging"], x="bucket", y="monto_pendiente", height=280)

with cob_tab:
    st.markdown(f"**Correos entrantes clasificados** — motor: {k_cob['motor']}")
    st.dataframe(
        pd.DataFrame(clasificados)[["cliente", "asunto", "categoria", "confianza"]],
        hide_index=True, width="stretch",
        column_config={"cliente": "Cliente", "asunto": "Asunto",
                       "categoria": "Categoría", "confianza": "Confianza"},
    )
    st.markdown("**Traspaso a Recaudo** — el ciclo entre agentes cerrándose")
    for c in clasificados:
        if c["categoria"] != "CONFIRMACION_PAGO":
            continue
        suyos = decisiones[decisiones.cliente == c["cliente"]]
        pend = suyos[suyos.cola != "AUTO"]
        if len(pend):
            st.warning(f"**{c['cliente']}** dice haber pagado y tiene {len(pend)} depósito(s) "
                       f"sin conciliar por S/ {pend.monto.sum():,.2f} — Recaudo prioriza el caso",
                       icon=":material/priority_high:")
        else:
            st.success(f"**{c['cliente']}** dice haber pagado y sus depósitos ya están aplicados "
                       f"— sacar de la ruta de cobranza, no volver a llamarlo",
                       icon=":material/check_circle:")

# --- Rigor -------------------------------------------------------------------
st.subheader("Qué es hallazgo del negocio y qué es artefacto del generador")
st.dataframe(
    pd.DataFrame([
        {"Hallazgo": "El RUC no sirve como llave (450 de 999 discrepan). RAZON_SOCIAL cruza 3,383 de 3,383",
         "¿Del negocio?": "Sí", "Cómo tratarlo": "Presentable — es la trampa de anonimización"},
        {"Hallazgo": "COD_CUENTA arrastra la misma inconsistencia (239 de 240)",
         "¿Del negocio?": "Sí", "Cómo tratarlo": "Presentable — hallazgo de Agentes 1551"},
        {"Hallazgo": "23 facturas sin pago son anteriores a la ventana de datos",
         "¿Del negocio?": "Sí", "Cómo tratarlo": "Presentable — es rigor metodológico"},
        {"Hallazgo": "5.8% de pagos anteriores a su factura", "¿Del negocio?": "Con cuidado",
         "Cómo tratarlo": "Se concentra en 9–15 días: parece frontera de ciclo del generador"},
        {"Hallazgo": "74 pagos huérfanos por S/ 106,289", "¿Del negocio?": "No",
         "Cómo tratarlo": "92% apunta a series válidas inexistentes: desacople del generador"},
    ]),
    hide_index=True, width="stretch",
    column_config={"Hallazgo": st.column_config.TextColumn(width="large"),
                   "Cómo tratarlo": st.column_config.TextColumn(width="large")},
)

st.warning(
    "**Probamos que el LLM eligiera mejor que la heurística entre combinaciones ambiguas, "
    "y resultó falso.** Sobre 108 casos: heurística determinista 74.1%, agente on-premise "
    "66.7% — siete puntos peor. Por eso esa cola la resuelve la regla. El modelo aporta donde "
    "no hay regla que aplicar: explicar cada caso y clasificar los correos, ambos corriendo aquí.",
    icon=":material/experiment:",
)

st.caption("Reproducible: `python orquestador.py` · precisión con `python backtest.py` · "
           "procedencia con `python procedencia.py` · exportar a HTML con `python reporte.py`")
