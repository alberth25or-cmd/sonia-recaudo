"""Torre de control — una sola página, interactiva, con todo dentro.

DECISIÓN DE DISEÑO QUE ORDENA TODO LO DEMÁS
-------------------------------------------
El motor clasifica cada depósito en cuatro colas según cuánta ayuda puede dar.
Eso es un detalle interno y NO se le muestra al usuario: nadie piensa "tengo un
caso CONFIRMAR", piensa "llegó plata, ¿a qué factura va?".

Por eso hay un solo flujo de trabajo —Asignar— que sirve los depósitos en orden
de monto y adapta lo que muestra a la ayuda disponible en cada uno:

    varias combinaciones válidas  ->  se eligen con radio
    cabe en una factura abierta   ->  se propone el pago parcial
    no encaja nada                ->  se marcan facturas a mano, con suma en vivo

La persona ve siempre lo mismo: el depósito, la mejor ayuda que hay, y dos
botones. Nunca elige una cola.

Todo corre sin servidor: los datos van embebidos como JSON y las decisiones se
guardan en el navegador. Un archivo, doble clic, funciona sin conexión.

    python torre.py     ->  torre.html
"""

import datetime as dt
import html
import json
from pathlib import Path

import datos
import llm
from agentes import bi, cobranza, correos, explicador, facturacion, recaudo

SALIDA = Path(__file__).parent / "torre.html"
CASOS_EXPLICADOS = 12      # a cuántos les redacta el motivo el modelo
MUESTRA_AUDITORIA = 40     # depósitos automáticos que se ofrecen para auditar


def e(x):
    return html.escape(str(x))


def _factura(nro, detalle):
    d = detalle.get(nro, {})
    return {"nro": nro,
            "importe": round(float(d.get("total", 0)), 2),
            "vence": d["vto"].strftime("%d/%m/%Y") if d.get("vto") is not None
                     and not __import__("pandas").isna(d.get("vto")) else "—"}


def main():
    print("Corriendo el ciclo completo...")
    f, p, ncs = datos.facturas(), datos.pagos(), datos.notas_credito()
    clientes, fija, movil = datos.clientes(), datos.planta_fija(), datos.planta_movil()

    decisiones = recaudo.procesar(f, p)
    k_rec = recaudo.kpis(decisiones)
    carga = recaudo.carga_humana(decisiones)

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

    detalle = {r.NRO_DOC_FISCAL: {"total": r.total, "vto": r.fecha_vto}
               for r in f.itertuples()}
    stp = k_rec["stp_pct"]
    pendientes = decisiones[decisiones.cola != "AUTO"].sort_values("monto", ascending=False)
    auto = decisiones[decisiones.cola == "AUTO"]

    # --- En qué se divide el trabajo ------------------------------------------
    # El Resumen dice "671 por asignar" sin explicar qué son. Esto los abre por
    # tipo. Los nombres son en lenguaje llano, NO los códigos internos
    # (AUTO/HIPOTESIS/INVESTIGAR): quien mira esto no tiene por qué conocerlos.
    reparto = []
    for clave, nombre, hace, color in [
        ("AUTO", "Aplicado solo", "Nada — ya quedó resuelto", "var(--green)"),
        ("CONFIRMAR", "Elegir entre opciones",
         "Confirma cuál de varias combinaciones válidas es la correcta", "var(--cyan)"),
        ("HIPOTESIS", "Pago a cuenta",
         "Aprueba el abono parcial y el saldo que queda debiendo", "var(--amber)"),
        ("INVESTIGAR", "Sin calce exacto",
         "Confirma o corrige las facturas que señala el modelo", "var(--rose)"),
    ]:
        g = decisiones[decisiones.cola == clave]
        if not len(g):
            continue
        reparto.append({
            "nombre": nombre, "hace": hace, "color": color,
            "casos": len(g),
            "pct": len(g) / len(decisiones) * 100,
            "monto": float(g.monto.sum()),
            "minutos": len(g) * recaudo.SEGUNDOS_POR_CASO[clave] / 60
                       / recaudo.DIAS_HABILES_VENTANA,
        })

    barra = "".join(
        f'<div class="tramo" style="width:{r["pct"]:.2f}%;background:{r["color"]}" '
        f'title="{e(r["nombre"])}: {r["casos"]:,} casos">'
        f'{f"{r['pct']:.1f}%" if r["pct"] >= 6 else ""}</div>' for r in reparto)

    # Un decimal en los minutos, no cero: con redondeo por fila la columna suma
    # 18 y el titular dice 19, y quien sume la tabla encuentra la diferencia.
    filas_reparto = "".join(f"""<tr>
      <td><span class="punto" style="background:{r['color']}"></span>{e(r['nombre'])}</td>
      <td class="dim">{e(r['hace'])}</td>
      <td class="num">{r['casos']:,}</td>
      <td class="num">{r['pct']:.1f}%</td>
      <td class="num">S/ {r['monto']:,.0f}</td>
      <td class="num">{r['minutos']:.1f}</td></tr>""" for r in reparto)
    filas_reparto += f"""<tr class="total">
      <td colspan="2">Total</td>
      <td class="num">{len(decisiones):,}</td>
      <td class="num">100%</td>
      <td class="num">S/ {decisiones.monto.sum():,.0f}</td>
      <td class="num">{carga['minutos_por_dia_habil']:.1f}</td></tr>"""

    print(f"Redactando {CASOS_EXPLICADOS} motivos con {llm.etiqueta()}...")
    redactados = {}
    for c in pendientes.head(CASOS_EXPLICADOS).to_dict("records"):
        redactados[f"{c['cliente']}|{c['fecha']:%Y-%m-%d}"] = explicador.explicar(c)

    # ------------------------------------------------------------- datos JSON
    casos = []
    for c in pendientes.itertuples():
        cid = f"{c.cliente}|{c.fecha:%Y-%m-%d}"
        # "ayuda" es lo único que el navegador necesita saber del tipo de caso:
        # determina qué control se dibuja, no cómo se navega.
        if c.cola == "CONFIRMAR":
            ayuda = "opciones"
        elif c.cola == "HIPOTESIS":
            ayuda = "parcial"
        else:
            ayuda = "manual"
        casos.append({
            "id": cid,
            "cliente": c.cliente,
            "fecha": f"{c.fecha:%d/%m/%Y}",
            "monto": round(float(c.monto), 2),
            "ayuda": ayuda,
            "motivo": redactados.get(cid, c.explicacion),
            "opciones": [[_factura(n, detalle) for n in combo]
                         for combo in ([list(c.facturas_propuestas)] + list(c.alternativas))
                         if combo],
            "parcial": ({"factura": c.parcial_sugerido["factura"],
                         "importe": c.parcial_sugerido["importe"],
                         "resto": c.parcial_sugerido["saldo_restante"]}
                        if c.parcial_sugerido else None),
            # Ranking del asignador aprendido: qué facturas son más probables.
            # Es lo que hace que un caso de "investigar" ya no llegue en blanco.
            "sugeridas": [{"nro": r["factura"], "importe": r["importe"],
                           "confianza": round(min(r["puntaje"], 0.999) * 100),
                           "acumulado": r["acumulado"]}
                          for r in (c.ranking_modelo or [])
                          if r.get("puntaje") is not None],
            "abiertas": [{"nro": a["factura"], "importe": a["importe"],
                          "vence": a["vence"].strftime("%d/%m/%Y")
                                   if a["vence"] is not None else "—"}
                         for a in c.abiertas],
        })

    muestra = auto.nlargest(MUESTRA_AUDITORIA, "monto")
    auditables = [{
        "id": f"{c.cliente}|{c.fecha:%Y-%m-%d}",
        "cliente": c.cliente, "fecha": f"{c.fecha:%d/%m/%Y}",
        "monto": round(float(c.monto), 2),
        "abiertas": int(c.n_candidatas),
        "facturas": [_factura(n, detalle) for n in c.facturas_propuestas],
    } for c in muestra.itertuples()]

    por_cliente = {}
    for c in decisiones.itertuples():
        d = por_cliente.setdefault(c.cliente, {"aplicados": 0, "monto_aplicado": 0.0,
                                               "pendientes": 0, "monto_pendiente": 0.0,
                                               "depositos": []})
        if c.cola == "AUTO":
            d["aplicados"] += 1
            d["monto_aplicado"] += float(c.monto)
        else:
            d["pendientes"] += 1
            d["monto_pendiente"] += float(c.monto)
        d["depositos"].append({
            "fecha": f"{c.fecha:%d/%m/%Y}", "monto": round(float(c.monto), 2),
            "estado": "Aplicado" if c.cola == "AUTO" else "Sin aplicar",
            "facturas": [n for n in c.facturas_propuestas],
        })
    for r in pcd.itertuples():
        if r.RAZON_SOCIAL in por_cliente:
            por_cliente[r.RAZON_SOCIAL].update(
                riesgo=r.nivel_pcd, deuda=round(float(r.deuda_pendiente), 2))
    for r in impacto.itertuples():
        if r.RAZON_SOCIAL in por_cliente:
            por_cliente[r.RAZON_SOCIAL].update(
                sin_facturar=r.nivel_riesgo, impacto=round(float(r.impacto_soles), 2))
    for c in clasificados:
        if c["cliente"] in por_cliente:
            por_cliente[c["cliente"]].setdefault("correos", []).append(
                {"asunto": c["asunto"], "cuerpo": c["cuerpo"], "categoria": c["categoria"]})

    # Empresas con trabajo pendiente, ordenadas por lo que más urge atender.
    # La prioridad no es solo el monto: una empresa que avisó que pagó y sigue
    # con depósitos sin asignar está recibiendo llamadas de cobranza por error.
    avisaron = {c["cliente"] for c in clasificados
                if c["categoria"] == "CONFIRMACION_PAGO"}
    riesgo_alto = set(pcd[pcd.nivel_pcd == "ALTO"].RAZON_SOCIAL)

    empresas = []
    for cli, g in pendientes.groupby("cliente"):
        info = por_cliente.get(cli, {})
        motivos = []
        prio = float(g.monto.sum())
        if cli in avisaron:
            motivos.append("avisó que pagó")
            prio += 1_000_000
        if cli in riesgo_alto:
            motivos.append("riesgo alto de impago")
            prio += 100_000
        if info.get("sin_facturar") in ("ALTO", "CRITICO"):
            motivos.append("servicio sin facturar")
            prio += 10_000
        empresas.append({
            "cliente": cli,
            "pendientes": int(len(g)),
            "monto": round(float(g.monto.sum()), 2),
            "aplicados": int(info.get("aplicados", 0)),
            "motivos": motivos,
            "prioridad": prio,
            "ids": [f"{cli}|{r.fecha:%Y-%m-%d}" for r in g.itertuples()],
        })
    empresas.sort(key=lambda x: -x["prioridad"])

    DATOS = {"casos": casos, "auditables": auditables, "clientes": por_cliente,
             "empresas": empresas,
             "stp": stp, "aplicados": int(k_rec["aplicados_sin_intervencion"]),
             "total": int(k_rec["depositos_procesados"]),
             "monto_aplicado": round(float(k_rec["monto_aplicado_solo_soles"]), 2),
             "minutos": round(carga["minutos_por_dia_habil"])}

    # -------------------------------------------------------------- tablas fijas
    filas_fuga = "".join(f"""<tr><td>{e(r.RAZON_SOCIAL)}</td>
        <td class="center">{'●' if r.tiene_fija else '—'}</td>
        <td class="center">{'●' if r.tiene_movil else '—'}</td>
        <td class="num">{'Nunca' if r.nunca_facturado else f'{r.dias_sin_facturar:,}'}</td>
        <td><span class="badge" style="background:{'var(--red)' if r.nivel_riesgo == 'CRITICO' else 'var(--violet)'}">{e(r.nivel_riesgo)}</span></td>
        <td class="num">S/ {r.impacto_soles:,.2f}</td></tr>"""
        for r in impacto.head(12).itertuples())

    c_pcd = {"ALTO": "var(--red)", "MEDIO": "var(--amber)", "BAJO": "var(--green)"}
    filas_bi = "".join(f"""<tr><td>{e(r.RAZON_SOCIAL)}</td>
        <td><span class="badge" style="background:{c_pcd[r.nivel_pcd]}">{e(r.nivel_pcd)}</span></td>
        <td class="num">{r.facturas_pendientes}</td>
        <td class="num">S/ {r.deuda_pendiente:,.2f}</td>
        <td class="dim">{e(r.estrategia)}</td></tr>"""
        for r in prioridad.head(8).itertuples())

    filas_aging = "".join(f"""<tr><td>{e(r.bucket)}</td><td class="num">{int(r.n_facturas)}</td>
        <td class="num">S/ {r.monto_pendiente:,.2f}</td></tr>""" for r in aging.itertuples())

    c_cat = {"CONFIRMACION_PAGO": "var(--green)", "RECLAMO_MONTO": "var(--red)",
             "SOLICITUD_DOCUMENTO": "var(--cyan)", "RECLAMO_SERVICIO": "var(--amber)",
             "OTRO": "var(--text-dim)"}
    filas_cob = "".join(f"""<tr><td>{e(c['cliente'])}</td><td>{e(c['asunto'])}</td>
        <td><span class="badge" style="background:{c_cat.get(c['categoria'], 'var(--text-dim)')}">{e(c['categoria'])}</span></td>
        <td class="num">{c['confianza']}</td></tr>""" for c in clasificados)

    alertas = ""
    for c in clasificados:
        if c["categoria"] != "CONFIRMACION_PAGO":
            continue
        suyos = decisiones[decisiones.cliente == c["cliente"]]
        pend = suyos[suyos.cola != "AUTO"]
        if len(pend):
            alertas += (f'<div class="alerta warn"><b>{e(c["cliente"])}</b> avisa que pagó y '
                        f'tiene {len(pend)} depósito(s) sin asignar por '
                        f'S/ {pend.monto.sum():,.2f}</div>')
        else:
            alertas += (f'<div class="alerta ok"><b>{e(c["cliente"])}</b> avisa que pagó y sus '
                        f'depósitos ya están aplicados — sacar de la ruta de cobranza</div>')
    criticos = impacto[impacto.nivel_riesgo == "CRITICO"]
    if len(criticos):
        alertas += (f'<div class="alerta warn"><b>{len(criticos)} cliente(s)</b> con servicio '
                    f'activo nunca facturados — S/ {criticos.impacto_soles.sum():,.0f} sin cobrar</div>')
    if not alertas:
        alertas = '<div class="alerta ok">Nada urgente.</div>'

    ahora = dt.datetime.now()
    log = [
        ("Supervisor", f"Delegando {len(decisiones):,} depósitos al Agente de Recaudo"),
        ("Recaudo", f"{stp}% aplicados sin intervención · S/ {k_rec['monto_aplicado_solo_soles']:,.2f}"),
        ("Supervisor", f"{len(pendientes):,} depósitos encolados · {carga['minutos_por_dia_habil']:.0f} min/día hábil"),
        ("Facturación", f"{k_fac['clientes_con_fuga']} clientes con servicio activo sin facturar · S/ {k_fac['impacto_estimado_soles']:,.2f}"),
        ("Facturación", f"Notas de crédito {k_fac['tasa_error_facturacion_pct']}% de las facturas"),
        ("BI", f"{k_bi['clientes_riesgo_alto']} clientes en riesgo alto deben S/ {k_bi['deuda_de_los_riesgo_alto_soles']:,.2f}"),
        ("BI", f"Mayor concentración en '{k_bi['bucket_mayor_concentracion']}': S/ {k_bi['monto_bucket_mayor_soles']:,.2f}"),
        ("Cobranza", f"{len(clasificados)} correos clasificados con {llm.etiqueta()}"),
    ]
    log_html = "".join(f'<div class="log-line"><span class="ts">{ahora:%H:%M:%S}</span> '
                       f'<span class="ag">[{e(a)}]</span> {e(t)}</div>' for a, t in log)

    n_con_pend = len(empresas)
    n_clientes = len(por_cliente)
    n_avisaron = len(avisaron & set(pendientes.cliente))

    doc = PLANTILLA.format(
        n_con_pend=n_con_pend, n_clientes=n_clientes, n_avisaron=n_avisaron,
        stp=stp, dona=440 * stp / 100, ahora=ahora,
        n_fact=len(f), n_dep=len(decisiones), motor=e(llm.etiqueta()),
        aplicados=k_rec["aplicados_sin_intervencion"],
        monto_aplicado=k_rec["monto_aplicado_solo_soles"],
        n_pend=len(pendientes), monto_pend=pendientes.monto.sum(),
        minutos=carga["minutos_por_dia_habil"], fte=carga["fte"],
        barra=barra, filas_reparto=filas_reparto,
        fuga=k_fac["clientes_con_fuga"], impacto_fuga=k_fac["impacto_estimado_soles"],
        nc=k_fac["tasa_error_facturacion_pct"], nunca=k_fac["nunca_facturados"],
        riesgo=k_bi["clientes_riesgo_alto"],
        deuda_riesgo=k_bi["deuda_de_los_riesgo_alto_soles"],
        deuda_total=k_bi["deuda_pendiente_total_soles"],
        bucket=e(k_bi["bucket_mayor_concentracion"]),
        monto_bucket=k_bi["monto_bucket_mayor_soles"],
        correos=k_cob["correos_procesados"], pagos_correo=k_cob["confirmaciones_de_pago"],
        motor_cob=e(k_cob["motor"]),
        alertas=alertas, filas_fuga=filas_fuga, filas_bi=filas_bi,
        filas_aging=filas_aging, filas_cob=filas_cob, log_html=log_html,
        n_auditables=len(auditables),
        datos_json=json.dumps(DATOS, ensure_ascii=False),
    )

    SALIDA.write_text(doc, encoding="utf-8")
    print(f"\nTorre generada en {SALIDA}  ({SALIDA.stat().st_size / 1024:.0f} KB)")
    print(f"  {stp}% aplicados solos · {len(pendientes):,} por asignar · "
          f"{carga['minutos_por_dia_habil']:.0f} min/día")


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0a0e1a">
<title>Agentes 1551 · SON-IA — Torre de control</title>
<style>
  :root {{
    color-scheme: dark;
    --bg:#0a0e1a; --panel:#12172d; --panel2:#171f3d; --line:#232a4a;
    --text:#e7ecf7; --text-dim:#8b93b8;
    --cyan:#22d3ee; --violet:#a78bfa; --amber:#fbbf24; --rose:#fb7185;
    --green:#34d399; --red:#f87171;
    --disp:"Segoe UI Semibold","Segoe UI",system-ui,sans-serif;
    --sans:"Segoe UI",system-ui,-apple-system,sans-serif;
    --mono:ui-monospace,"Cascadia Code",Consolas,"SF Mono",monospace;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:var(--sans);
    padding:24px; }}
  h1,h2,h3 {{ font-family:var(--disp); text-wrap:balance; }}
  .mono {{ font-family:var(--mono); }}
  .num {{ font-variant-numeric:tabular-nums; }}
  button {{ font:inherit; color:inherit; touch-action:manipulation;
    -webkit-tap-highlight-color:transparent; cursor:pointer; }}
  @media (prefers-reduced-motion:reduce) {{ * {{ animation:none!important;
    transition:none!important }} }}

  .topbar {{ display:flex; justify-content:space-between; align-items:center; gap:16px;
    padding:16px 20px; background:linear-gradient(90deg,#0d1330,#141b3f);
    border:1px solid var(--line); border-radius:14px; margin-bottom:16px; }}
  .brand {{ display:flex; align-items:center; gap:12px; }}
  .brand-mark {{ width:40px; height:40px; border-radius:10px; flex-shrink:0;
    background:conic-gradient(from 180deg,var(--cyan),var(--violet),var(--amber),var(--rose),var(--cyan));
    display:flex; align-items:center; justify-content:center; font-weight:700;
    font-size:13px; color:#0a0e1a; }}
  .brand h1 {{ font-size:18px; margin:0; }}
  .brand p {{ margin:2px 0 0; font-size:12px; color:var(--text-dim); }}
  .date {{ font-size:12px; color:var(--text-dim); text-align:right; white-space:nowrap; }}
  .date .mono {{ color:var(--text); }}

  /* ---- navegación: una tarea por pestaña ---- */
  .tabs {{ display:flex; gap:6px; margin-bottom:18px; flex-wrap:wrap; }}
  .tab {{ padding:11px 18px; border-radius:10px; background:var(--panel);
    border:1px solid var(--line); color:var(--text-dim); font-size:13.5px;
    font-weight:500; display:flex; align-items:center; gap:8px;
    transition:background-color .15s, color .15s, border-color .15s; }}
  .tab:hover {{ color:var(--text); border-color:#3a4270; }}
  .tab.active {{ background:var(--panel2); color:var(--text); border-color:var(--cyan); }}
  .tab:focus-visible {{ outline:2px solid var(--cyan); outline-offset:2px; }}
  .tab .cuenta {{ background:var(--cyan); color:#0a0e1a; border-radius:20px;
    padding:1px 8px; font-size:11px; font-weight:700; font-variant-numeric:tabular-nums; }}
  .tab.active .cuenta {{ background:var(--cyan); }}
  .panel {{ display:none; }} .panel.active {{ display:block; animation:fade .2s; }}
  @keyframes fade {{ from{{opacity:0}} to{{opacity:1}} }}

  .cards {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:18px; }}
  .card {{ flex:1 1 190px; background:var(--panel); border:1px solid var(--line);
    border-radius:12px; padding:16px; }}
  .card .metric {{ font-family:var(--disp); font-size:24px; font-weight:700;
    font-variant-numeric:tabular-nums; }}
  .card .label {{ font-size:11.5px; color:var(--text-dim); margin-top:4px; }}
  .card .bar {{ height:5px; border-radius:3px; background:var(--line); margin-top:10px;
    overflow:hidden; }}
  .card .bar i {{ display:block; height:100%; border-radius:3px; }}

  .overview {{ display:flex; gap:24px; background:var(--panel); border:1px solid var(--line);
    border-radius:14px; padding:20px; margin-bottom:18px; align-items:center;
    flex-wrap:wrap; }}
  .donut {{ flex-shrink:0; width:170px; height:170px; position:relative; }}
  .donut svg {{ position:absolute; inset:0; transform:rotate(-90deg); }}
  .donut .lab {{ position:absolute; inset:0; display:flex; flex-direction:column;
    align-items:center; justify-content:center; }}
  .donut .val {{ font-family:var(--disp); font-size:26px; font-weight:700; }}
  .donut .sub {{ font-size:10px; color:var(--text-dim); letter-spacing:.5px; }}
  .ov {{ flex:1 1 340px; }}
  .ov h2 {{ margin:0 0 6px; font-size:16px; }}
  .ov p {{ margin:0 0 8px; font-size:13.5px; color:var(--text-dim); line-height:1.55; }}
  .ov .hl {{ color:var(--cyan); font-family:var(--mono); }}

  .alerta {{ border-left:3px solid var(--line); background:var(--panel); padding:11px 15px;
    border-radius:0 10px 10px 0; margin-bottom:8px; font-size:13px; }}
  .alerta.warn {{ border-color:var(--amber); }} .alerta.ok {{ border-color:var(--green); }}

  /* ---- flujo de asignación ---- */
  .trabajo {{ display:grid; grid-template-columns:1fr 320px; gap:16px; align-items:start; }}
  @media (max-width:900px) {{ .trabajo {{ grid-template-columns:1fr; }} }}
  .caja {{ background:var(--panel); border:1px solid var(--line); border-radius:14px;
    padding:20px; }}
  .caja h3 {{ margin:0 0 14px; font-size:15px; }}
  .deposito {{ display:flex; gap:26px; flex-wrap:wrap; padding-bottom:16px;
    border-bottom:1px solid var(--line); margin-bottom:16px; }}
  .deposito div span {{ display:block; font-size:11px; color:var(--text-dim);
    text-transform:uppercase; letter-spacing:.5px; margin-bottom:3px; }}
  .deposito div b {{ font-family:var(--disp); font-size:20px;
    font-variant-numeric:tabular-nums; }}
  .opcion {{ display:block; border:1px solid var(--line); border-radius:10px; padding:13px 15px;
    margin-bottom:9px; cursor:pointer; transition:border-color .15s, background-color .15s; }}
  .opcion:hover {{ border-color:#3a4270; }}
  .opcion.sel {{ border-color:var(--cyan); background:var(--panel2); }}
  .opcion input {{ margin-right:9px; accent-color:var(--cyan); }}
  .opcion .lista {{ font-family:var(--mono); font-size:12px; color:var(--text-dim);
    margin:7px 0 0 24px; line-height:1.7; }}
  .opcion .suma {{ font-family:var(--mono); font-size:12.5px; color:var(--green);
    margin-left:24px; }}
  .chk {{ display:flex; align-items:center; gap:10px; padding:9px 12px;
    border-bottom:1px solid var(--line); font-size:13px; cursor:pointer; }}
  .chk:hover {{ background:var(--panel2); }}
  .chk input {{ accent-color:var(--cyan); }}
  .chk .imp {{ margin-left:auto; font-family:var(--mono);
    font-variant-numeric:tabular-nums; }}
  .lista-scroll {{ max-height:290px; overflow:auto; border:1px solid var(--line);
    border-radius:10px; }}
  .marcador {{ margin-top:13px; font-family:var(--mono); font-size:13px; }}
  /* Bloque del asignador aprendido: se distingue del listado plano porque es
     una propuesta con confianza, no un catálogo para revisar entero. */
  .sugerencia {{ border:1px solid var(--cyan); border-radius:10px; margin-top:14px;
    background:color-mix(in srgb, var(--cyan) 7%, transparent); overflow:hidden; }}
  .sug-tit {{ padding:10px 13px; font-size:12px; font-weight:600; letter-spacing:.03em;
    text-transform:uppercase; color:var(--cyan); border-bottom:1px solid var(--line); }}
  .sug-fila {{ border-bottom:1px solid var(--line); }}
  .sug-fila:last-of-type {{ border-bottom:none; }}
  .sug-conf {{ font-family:var(--mono); font-size:12px; padding:2px 7px; border-radius:20px;
    background:var(--panel2); color:var(--text-dim); }}
  .sug-conf.alta {{ background:var(--cyan); color:#04121f; font-weight:600; }}
  .sug-nota {{ padding:9px 13px; font-size:11.5px; color:var(--text-dim);
    border-top:1px solid var(--line); line-height:1.5; }}
  .pista {{ background:var(--panel2); border-radius:10px; padding:12px 15px; font-size:13px;
    color:var(--text-dim); line-height:1.55; margin-top:14px; }}
  .btn {{ display:block; width:100%; padding:13px; border-radius:10px; font-weight:600;
    font-size:14px; margin-bottom:9px; border:1px solid var(--line);
    background:var(--panel2); }}
  .btn:hover:not(:disabled) {{ border-color:#3a4270; }}
  .btn:focus-visible {{ outline:2px solid var(--cyan); outline-offset:2px; }}
  .btn.primario {{ background:var(--cyan); color:#0a0e1a; border-color:var(--cyan); }}
  .btn.primario:hover:not(:disabled) {{ filter:brightness(1.1); }}
  .btn:disabled {{ opacity:.4; cursor:not-allowed; }}
  select, input[type=search] {{ width:100%; padding:11px 13px; border-radius:10px;
    background:var(--panel2); border:1px solid var(--line); color:var(--text);
    font:inherit; }}
  select:focus-visible, input:focus-visible {{ outline:2px solid var(--cyan);
    outline-offset:1px; }}
  .avance {{ height:5px; background:var(--line); border-radius:3px; overflow:hidden;
    margin-bottom:14px; }}
  .avance i {{ display:block; height:100%; background:var(--cyan); border-radius:3px;
    transition:width .3s; }}
  .vacio {{ text-align:center; padding:60px 20px; color:var(--text-dim); }}
  .vacio .grande {{ font-size:44px; margin-bottom:12px; }}

  .tablewrap {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; background:var(--panel);
    border-radius:12px; overflow:hidden; border:1px solid var(--line); min-width:520px; }}
  th {{ text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.4px;
    color:var(--text-dim); padding:10px 12px; background:var(--panel2); font-weight:600; }}
  td {{ padding:10px 12px; border-top:1px solid var(--line); font-size:13px; }}
  td.num {{ font-family:var(--mono); text-align:right; white-space:nowrap;
    font-variant-numeric:tabular-nums; }}
  td.center {{ text-align:center; }}
  td.dim {{ color:var(--text-dim); font-size:12px; max-width:340px; }}
  /* Reparto del trabajo: la barra da la proporción de un vistazo y la tabla
     el detalle. El ancho de cada tramo ES el volumen, no un adorno. */
  p.intro {{ color:var(--text-dim); font-size:13px; line-height:1.6;
    margin:0 0 12px; max-width:70ch; }}
  .barra-colas {{ display:flex; height:34px; border-radius:9px; overflow:hidden;
    margin-bottom:12px; border:1px solid var(--line); }}
  .barra-colas .tramo {{ display:flex; align-items:center; justify-content:center;
    font-size:11.5px; font-weight:600; color:#0a0e1a; overflow:hidden;
    font-variant-numeric:tabular-nums; }}
  .punto {{ display:inline-block; width:9px; height:9px; border-radius:50%;
    margin-right:8px; vertical-align:baseline; }}
  tr.total td {{ border-top:2px solid var(--line); font-weight:600;
    color:var(--text); }}
  .badge {{ padding:3px 9px; border-radius:20px; font-size:10.5px; font-weight:600;
    color:#0a0e1a; white-space:nowrap; }}
  h3.sec {{ font-size:13px; margin:22px 0 10px; color:var(--text-dim);
    text-transform:uppercase; letter-spacing:.5px; }}
  .subtabs {{ display:flex; gap:6px; margin-bottom:14px; flex-wrap:wrap; }}
  .subtab {{ padding:8px 14px; border-radius:8px; background:transparent;
    border:1px solid var(--line); color:var(--text-dim); font-size:12.5px; }}
  .subtab.active {{ background:var(--panel); color:var(--text); border-color:#3a4270; }}
  .subpanel {{ display:none; }} .subpanel.active {{ display:block; }}

  .log {{ background:var(--panel); border:1px solid var(--line); border-radius:12px;
    padding:14px; max-height:340px; overflow:auto; }}
  .log-line {{ font-family:var(--mono); font-size:11.5px; padding:6px 4px 6px 10px;
    border-left:2px solid var(--cyan); margin-bottom:6px; color:#c3c9e0; }}
  .log-line .ts {{ color:var(--text-dim); }}
  .log-line .ag {{ color:var(--cyan); font-weight:500; }}
  footer {{ margin-top:24px; padding:18px 4px; border-top:1px solid var(--line);
    font-size:12px; color:var(--text-dim); display:flex; justify-content:space-between;
    gap:16px; flex-wrap:wrap; }}
</style></head><body>

<div class="topbar">
  <div class="brand">
    <div class="brand-mark">1551</div>
    <div><h1>Agentes 1551 · SON-IA</h1>
    <p>Integratel B2B · {n_fact:,} facturas · {n_dep:,} depósitos · motor {motor}</p></div>
  </div>
  <div class="date">Última ejecución<br><span class="mono">{ahora:%d/%m/%Y %H:%M}</span></div>
</div>

<div class="tabs" role="tablist" aria-label="Secciones">
  <button type="button" role="tab" aria-selected="true" aria-controls="p-resumen"
    class="tab active" onclick="ir('resumen')">Resumen</button>
  <button type="button" role="tab" aria-selected="false" aria-controls="p-asignar"
    class="tab" onclick="ir('asignar')">Asignar depósitos
    <span class="cuenta" id="cuenta-asignar">0</span></button>
  <button type="button" role="tab" aria-selected="false" aria-controls="p-cartera"
    class="tab" onclick="ir('cartera')">Cartera</button>
  <button type="button" role="tab" aria-selected="false" aria-controls="p-auditar"
    class="tab" onclick="ir('auditar')">Auditar</button>
  <button type="button" role="tab" aria-selected="false" aria-controls="p-registro"
    class="tab" onclick="ir('registro')">Registro
    <span class="cuenta" id="cuenta-registro">0</span></button>
</div>

<!-- ============================================ RESUMEN -->
<div class="panel active" id="p-resumen">
  <div class="overview">
    <div class="donut">
      <svg width="170" height="170" viewBox="0 0 170 170" role="img"
        aria-label="{stp} por ciento aplicado sin intervención">
        <circle cx="85" cy="85" r="70" fill="none" stroke="var(--line)" stroke-width="16"/>
        <circle cx="85" cy="85" r="70" fill="none" stroke="var(--cyan)" stroke-width="16"
          stroke-dasharray="{dona:.1f} 440" stroke-linecap="round"/>
      </svg>
      <div class="lab"><div class="val">{stp}%</div><div class="sub">SIN TOCAR</div></div>
    </div>
    <div class="ov">
      <h2>Cómo va la conciliación</h2>
      <p>De <span class="hl">{n_dep:,}</span> depósitos recibidos del banco,
      <span class="hl">{aplicados:,}</span> se asignaron solos a su factura —
      S/ {monto_aplicado:,.0f} sin que nadie los revisara.</p>
      <p>Quedan <span class="hl">{n_pend:,}</span> por asignar
      (S/ {monto_pend:,.0f}), unos <span class="hl">{minutos:.0f} minutos</span>
      de trabajo. Se resuelven en <b>Asignar depósitos</b>.</p>
    </div>
  </div>
  <h3 class="sec">En qué se divide el trabajo</h3>
  <p class="intro">Cada depósito cae en uno de estos cuatro grupos según cuánta
  intervención necesita. El ancho de la barra es el volumen real.</p>
  <div class="barra-colas">{barra}</div>
  <div class="tablewrap"><table>
    <tr><th>Grupo</th><th>Qué hace la persona</th><th class="num">Casos</th>
      <th class="num">%</th><th class="num">Monto</th>
      <th class="num">Min por día</th></tr>
    {filas_reparto}
  </table></div>

  <h3 class="sec">Requiere atención</h3>
  {alertas}

  <h3 class="sec">Estado de los clientes</h3>
  <div class="cards">
    <div class="card"><div class="metric">{n_clientes:,}</div>
      <div class="label">Empresas en cartera</div></div>
    <div class="card"><div class="metric" style="color:var(--cyan)">{n_con_pend}</div>
      <div class="label">Con depósitos por asignar</div></div>
    <div class="card"><div class="metric" style="color:var(--rose)">{n_avisaron}</div>
      <div class="label">Avisaron que pagaron y siguen pendientes</div></div>
    <div class="card"><div class="metric" style="color:var(--amber)">{riesgo}</div>
      <div class="label">En riesgo alto de impago · S/ {deuda_riesgo:,.0f}</div></div>
    <div class="card"><div class="metric" style="color:var(--violet)">{fuga}</div>
      <div class="label">Con servicio activo sin facturar</div></div>
  </div>

  <h3 class="sec">Operación del período</h3>
  <div class="cards">
    <div class="card"><div class="metric" style="color:var(--cyan)">{stp}%</div>
      <div class="label">Depósitos asignados sin intervención</div>
      <div class="bar"><i style="width:{stp}%;background:var(--cyan)"></i></div></div>
    <div class="card"><div class="metric">{minutos:.0f} min</div>
      <div class="label">Trabajo humano por día hábil · {fte} FTE</div></div>
    <div class="card"><div class="metric">{nc}%</div>
      <div class="label">Facturas que requirieron nota de crédito</div></div>
    <div class="card"><div class="metric" style="font-size:17px">{bucket}</div>
      <div class="label">Tramo con más deuda · S/ {monto_bucket:,.0f}</div></div>
  </div>
</div>

<!-- ============================================ ASIGNAR -->
<div class="panel" id="p-asignar">
  <div class="caja" style="margin-bottom:14px">
    <h3>Buscar una empresa</h3>
    <input type="search" id="buscar" placeholder="Escriba el nombre de la empresa…"
      list="lista-empresas" oninput="abrirEmpresa(this.value)" aria-label="Buscar empresa">
    <datalist id="lista-empresas"></datalist>
  </div>
  <div class="avance"><i id="avance" style="width:0%"></i></div>
  <div id="zona-trabajo"></div>
</div>

<!-- ============================================ CARTERA -->
<div class="panel" id="p-cartera">
  <div class="subtabs">
    <button type="button" class="subtab active" onclick="sub('facturar')">Sin facturar</button>
    <button type="button" class="subtab" onclick="sub('cobrar')">Riesgo de impago</button>
    <button type="button" class="subtab" onclick="sub('correos')">Correos</button>
  </div>

  <div class="subpanel active" id="s-facturar">
    <div class="cards">
      <div class="card"><div class="metric" style="color:var(--violet)">{fuga}</div>
        <div class="label">Con servicio activo sin facturar</div></div>
      <div class="card"><div class="metric">{nunca}</div><div class="label">Nunca facturados</div></div>
      <div class="card"><div class="metric">S/ {impacto_fuga:,.0f}</div>
        <div class="label">Impacto estimado</div></div>
      <div class="card"><div class="metric">{nc}%</div>
        <div class="label">Facturas con nota de crédito</div></div>
    </div>
    <div class="tablewrap"><table>
      <tr><th>Cliente</th><th>Fijo</th><th>Móvil</th><th>Días sin facturar</th>
        <th>Riesgo</th><th>Impacto estimado</th></tr>{filas_fuga}</table></div>
  </div>

  <div class="subpanel" id="s-cobrar">
    <div class="cards">
      <div class="card"><div class="metric" style="color:var(--amber)">{riesgo}</div>
        <div class="label">Clientes en riesgo alto</div></div>
      <div class="card"><div class="metric">S/ {deuda_riesgo:,.0f}</div>
        <div class="label">Lo que deben esos clientes</div></div>
      <div class="card"><div class="metric">S/ {deuda_total:,.0f}</div>
        <div class="label">Deuda pendiente total</div></div>
      <div class="card"><div class="metric" style="font-size:17px">{bucket}</div>
        <div class="label">Mayor concentración · S/ {monto_bucket:,.0f}</div></div>
    </div>
    <h3 class="sec">A quién cobrar primero</h3>
    <div class="tablewrap"><table>
      <tr><th>Cliente</th><th>Riesgo</th><th>Facturas</th><th>Deuda</th>
        <th>Estrategia sugerida</th></tr>{filas_bi}</table></div>
    <h3 class="sec">Antigüedad de la deuda</h3>
    <div class="tablewrap"><table>
      <tr><th>Tramo</th><th>Facturas</th><th>Monto pendiente</th></tr>{filas_aging}</table></div>
  </div>

  <div class="subpanel" id="s-correos">
    <div class="cards">
      <div class="card"><div class="metric" style="color:var(--rose)">{correos}</div>
        <div class="label">Correos procesados</div></div>
      <div class="card"><div class="metric">{pagos_correo}</div>
        <div class="label">Confirman pago</div></div>
      <div class="card"><div class="metric" style="font-size:15px">{motor_cob}</div>
        <div class="label">Clasificados con</div></div>
    </div>
    <div class="tablewrap"><table>
      <tr><th>Cliente</th><th>Asunto</th><th>Categoría</th><th>Confianza</th></tr>
      {filas_cob}</table></div>
  </div>
</div>

<!-- ============================================ AUDITAR -->
<div class="panel" id="p-auditar">
  <div class="caja" style="margin-bottom:14px">
    <h3>Para qué sirve esta sección</h3>
    <p style="color:var(--text-dim);font-size:13.5px;margin:0 0 10px;line-height:1.6">
      Los depósitos se parten en dos: los que el sistema <b>no supo</b> resolver, que
      van a <i>Asignar</i>, y los que resolvió con una única respuesta exacta, que se
      aplican <b>sin que nadie los mire</b>. Aquí se revisa una muestra de los
      segundos.</p>
    <p style="color:var(--text-dim);font-size:13.5px;margin:0 0 10px;line-height:1.6">
      No son casos sospechosos — al contrario: son los que el sistema dio por seguros.
      Se revisan justamente porque nadie más los va a mirar. Si el motor cambiara de
      comportamiento por un cambio en los datos, esta muestra es donde se nota.</p>
    <p style="color:var(--text-dim);font-size:13.5px;margin:0;line-height:1.6">
      <b>Cadencia sugerida:</b> una vez por semana, unos quince minutos. Al revisar
      cada caso la pregunta no es si la suma cuadra —eso ya está verificado— sino si
      <b>tiene sentido de negocio</b> que esa empresa pagara justo esas facturas.</p>
  </div>
  <div id="zona-auditoria"></div>
</div>

<!-- ============================================ REGISTRO -->
<div class="panel" id="p-registro">
  <div id="zona-registro"></div>
  <h3 class="sec">Actividad de los agentes</h3>
  <div class="log">{log_html}</div>
</div>

<footer>
  <div>Integratel B2B · ciclo de ingreso — facturación, recaudo, cobranza e
  inteligencia de negocio, coordinados por el orquestador</div>
  <div>Ejecución {ahora:%d/%m/%Y %H:%M}</div>
</footer>

<script>
const D = {datos_json};
const CLAVE = 'sonia-decisiones';
let hechas = JSON.parse(localStorage.getItem(CLAVE) || '{{}}');
let seleccion = {{}};   // por caso: índice de opción o lista de facturas
const soles = n => 'S/ ' + n.toLocaleString('es-PE',
  {{minimumFractionDigits:2, maximumFractionDigits:2}});

/* ---------------- navegación ---------------- */
function ir(id, empujar = true) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const p = document.getElementById('p-' + id);
  if (!p) return;
  p.classList.add('active');
  document.querySelectorAll('.tab').forEach(t => {{
    const on = t.getAttribute('aria-controls') === 'p-' + id;
    t.classList.toggle('active', on);
    t.setAttribute('aria-selected', on);
  }});
  if (empujar) history.replaceState(null, '', '#' + id);
  if (id === 'asignar') pintarTrabajo();
  if (id === 'auditar') pintarAuditoria();
  if (id === 'registro') pintarRegistro();
}}
function sub(id) {{
  document.querySelectorAll('.subpanel').forEach(p => p.classList.remove('active'));
  document.getElementById('s-' + id).classList.add('active');
  document.querySelectorAll('.subtab').forEach(t =>
    t.classList.toggle('active', t.getAttribute('onclick').includes("'" + id + "'")));
}}

/* ---------------- asignar depósitos ----------------
   Arranca por la lista de empresas ordenada por urgencia. Al elegir una se ve
   su situación completa y se trabajan sus depósitos uno a uno. El tipo de caso
   decide qué control se dibuja; nunca obliga a elegir un montón antes de
   empezar.                                                                */
let empresaActiva = null;

function porHacer() {{ return D.casos.filter(c => !hechas[c.id]); }}
function pendientesDe(nom) {{
  const e = D.empresas.find(x => x.cliente === nom);
  return e ? e.ids.filter(id => !hechas[id]) : [];
}}

function pintarTrabajo() {{
  const cola = porHacer();
  const total = D.casos.length;
  document.getElementById('cuenta-asignar').textContent = cola.length;
  document.getElementById('avance').style.width =
    ((total - cola.length) / total * 100) + '%';
  const z = document.getElementById('zona-trabajo');

  if (!cola.length) {{
    z.innerHTML = `<div class="caja vacio"><div class="grande">✓</div>
      <h3>No queda nada por asignar</h3>
      <p>Los ${{total}} depósitos que necesitaban criterio ya fueron resueltos.</p></div>`;
    return;
  }}
  if (!empresaActiva) {{ pintarListaEmpresas(); return; }}

  const ids = pendientesDe(empresaActiva);
  if (!ids.length) {{ empresaActiva = null; pintarListaEmpresas(); return; }}
  const c = D.casos.find(x => x.id === ids[0]);
  let ayuda = '', acciones = '';

  if (c.ayuda === 'opciones') {{
    const sel = seleccion[c.id] ?? 0;
    ayuda = `<h3>Hay ${{c.opciones.length}} combinaciones de facturas que suman
      exactamente este monto. ¿Cuál pagó?</h3>` +
      c.opciones.map((op, i) => {{
        const suma = op.reduce((s, f) => s + f.importe, 0);
        return `<label class="opcion ${{i === sel ? 'sel' : ''}}">
          <input type="radio" name="op" value="${{i}}" ${{i === sel ? 'checked' : ''}}
            onchange="elegir('${{c.id}}', ${{i}})">
          <b>Opción ${{i + 1}}</b> — ${{op.length}} factura(s)
          <div class="lista">${{op.map(f =>
            `${{f.nro}} · ${{soles(f.importe)}} · vence ${{f.vence}}`).join('<br>')}}</div>
          <div class="suma">Suma ${{soles(suma)}}</div></label>`;
      }}).join('');
    acciones = `<button class="btn primario" onclick="resolver('${{c.id}}','asignado')">
      Asignar la opción elegida</button>`;

  }} else if (c.ayuda === 'parcial') {{
    ayuda = `<h3>El depósito no alcanza a cubrir ninguna factura completa</h3>
      <p style="color:var(--text-dim);font-size:13.5px;line-height:1.6">
      Lo más probable es que sea un pago a cuenta de la factura que está por vencer:</p>
      <div class="deposito" style="border:none;padding:0;margin:14px 0 0">
        <div><span>Factura</span><b class="mono" style="font-size:15px">
          ${{c.parcial.factura}}</b></div>
        <div><span>Debe</span><b>${{soles(c.parcial.importe)}}</b></div>
        <div><span>Paga ahora</span><b style="color:var(--cyan)">${{soles(c.monto)}}</b></div>
        <div><span>Quedaría debiendo</span><b style="color:var(--amber)">
          ${{soles(c.parcial.resto)}}</b></div>
      </div>`;
    acciones = `<button class="btn primario" onclick="resolver('${{c.id}}','parcial')">
      Registrar como pago a cuenta</button>`;

  }} else {{
    const marcadas = seleccion[c.id] || [];
    const suma = c.abiertas.filter(f => marcadas.includes(f.nro))
      .reduce((s, f) => s + f.importe, 0);
    const dif = suma - c.monto;

    // El modelo entrenado puntúa cada factura abierta. Cuando hay ranking, el
    // caso deja de arrancar en blanco: se señalan las más probables y el
    // operador confirma. El listado completo sigue abajo para poder corregir.
    const cubre = c.sugeridas && c.sugeridas.length
      && c.sugeridas[c.sugeridas.length - 1].acumulado >= c.monto - 0.005;
    const sug = c.sugeridas && c.sugeridas.length
      ? `<div class="sugerencia">
          <div class="sug-tit">El modelo señala estas como las más probables</div>
          ${{c.sugeridas.map((s, i) => `
            <label class="chk sug-fila">
              <input type="checkbox" ${{marcadas.includes(s.nro) ? 'checked' : ''}}
                onchange="marcar('${{c.id}}','${{s.nro}}')">
              <span class="mono">${{s.nro}}</span>
              <span class="sug-conf ${{i === 0 ? 'alta' : ''}}">${{s.confianza}}%</span>
              <span class="imp">${{soles(s.importe)}}</span></label>`).join('')}}
          <div class="sug-nota">
            Las ${{c.sugeridas.length}} juntas suman
            <b>${{soles(c.sugeridas[c.sugeridas.length - 1].acumulado)}}</b>
            contra un depósito de <b>${{soles(c.monto)}}</b> —
            ${{cubre
              ? '<span style="color:var(--green)">alcanzan a cubrirlo</span>.'
              : '<span style="color:var(--amber)">no alcanzan</span>: el pago cubre ' +
                'parcialmente varias, o hay una factura fuera del sistema.'}}
            <br>La confianza es del modelo, no certeza: marque las que correspondan
            y ajuste con el listado completo.</div>
        </div>`
      : '';

    ayuda = `<h3>${{c.sugeridas && c.sugeridas.length
        ? 'Ninguna combinación cuadra exacto — confirme la propuesta'
        : 'Ninguna combinación cuadra — hay que armarla a mano'}}</h3>
      ${{sug}}
      <p style="color:var(--text-dim);font-size:13.5px;line-height:1.6;margin-top:14px">
      ${{c.sugeridas && c.sugeridas.length
        ? 'Todas las facturas abiertas del cliente, por si la correcta no está arriba:'
        : 'Marque las facturas que crea que cubre este depósito. La suma se actualiza abajo.'}}</p>
      <div class="lista-scroll">${{c.abiertas.map(f => `
        <label class="chk"><input type="checkbox" ${{marcadas.includes(f.nro) ? 'checked' : ''}}
          onchange="marcar('${{c.id}}','${{f.nro}}')">
          <span class="mono">${{f.nro}}</span>
          <span style="color:var(--text-dim);font-size:12px">vence ${{f.vence}}</span>
          <span class="imp">${{soles(f.importe)}}</span></label>`).join('')}}</div>
      <div class="marcador">Seleccionado <b>${{soles(suma)}}</b> · Depósito
        <b>${{soles(c.monto)}}</b> · ${{Math.abs(dif) < 0.005
          ? '<span style="color:var(--green)">cuadra</span>'
          : `<span style="color:var(--amber)">faltan ${{soles(Math.abs(dif))}}</span>`}}</div>`;
    acciones = `<button class="btn primario" ${{marcadas.length ? '' : 'disabled'}}
      onclick="resolver('${{c.id}}','manual')">
      Asignar a ${{marcadas.length}} factura(s)</button>`;
  }}

  const info = D.clientes[c.cliente] || {{}};
  z.innerHTML = `
    <div class="caja" style="margin-bottom:14px">
      <button class="btn" style="width:auto;margin:0 0 12px" onclick="volverLista()">
        ← Volver a la lista de empresas</button>
      <h3 style="margin-bottom:10px">${{c.cliente}}</h3>
      <div class="deposito" style="border:none;padding:0;margin:0">
        <div><span>Depósitos ya aplicados</span><b>${{info.aplicados || 0}}</b></div>
        <div><span>Por asignar</span><b style="color:var(--amber)">${{ids.length}}</b></div>
        ${{info.riesgo ? `<div><span>Riesgo de impago</span><b>${{info.riesgo}}</b></div>` : ''}}
        ${{info.deuda ? `<div><span>Deuda</span><b>${{soles(info.deuda)}}</b></div>` : ''}}
        ${{info.sin_facturar ? `<div><span>Servicio sin facturar</span>
          <b>${{info.sin_facturar}}</b></div>` : ''}}
      </div>
      ${{info.correos ? info.correos.map(m => `<div class="alerta warn"
        style="margin:12px 0 0"><b>Escribió:</b> "${{m.asunto}}" —
        clasificado como ${{m.categoria}}</div>`).join('') : ''}}
    </div>
    <div class="trabajo">
    <div class="caja">
      <div class="deposito">
        <div><span>Monto recibido</span><b style="color:var(--cyan)">
          ${{soles(c.monto)}}</b></div>
        <div><span>Fecha</span><b>${{c.fecha}}</b></div>
        <div><span>Facturas abiertas</span><b>${{c.abiertas.length}}</b></div>
      </div>
      ${{ayuda}}
      <div class="pista">${{c.motivo}}</div>
    </div>
    <div>
      <div class="caja">
        <h3>Decisión</h3>
        ${{acciones}}
        <button class="btn" onclick="resolver('${{c.id}}','rechazado')">
          No corresponde — devolver</button>
        <button class="btn" onclick="resolver('${{c.id}}','pospuesto')">
          Dejar para después</button>
      </div>
      <p style="color:var(--text-dim);font-size:12px;margin:12px 4px 0;line-height:1.5">
        Depósito 1 de ${{ids.length}} de esta empresa · ${{cola.length}} en total.</p>
    </div></div>`;
}}

function pintarListaEmpresas() {{
  const z = document.getElementById('zona-trabajo');
  const filtro = (document.getElementById('buscar').value || '').toLowerCase();
  const lista = D.empresas
    .map(e => ({{...e, faltan: pendientesDe(e.cliente).length}}))
    .filter(e => e.faltan && e.cliente.toLowerCase().includes(filtro));

  if (!lista.length) {{
    z.innerHTML = `<div class="caja vacio"><div class="grande">✓</div>
      <h3>${{filtro ? 'Ninguna empresa coincide' : 'Todo asignado'}}</h3>
      <p>${{filtro ? 'Pruebe con otro nombre.'
        : 'No queda ninguna empresa con depósitos pendientes.'}}</p></div>`;
    return;
  }}

  z.innerHTML = `<div class="caja">
    <h3>${{lista.length}} empresa(s) con depósitos por asignar</h3>
    <p style="color:var(--text-dim);font-size:13px;margin:0 0 14px;line-height:1.55">
      Ordenadas por urgencia: primero las que avisaron que ya pagaron —esas están
      recibiendo cobranza por error— luego las de mayor riesgo de impago, y después
      por monto.</p>
    <div class="tablewrap"><table>
      <tr><th>Empresa</th><th>Por asignar</th><th>Monto</th><th>Por qué urge</th><th></th></tr>
      ${{lista.map(e => `<tr>
        <td><b>${{e.cliente}}</b></td>
        <td class="num">${{e.faltan}}</td>
        <td class="num">${{soles(e.monto)}}</td>
        <td class="dim">${{e.motivos.length
          ? e.motivos.map(m => `<span class="badge" style="background:${{
              m.includes('pagó') ? 'var(--rose)' : m.includes('impago')
              ? 'var(--amber)' : 'var(--violet)'}};margin-right:4px">${{m}}</span>`).join('')
          : '—'}}</td>
        <td><button class="btn primario" style="width:auto;margin:0;padding:7px 14px;
          font-size:12.5px" onclick="abrirEmpresa('${{e.cliente}}')">Trabajar</button></td>
      </tr>`).join('')}}
    </table></div></div>`;
}}

function abrirEmpresa(nombre) {{
  if (!nombre) {{ empresaActiva = null; pintarTrabajo(); return; }}
  empresaActiva = D.empresas.some(e => e.cliente === nombre) ? nombre : null;
  pintarTrabajo();
}}
function volverLista() {{
  empresaActiva = null;
  document.getElementById('buscar').value = '';
  pintarTrabajo();
}}

function elegir(id, i) {{ seleccion[id] = i; pintarTrabajo(); }}
function marcar(id, nro) {{
  const l = seleccion[id] || [];
  seleccion[id] = l.includes(nro) ? l.filter(x => x !== nro) : [...l, nro];
  pintarTrabajo();
}}
function resolver(id, accion) {{
  const c = D.casos.find(x => x.id === id);
  let det = '', facturas = [];
  if (accion === 'asignado') {{
    const i = seleccion[id] ?? 0;
    det = 'opción ' + (i + 1);
    facturas = (c.opciones[i] || []).map(f => f.nro);
  }}
  if (accion === 'parcial') {{
    det = c.parcial.factura + ', queda ' + soles(c.parcial.resto);
    facturas = [c.parcial.factura];
  }}
  if (accion === 'manual') {{
    facturas = seleccion[id] || [];
    det = facturas.join(', ');
  }}
  // `facturas` es lo que convierte el registro en datos de entrenamiento: cada
  // caso que un humano resuelve es un ejemplo etiquetado para asignador.py.
  hechas[id] = {{accion, det, facturas, cliente: c.cliente, monto: c.monto,
                fecha: c.fecha, hora: new Date().toLocaleString('es-PE')}};
  localStorage.setItem(CLAVE, JSON.stringify(hechas));
  actualizarCuentas();
  pintarTrabajo();
}}

document.getElementById('lista-empresas').innerHTML =
  D.empresas.map(e => `<option value="${{e.cliente}}">`).join('');

/* ---------------- auditar ---------------- */
let auditActiva = null;

function pintarAuditoria() {{
  const z = document.getElementById('zona-auditoria');
  const rev = D.auditables.filter(a => hechas['aud-' + a.id]).length;
  const mal = D.auditables.filter(a => hechas['aud-' + a.id]?.accion === 'incorrecta').length;

  const resumen = `<div class="cards">
      <div class="card"><div class="metric">${{rev}}/${{D.auditables.length}}</div>
        <div class="label">Revisados de la muestra</div>
        <div class="bar"><i style="width:${{rev / D.auditables.length * 100}}%;
          background:var(--cyan)"></i></div></div>
      <div class="card"><div class="metric" style="color:${{mal ? 'var(--red)'
        : 'var(--green)'}}">${{mal}}</div><div class="label">Errores encontrados</div></div>
      <div class="card"><div class="metric">${{Math.round(
        (D.auditables.length - rev) * 20 / 60)}} min</div>
        <div class="label">Trabajo restante estimado</div></div>
    </div>`;

  if (!auditActiva) {{
    z.innerHTML = resumen + `<div class="caja">
      <h3>Clientes a auditar</h3>
      <p style="color:var(--text-dim);font-size:13px;margin:0 0 14px;line-height:1.55">
        Muestra de ${{D.auditables.length}} depósitos aplicados automáticamente.
        Revise cualquiera de la lista; el orden no importa.</p>
      <div class="tablewrap"><table>
        <tr><th>Empresa</th><th>Fecha</th><th>Depósito</th><th>Facturas</th>
          <th>Estado</th><th></th></tr>
        ${{D.auditables.map(a => {{
          const h = hechas['aud-' + a.id];
          return `<tr>
            <td><b>${{a.cliente}}</b></td><td class="mono">${{a.fecha}}</td>
            <td class="num">${{soles(a.monto)}}</td>
            <td class="num">${{a.facturas.length}}</td>
            <td>${{h ? `<span class="badge" style="background:${{
                h.accion === 'correcta' ? 'var(--green)' : 'var(--red)'}}">${{
                h.accion === 'correcta' ? 'Correcta' : 'Incorrecta'}}</span>`
              : '<span style="color:var(--text-dim)">Sin revisar</span>'}}</td>
            <td><button class="btn ${{h ? '' : 'primario'}}" style="width:auto;margin:0;
              padding:7px 14px;font-size:12.5px" onclick="verAudit('${{a.id}}')">
              ${{h ? 'Ver' : 'Revisar'}}</button></td></tr>`;
        }}).join('')}}
      </table></div></div>`;
    return;
  }}

  const a = D.auditables.find(x => x.id === auditActiva);
  const h = hechas['aud-' + a.id];
  z.innerHTML = resumen + `<div class="trabajo"><div class="caja">
      <button class="btn" style="width:auto;margin:0 0 12px" onclick="volverAudit()">
        ← Volver a la lista</button>
      <h3>¿Esta asignación automática fue correcta?</h3>
      <div class="deposito">
        <div><span>Empresa</span><b>${{a.cliente}}</b></div>
        <div><span>Depósito</span><b>${{soles(a.monto)}}</b></div>
        <div><span>Fecha</span><b>${{a.fecha}}</b></div>
      </div>
      <div style="font-family:var(--mono);font-size:12.5px;line-height:1.9">
        ${{a.facturas.map(f => `${{f.nro}} · ${{soles(f.importe)}} · vence ${{f.vence}}`)
          .join('<br>')}}</div>
      <div class="pista">Tenía ${{a.abiertas}} factura(s) abierta(s) ese día y esta fue la
        única combinación que sumaba exacto. La pregunta no es si la suma cuadra
        —eso ya está verificado— sino si tiene sentido que esta empresa pagara
        justo esas facturas.</div>
    </div>
    <div class="caja"><h3>Veredicto</h3>
      ${{h ? `<div class="alerta ${{h.accion === 'correcta' ? 'ok' : 'warn'}}">
        Ya revisado: <b>${{h.accion}}</b> · ${{h.hora}}</div>` : ''}}
      <button class="btn primario" onclick="auditar('${{a.id}}','correcta')">Correcta</button>
      <button class="btn" onclick="auditar('${{a.id}}','incorrecta')">
        Incorrecta — revertir</button>
    </div></div>`;
}}
function verAudit(id) {{ auditActiva = id; pintarAuditoria(); }}
function volverAudit() {{ auditActiva = null; pintarAuditoria(); }}
function auditar(id, veredicto) {{
  const a = D.auditables.find(x => x.id === id);
  hechas['aud-' + id] = {{accion: veredicto, det: 'auditoría', cliente: a.cliente,
    monto: a.monto, hora: new Date().toLocaleString('es-PE')}};
  localStorage.setItem(CLAVE, JSON.stringify(hechas));
  actualizarCuentas();
  auditActiva = null;   // vuelve a la lista para seguir con el siguiente
  pintarAuditoria();
}}

/* ---------------- registro ---------------- */
const NOMBRE = {{asignado:'Asignado', parcial:'Pago a cuenta', manual:'Asignado a mano',
  rechazado:'Devuelto', pospuesto:'Pospuesto', correcta:'Auditoría: correcta',
  incorrecta:'Auditoría: incorrecta'}};

function pintarRegistro() {{
  const z = document.getElementById('zona-registro');
  const filas = Object.entries(hechas);
  if (!filas.length) {{
    z.innerHTML = `<div class="caja vacio"><div class="grande">·</div>
      <h3>Sin decisiones todavía</h3>
      <p>Lo que resuelva en <b>Asignar depósitos</b> o <b>Auditar</b> queda aquí,
      con su hora y motivo.</p></div>`;
    return;
  }}
  z.innerHTML = `<div class="cards">
      <div class="card"><div class="metric">${{filas.length}}</div>
        <div class="label">Decisiones en esta sesión</div></div>
      <div class="card"><div class="metric">${{soles(
        filas.reduce((s, [, v]) => s + v.monto, 0))}}</div>
        <div class="label">Monto resuelto</div></div>
    </div>
    <div style="display:flex;gap:9px;margin-bottom:8px;flex-wrap:wrap">
      <button class="btn" style="width:auto;margin:0" onclick="descargar()">
        Descargar registro (CSV)</button>
      <button class="btn" style="width:auto;margin:0" onclick="descargarEntrenamiento()">
        Exportar para reentrenar</button>
      <button class="btn" style="width:auto;margin:0" onclick="deshacer()">
        Deshacer la última</button>
    </div>
    <p style="color:var(--text-dim);font-size:12px;margin:0 2px 14px;line-height:1.5">
      Cada caso que usted resuelve enseña al sistema. «Exportar para reentrenar»
      genera el archivo que el equipo técnico usa para que el modelo aprenda de
      sus decisiones y proponga mejor la próxima vez.</p>
    <div class="tablewrap"><table>
      <tr><th>Hora</th><th>Empresa</th><th>Monto</th><th>Decisión</th><th>Detalle</th></tr>
      ${{filas.reverse().map(([, v]) => `<tr><td class="mono">${{v.hora}}</td>
        <td>${{v.cliente}}</td><td class="num">${{soles(v.monto)}}</td>
        <td>${{NOMBRE[v.accion] || v.accion}}</td>
        <td class="dim mono">${{v.det || '—'}}</td></tr>`).join('')}}
    </table></div>`;
}}
function deshacer() {{
  const ks = Object.keys(hechas);
  if (!ks.length) return;
  delete hechas[ks[ks.length - 1]];
  localStorage.setItem(CLAVE, JSON.stringify(hechas));
  actualizarCuentas(); pintarRegistro();
}}
function bajarCSV(filas, nombre) {{
  const csv = filas.map(f => f.map(x => `"${{String(x).replace(/"/g, '""')}}"`).join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], {{type: 'text/csv;charset=utf-8'}}));
  a.download = nombre;
  a.click();
}}

function descargar() {{
  bajarCSV([['hora', 'empresa', 'monto', 'decision', 'detalle'],
    ...Object.values(hechas).map(v => [v.hora, v.cliente, v.monto,
      NOMBRE[v.accion] || v.accion, v.det || ''])], 'decisiones.csv');
}}

/* Exporta las decisiones en el formato que lee realimentacion.py: cada caso que
   un humano resolvió se convierte en un ejemplo etiquetado para reentrenar el
   asignador. Solo salen los que asignaron facturas — devolver o posponer no
   enseña nada. */
function descargarEntrenamiento() {{
  const utiles = Object.entries(hechas)
    .filter(([id, v]) => v.facturas && v.facturas.length);
  if (!utiles.length) {{
    alert('Todavía no hay decisiones con facturas asignadas para reentrenar.');
    return;
  }}
  bajarCSV([['id', 'cliente', 'fecha', 'monto', 'facturas', 'accion'],
    ...utiles.map(([id, v]) => [id, v.cliente, v.fecha || '', v.monto,
      v.facturas.join('|'), v.accion])], 'realimentacion.csv');
}}

function actualizarCuentas() {{
  document.getElementById('cuenta-asignar').textContent = porHacer().length;
  document.getElementById('cuenta-registro').textContent = Object.keys(hechas).length;
}}

actualizarCuentas();
const inicial = location.hash.slice(1);
if (inicial) ir(inicial, false);
</script>
</body></html>"""


if __name__ == "__main__":
    main()
