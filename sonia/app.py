"""SON-IA — una sola app, dos pantallas.

    streamlit run app.py

  Informe       lo que se le muestra al jurado: todo visible de corrido
  Verificación  la herramienta del operador: un caso a la vez, confirmar o rechazar
  Auditoría     el control: muestreo del 2% sobre lo que se aplicó solo

Todo lo demás del proyecto corre en terminal y no tiene pantalla:
    python orquestador.py     el ciclo completo con log de auditoría
    python backtest.py        precisión medida contra ground truth
    python reporte.py         exporta el informe como HTML para enviar por correo
"""

import streamlit as st

st.set_page_config(page_title="SON-IA", page_icon=":material/hub:", layout="wide")

nav = st.navigation([
    st.Page("app_pages/informe.py", title="Informe", icon=":material/analytics:", default=True),
    st.Page("app_pages/verificacion.py", title="Verificación", icon=":material/fact_check:"),
    st.Page("app_pages/auditoria.py", title="Auditoría", icon=":material/verified_user:"),
])
nav.run()
