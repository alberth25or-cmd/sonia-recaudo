"""Genera el informe HTML de una corrida completa.

Formato heredado del prototipo de Agentes 1551 (generar_reporte_demo.py) —
un informe que se lee de corrido, no una herramienta— con las cifras
verificadas de este motor.

    python reporte.py            # -> informe.html
"""

import datetime as dt
import html
from pathlib import Path

import llm
import datos
from agentes import bi, cobranza, correos, explicador, facturacion, recaudo

SALIDA = Path(__file__).parent / "informe.html"
MAX_CASOS_EXPLICADOS = 10

CSS = """
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#f4f6f8;color:#1a2733}
.wrap{max-width:1500px;margin:0 auto;padding:22px}
header{background:linear-gradient(135deg,#0b3a5d,#12557f);color:#fff;border-radius:10px;
       padding:22px 26px;margin-bottom:22px}
header h1{margin:0;font-size:23px;letter-spacing:.2px}
header p{margin:6px 0 0;opacity:.88;font-size:13.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin-bottom:26px}
.kpi{background:#fff;border-radius:9px;padding:18px 20px;box-shadow:0 1px 3px rgba(16,42,67,.10)}
.kpi .v{font-size:29px;font-weight:700;color:#0b3a5d;line-height:1.15}
.kpi .l{font-size:12.5px;color:#5c7085;margin-top:5px}
.kpi.alerta .v{color:#b4451f}
h2{font-size:15px;margin:30px 0 11px;color:#0b3a5d;font-weight:700}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:9px;overflow:hidden;
      box-shadow:0 1px 3px rgba(16,42,67,.10);font-size:13.5px}
th{background:#0b3a5d;color:#fff;text-align:left;padding:10px 13px;font-weight:600;font-size:12.5px}
td{padding:9px 13px;border-top:1px solid #edf1f5;vertical-align:top}
tr:nth-child(even) td{background:#fafbfc}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;padding:2px 10px;border-radius:11px;font-size:11.5px;font-weight:600;color:#fff}
.p-auto{background:#1e7a46}.p-conf{background:#1b6ca8}.p-hip{background:#c9761a}
.p-inv{background:#b4451f}.p-alto{background:#b4451f}.p-crit{background:#7d1f1f}
.log{background:#0f1f2e;color:#c8d6e2;border-radius:9px;padding:15px 17px;font:12.5px/1.75
     ui-monospace,'Cascadia Code',Consolas,monospace;max-height:420px;overflow:auto}
.log .ag{color:#6cc5ff;font-weight:600}.log .ts{color:#5c7085}
.nota{background:#fff8e6;border-left:4px solid #d9a520;border-radius:0 8px 8px 0;
      padding:14px 18px;margin:16px 0;font-size:13.5px}
.nota b{color:#8a6400}
.ok{color:#1e7a46;font-weight:600}.no{color:#b4451f;font-weight:600}
footer{margin:34px 0 10px;color:#5c7085;font-size:12.5px;text-align:center}
"""


def e(x):
    return html.escape(str(x))


def kpi(valor, etiqueta, alerta=False):
    return (f'<div class="kpi{" alerta" if alerta else ""}">'
            f'<div class="v">{e(valor)}</div><div class="l">{e(etiqueta)}</div></div>')


def tabla(cabeceras, filas):
    th = "".join(f"<th>{e(c)}</th>" for c in cabeceras)
    tr = "".join("<tr>" + "".join(celdas) + "</tr>" for celdas in filas)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>"


def pill(texto, clase):
    return f'<span class="pill {clase}">{e(texto)}</span>'


def main():
    print("Corriendo el ciclo completo...")
    f, p, ncs = datos.facturas(), datos.pagos(), datos.notas_credito()
    clientes, fija, movil = datos.clientes(), datos.planta_fija(), datos.planta_movil()

    decisiones = recaudo.procesar(f, p)
    k_rec = recaudo.kpis(decisiones)

    fuga = facturacion.detectar_fuga(fija, movil, f)
    impacto = facturacion.estimar_impacto(fuga, f)
    cal = facturacion.calidad(f, ncs)
    k_fac = facturacion.kpis(fuga, impacto, cal)

    pcd = bi.calcular_pcd(clientes, f, p)
    aging = bi.calcular_aging(f, p)
    prioridad = bi.priorizar(pcd, fuga)
    k_bi = bi.kpis(pcd, aging)

    clasificados = cobranza.clasificar_lote(correos.CORREOS)
    k_cob = cobranza.kpis(clasificados)

    pendientes = decisiones[decisiones.cola != "AUTO"]
    carga = recaudo.carga_humana(decisiones)
    minutos = carga["minutos_por_dia_habil"]

    print(f"Redactando {MAX_CASOS_EXPLICADOS} explicaciones con {llm.etiqueta()}...")
    muestra = pendientes.nlargest(MAX_CASOS_EXPLICADOS, "monto").to_dict("records")
    for c in muestra:
        c["texto"] = explicador.explicar(c)

    # ---------------------------------------------------------------- armado
    partes = [f"<style>{CSS}</style>", '<div class="wrap">']

    partes.append(f"""<header>
      <h1>SON-IA · equipo de agentes para el ciclo de ingreso</h1>
      <p>Reto 3 · Integratel B2B — corrida completa sobre el dataset del reto
      ({len(f):,} facturas · {len(p):,} pagos). Motor de lenguaje: {e(llm.etiqueta())}.
      Generado {dt.datetime.now():%d/%m/%Y %H:%M}</p></header>""")

    partes.append('<div class="grid">' + "".join([
        kpi(f"{k_rec['stp_pct']}%", "STP — depósitos aplicados sin intervención humana"),
        kpi(f"{k_rec['depositos_procesados']:,}", "Depósitos procesados"),
        kpi(f"S/ {k_rec['monto_aplicado_solo_soles']:,.0f}", "Aplicado sin que nadie lo mire"),
        kpi("1 de 1,596", "Tasa de error en la banda automática"),
        kpi(f"{len(pendientes):,}", "Casos en cola humana", alerta=True),
        kpi(f"{minutos:.0f} min", "Carga humana por día hábil"),
        kpi(f"{carga['fte']} FTE", "Personal necesario"),
        kpi("4", "Agentes operadores + supervisor"),
        kpi(f"{k_fac['clientes_con_fuga']}", "Clientes con servicio activo sin facturar"),
        kpi(f"{k_fac['tasa_error_facturacion_pct']}%", "Notas de crédito (línea base a reducir)"),
        kpi(f"{k_bi['clientes_riesgo_alto']}", "Clientes en riesgo alto de impago"),
        kpi(f"{k_cob['confirmaciones_de_pago']}/{k_cob['correos_procesados']}",
            "Correos que confirman pago → van a Recaudo"),
    ]) + "</div>")

    partes.append("""<div class="nota">
      <b>Cómo se midió.</b> El dataset del reto es <b>sintético</b>. Para medir de verdad
      escondimos la columna <code>FACTURA_AFECTADA</code> —que es la respuesta que hoy produce
      a mano un analista— y reconstruimos cada depósito como llega del banco: empresa, monto y
      fecha. El motor resuelve sin verla; esa columna solo se usa después, para calificar la
      propuesta. Por eso <b>no decimos "Integratel está en X%"</b>: lo medible es lo que este
      motor logra sobre estos datos.
    </div>""")

    # Colas
    partes.append("<h2>Las cuatro colas — dónde entra el humano</h2>")
    clases = {"AUTO": "p-auto", "CONFIRMAR": "p-conf", "HIPOTESIS": "p-hip", "INVESTIGAR": "p-inv"}
    filas = []
    for cola, desc in recaudo.COLAS.items():
        sub = decisiones[decisiones.cola == cola]
        seg = recaudo.SEGUNDOS_POR_CASO[cola]
        filas.append([
            f"<td>{pill(cola, clases[cola])}</td>",
            f"<td>{e(desc)}</td>",
            f'<td class="num">{len(sub):,}</td>',
            f'<td class="num">{len(sub) / len(decisiones):.1%}</td>',
            f'<td class="num">S/ {sub.monto.sum():,.2f}</td>',
            f'<td class="num">{len(sub) * seg / 60 / recaudo.DIAS_HABILES_VENTANA:.0f} min</td>',
        ])
    partes.append(tabla(["Cola", "Qué hace el humano", "Casos", "%", "Monto", "Min/día"], filas))

    # Casos con explicación
    partes.append("<h2>Casos escalados, con la explicación que lee el operador</h2>")
    filas = [[
        f"<td>{e(c['cliente'])}</td>",
        f'<td class="num">{c["fecha"]:%d/%m/%Y}</td>',
        f'<td class="num">S/ {c["monto"]:,.2f}</td>',
        f"<td>{pill(c['cola'], clases[c['cola']])}</td>",
        f'<td class="num">{c["n_candidatas"]}</td>',
        f"<td>{e(c['texto'])}</td>",
    ] for c in muestra]
    partes.append(tabla(["Cliente", "Fecha", "Depósito", "Cola", "Facturas abiertas",
                         "Explicación del agente"], filas))

    # Cobranza
    partes.append("<h2>Agente de Cobranza — correos clasificados</h2>")
    cls = {"CONFIRMACION_PAGO": "p-auto", "RECLAMO_MONTO": "p-inv",
           "SOLICITUD_DOCUMENTO": "p-conf", "RECLAMO_SERVICIO": "p-hip", "OTRO": "p-hip"}
    filas = [[
        f"<td>{e(c['cliente'])}</td>",
        f"<td>{e(c['asunto'])}</td>",
        f"<td>{pill(c['categoria'], cls.get(c['categoria'], 'p-hip'))}</td>",
        f'<td class="num">{c["confianza"]}</td>',
    ] for c in clasificados]
    partes.append(tabla(["Cliente", "Asunto", "Categoría", "Confianza"], filas))

    # Facturación
    partes.append("<h2>Agente de Facturación — fuga de ingresos</h2>")
    filas = [[
        f"<td>{e(r.RAZON_SOCIAL)}</td>",
        f'<td>{"Sí" if r.tiene_fija else "—"}</td>',
        f'<td>{"Sí" if r.tiene_movil else "—"}</td>',
        f'<td class="num">{"Nunca" if r.nunca_facturado else f"{r.dias_sin_facturar:,}"}</td>',
        f"<td>{pill(r.nivel_riesgo, 'p-crit' if r.nivel_riesgo == 'CRITICO' else 'p-alto')}</td>",
        f'<td class="num">S/ {r.impacto_soles:,.2f}</td>',
    ] for r in impacto.head(10).itertuples()]
    partes.append(tabla(["Cliente", "Fijo activo", "Móvil activo", "Días sin facturar",
                         "Riesgo", "Impacto estimado"], filas))

    # BI
    partes.append("<h2>Agente de BI — priorización de cobranza</h2>")
    filas = [[
        f"<td>{e(r.RAZON_SOCIAL)}</td>",
        f"<td>{pill(r.nivel_pcd, 'p-alto' if r.nivel_pcd == 'ALTO' else 'p-hip')}</td>",
        f'<td class="num">{r.facturas_pendientes}</td>',
        f'<td class="num">S/ {r.deuda_pendiente:,.2f}</td>',
        f"<td>{e(r.estrategia)}</td>",
    ] for r in prioridad.head(8).itertuples()]
    partes.append(tabla(["Cliente", "Riesgo PCD", "Facturas pendientes", "Deuda pendiente",
                         "Estrategia sugerida"], filas))

    # Procedencia
    partes.append("<h2>Qué es hallazgo del negocio y qué es artefacto del generador</h2>")
    hallazgos = [
        ("El RUC no sirve como llave (450 de 999 discrepan). RAZON_SOCIAL cruza 3,383 de 3,383",
         True, "Presentable — es la trampa de anonimización"),
        ("COD_CUENTA arrastra la misma inconsistencia (239 de 240)", True,
         "Presentable — hallazgo de Agentes 1551"),
        ("23 facturas sin pago son anteriores a la ventana de datos: no son mora", True,
         "Presentable — es rigor metodológico"),
        ("5.8% de pagos anteriores a su factura", False,
         "Con cuidado — se concentra en 9-15 días: parece frontera de ciclo del generador"),
        ("74 pagos huérfanos por S/ 106,289", False,
         "NO presentar — 92% apunta a series válidas inexistentes: desacople del generador"),
    ]
    filas = [[
        f"<td>{e(t)}</td>",
        f'<td class="{"ok" if ok else "no"}">{"Sí" if ok else "No"}</td>',
        f"<td>{e(nota)}</td>",
    ] for t, ok, nota in hallazgos]
    partes.append(tabla(["Hallazgo", "¿Del negocio?", "Cómo tratarlo"], filas))

    partes.append("""<div class="nota">
      <b>Probamos que el LLM mejorara la elección entre combinaciones ambiguas y resultó falso.</b>
      Sobre 108 casos: heurística determinista 74.1%, agente on-premise 66.7% — siete puntos peor.
      Por eso esa cola la resuelve la regla. El modelo aporta donde no hay regla que aplicar:
      explicar cada caso al operador y clasificar los correos entrantes, ambos corriendo aquí.
    </div>""")

    # Log
    partes.append("<h2>Log de auditoría — trazabilidad de cada decisión</h2>")
    ahora = f"{dt.datetime.now():%Y-%m-%dT%H:%M:%S}"
    lineas = [
        ("Supervisor", f"Delegando {len(decisiones):,} depósitos al Agente de Recaudo"),
        ("Recaudo", f"STP {k_rec['stp_pct']}% · S/ {k_rec['monto_aplicado_solo_soles']:,.2f} "
                    f"aplicados sin intervención"),
        ("Supervisor", f"{len(pendientes):,} casos encolados para revisión humana "
                       f"({minutos:.0f} min/día hábil)"),
        ("Supervisor", "Delegando análisis de planta vs. facturación"),
        ("Facturación", f"{k_fac['clientes_con_fuga']} clientes con servicio activo y "
                        f"facturación atrasada · impacto S/ {k_fac['impacto_estimado_soles']:,.2f}"),
        ("Facturación", f"Tasa de notas de crédito {k_fac['tasa_error_facturacion_pct']}% "
                        f"({cal['facturas_con_nota_credito']} de {cal['total_facturas']:,})"),
        ("Supervisor", "Delegando a BI los resultados de Recaudo + Facturación"),
        ("BI", f"{k_bi['clientes_riesgo_alto']} clientes en riesgo ALTO, que deben "
               f"S/ {k_bi['deuda_de_los_riesgo_alto_soles']:,.2f} de un pendiente total de "
               f"S/ {k_bi['deuda_pendiente_total_soles']:,.2f}"),
        ("BI", f"Mayor concentración en '{k_bi['bucket_mayor_concentracion']}' con "
               f"S/ {k_bi['monto_bucket_mayor_soles']:,.2f}"),
        ("Supervisor", f"Delegando {len(clasificados)} correos al Agente de Cobranza"),
        ("Cobranza", f"Clasificados con {llm.etiqueta()} — " +
                     ", ".join(f"{k}={v}" for k, v in k_cob["distribucion"].items())),
    ]
    for c in clasificados:
        if c["categoria"] == "CONFIRMACION_PAGO":
            suyos = decisiones[decisiones.cliente == c["cliente"]]
            pend = suyos[suyos.cola != "AUTO"]
            lineas.append(("Cobranza", f"{c['cliente']} dice haber pagado y tiene "
                                       f"{len(pend)} depósito(s) sin conciliar por "
                                       f"S/ {pend.monto.sum():,.2f} — Recaudo prioriza"
                           if len(pend) else
                           f"{c['cliente']} dice haber pagado y sus depósitos ya están "
                           f"aplicados — sacar de la ruta de cobranza"))
    partes.append('<div class="log">' + "".join(
        f'<div><span class="ts">{ahora}</span> <span class="ag">[{e(a)}]</span> {e(t)}</div>'
        for a, t in lineas) + "</div>")

    partes.append(f"""<footer>
      Reproducible: <code>python orquestador.py</code> · precisión medida con
      <code>python backtest.py</code> · carga humana con <code>python triaje.py</code> ·
      procedencia de los hallazgos con <code>python procedencia.py</code>
    </footer></div>""")

    SALIDA.write_text("".join(partes), encoding="utf-8")
    print(f"\nInforme escrito en {SALIDA}")
    print(f"  STP {k_rec['stp_pct']}% · {len(pendientes):,} casos en cola · {minutos:.0f} min/día")


if __name__ == "__main__":
    main()
