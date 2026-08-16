"""Pantalla 0 — cargar los archivos del período.

De aquí entra la información al sistema. Cada archivo pasa por la misma
validación que se usa al leerlos del disco: se comprueba que estén las columnas
necesarias y se detecta solo el formato de fecha de cada una.
"""

import streamlit as st

import carga
import contrato

TABLAS = {
    "pagos": ("Depósitos del banco", "Lo que entró en el período: empresa, monto y fecha."),
    "facturas": ("Facturas emitidas", "Contra qué se concilian los depósitos."),
    "notas_credito": ("Notas de crédito", "Correcciones que reducen lo facturado."),
    "clientes": ("Maestro de clientes", "Situación tributaria, para el riesgo de impago."),
    "fija": ("Planta fija", "Servicios activos, para detectar lo no facturado."),
    "movil": ("Planta móvil", "Líneas activas, mismo propósito."),
}

st.session_state.setdefault("subidos", {})

st.title("Cargar información")
st.caption("Los archivos del período. Se validan al cargarlos, antes de procesar nada.")

col_izq, col_der = st.columns([3, 2])

with col_izq:
    with st.container(border=True):
        st.markdown("**Formato esperado**")
        st.markdown(
            "Archivos de texto separados por `|` (barra vertical), como los exporta el "
            "sistema de facturación. Si el suyo usa otro separador o codificación, "
            "indíquelo abajo antes de cargar."
        )
        c1, c2 = st.columns(2)
        sep = c1.selectbox("Separador", ["|", ";", ",", "tabulador"], key="sep")
        enc = c2.selectbox("Codificación", ["latin-1", "utf-8", "cp1252"], key="enc")
        sep_real = "\t" if sep == "tabulador" else sep

with col_der:
    with st.container(border=True):
        st.markdown("**Origen actual**")
        if st.session_state.subidos:
            st.success(f"{len(st.session_state.subidos)} de {len(TABLAS)} archivos cargados "
                       f"en esta sesión", icon=":material/cloud_upload:")
        else:
            st.info("Se están usando los archivos de la carpeta del sistema.",
                    icon=":material/folder:")
        if st.session_state.subidos:
            st.button("Descartar y volver a los del sistema", icon=":material/restart_alt:",
                      width="stretch",
                      on_click=lambda: (st.session_state.subidos.clear(),
                                        carga.todo.clear()))

st.subheader("Archivos")

for tabla, (titulo, para_que) in TABLAS.items():
    with st.container(border=True):
        izq, der = st.columns([3, 2])

        with izq:
            st.markdown(f"**{titulo}**")
            st.caption(para_que)
            requeridas = ", ".join(f"`{c}`" for c in contrato.ESQUEMA[tabla]["columnas"])
            st.caption(f"Columnas necesarias: {requeridas}")

        with der:
            archivo = st.file_uploader(titulo, type=["csv", "txt"], key=f"up_{tabla}",
                                       label_visibility="collapsed")
            if archivo is None:
                if tabla in st.session_state.subidos:
                    del st.session_state.subidos[tabla]
                continue

            ok, informe, _ = contrato.validar(tabla, archivo, sep=sep_real, encoding=enc)
            if ok:
                st.success("Válido — listo para procesar", icon=":material/check_circle:")
                st.session_state.subidos[tabla] = archivo
            else:
                falta = [l.split()[1] for l in informe if l.strip().startswith("✗ FALTA")]
                if falta:
                    st.error(f"Faltan columnas: {', '.join(falta)}. Revise que el export "
                             f"las incluya, o vuelva a generarlo con el juego completo.",
                             icon=":material/error:")
                else:
                    st.error("El separador o la codificación no coinciden. Pruebe con otra "
                             "combinación arriba y vuelva a cargar el archivo.",
                             icon=":material/error:")
                st.session_state.subidos.pop(tabla, None)

            with st.expander("Ver revisión del archivo"):
                for linea in informe:
                    st.text(linea)

st.divider()

listos = len(st.session_state.subidos)
if listos == 0:
    st.info("Sin archivos cargados: el sistema seguirá usando los de su carpeta. "
            "Puede ir directamente a **Informe** o **Verificación**.",
            icon=":material/info:")
elif listos < len(TABLAS):
    faltan = [TABLAS[t][0] for t in TABLAS if t not in st.session_state.subidos]
    st.warning(f"Faltan {len(faltan)}: {', '.join(faltan)}. Para procesar hace falta el "
               f"juego completo — los agentes cruzan información entre todos.",
               icon=":material/warning:")
else:
    st.success("Los seis archivos están validados.", icon=":material/task_alt:")
    if st.button("Procesar el período", type="primary", icon=":material/play_arrow:"):
        carga.todo.clear()
        carga.correos_clasificados.clear()
        st.success("Listo. Los resultados están en **Informe** y la cola de trabajo "
                   "en **Verificación**.", icon=":material/check:")
