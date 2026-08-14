"""Orquestador (Agente Supervisor) — SON-IA.

Cumple los tres requisitos que la ficha exige explícitamente:

  1. IA agéntica con skills especializados  -> cuatro agentes operadores,
     cada uno con su dominio y sus herramientas.
  2. Orquestación por un supervisor          -> este módulo asigna, controla el
     resultado, escala lo que no se resuelve solo y encadena a los agentes
     entre sí (Cobranza entrega a Recaudo).
  3. Control de indicadores, calidad y tiempo -> cada decisión queda en el log
     de auditoría con marca de tiempo, y al final se reportan los KPIs.

Uso:
    python orquestador.py            # ejecuta el ciclo completo
    python orquestador.py --log      # además imprime el log de auditoría entero
"""

import datetime as dt
import sys

import datos
from agentes import bi, cobranza, correos, explicador, facturacion, recaudo

# Los tiempos por caso y el cálculo de carga viven en agentes/recaudo.py


class Supervisor:
    def __init__(self):
        self.log = []

    def _registrar(self, agente, accion, detalle):
        self.log.append({
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "agente": agente,
            "accion": accion,
            "detalle": detalle,
        })

    # ------------------------------------------------------------------ agentes

    def recaudo(self, facturas, pagos):
        self._registrar("Supervisor", "asignar", "Depósitos bancarios -> Agente de Recaudo")

        decisiones = recaudo.procesar(facturas, pagos)
        k = recaudo.kpis(decisiones)

        self._registrar(
            "Recaudo", "conciliacion_completada",
            f"{k['depositos_procesados']:,} depósitos · STP {k['stp_pct']}% "
            f"(S/ {k['monto_aplicado_solo_soles']:,.0f} aplicados sin intervención)",
        )

        for cola in ("CONFIRMAR", "HIPOTESIS", "INVESTIGAR"):
            n = int((decisiones.cola == cola).sum())
            if n:
                self._registrar("Supervisor", "encolar_para_humano",
                                f"{n} casos a la cola {cola}: {recaudo.COLAS[cola]}")

        # Muestra de casos escalados, ya redactados para el operador.
        muestra = decisiones[decisiones.cola != "AUTO"].nlargest(3, "monto")
        for caso in muestra.to_dict("records"):
            self._registrar("Recaudo", "escalar_a_humano",
                            f"{caso['cliente']} S/ {caso['monto']:,.2f} — {explicador.explicar(caso)}")

        return decisiones, k

    def facturacion(self, fija, movil, facturas, ncs):
        self._registrar("Supervisor", "asignar", "Planta vs. facturación -> Agente de Facturación")

        fuga = facturacion.detectar_fuga(fija, movil, facturas)
        impacto = facturacion.estimar_impacto(fuga, facturas)
        cal = facturacion.calidad(facturas, ncs)
        k = facturacion.kpis(fuga, impacto, cal)

        self._registrar(
            "Facturación", "fuga_detectada",
            f"{k['clientes_con_fuga']} clientes con servicio activo y facturación atrasada "
            f"({k['nunca_facturados']} nunca facturado) · impacto S/ {k['impacto_estimado_soles']:,.0f}",
        )
        self._registrar(
            "Facturación", "calidad_medida",
            f"Tasa de notas de crédito: {k['tasa_error_facturacion_pct']}% "
            f"({cal['facturas_con_nota_credito']} de {cal['total_facturas']:,}) — línea base a reducir",
        )
        for caso in impacto.head(3).to_dict("records"):
            self._registrar("Supervisor", "alertar_facturacion",
                            f"{caso['RAZON_SOCIAL']}: {caso['motivo']} S/ {caso['impacto_soles']:,.2f}")

        return fuga, impacto, k

    def bi(self, clientes, facturas, pagos, fuga):
        self._registrar("Supervisor", "asignar",
                        "Resultados de Recaudo + Facturación -> Agente de BI")

        pcd = bi.calcular_pcd(clientes, facturas, pagos)
        aging = bi.calcular_aging(facturas, pagos)
        prioridad = bi.priorizar(pcd, fuga)
        k = bi.kpis(pcd, aging)

        self._registrar(
            "BI", "pcd_calculado",
            f"{k['clientes_riesgo_alto']} clientes en riesgo ALTO, que deben "
            f"S/ {k['deuda_de_los_riesgo_alto_soles']:,.0f} de un total pendiente de "
            f"S/ {k['deuda_pendiente_total_soles']:,.0f}",
        )
        self._registrar(
            "BI", "aging_calculado",
            f"Mayor concentración en '{k['bucket_mayor_concentracion']}' con "
            f"S/ {k['monto_bucket_mayor_soles']:,.0f} (corte: {aging.attrs['fecha_corte']:%Y-%m-%d})",
        )
        for caso in prioridad.head(3).to_dict("records"):
            self._registrar("Supervisor", "priorizar_cobranza",
                            f"{caso['RAZON_SOCIAL']} ({caso['nivel_pcd']}): {caso['estrategia']}")

        return pcd, aging, prioridad, k

    def cobranza(self, decisiones_recaudo):
        self._registrar("Supervisor", "asignar",
                        f"{len(correos.CORREOS)} correos entrantes -> Agente de Cobranza")

        clasificados = cobranza.clasificar_lote(correos.CORREOS)
        k = cobranza.kpis(clasificados)

        self._registrar("Cobranza", "clasificacion_completada",
                        f"{k['correos_procesados']} correos (motor: {k['motor']}) — " +
                        ", ".join(f"{c}={n}" for c, n in k["distribucion"].items()))

        # El traspaso real entre agentes: cada confirmación de pago se contrasta
        # contra lo que Recaudo ya sabe de ese cliente.
        confirmaciones = [c for c in clasificados if c["categoria"] == "CONFIRMACION_PAGO"]
        for c in confirmaciones:
            suyos = decisiones_recaudo[decisiones_recaudo.cliente == c["cliente"]]
            pendientes = suyos[suyos.cola != "AUTO"]
            if len(pendientes):
                self._registrar(
                    "Cobranza", "traspaso_a_recaudo",
                    f"{c['cliente']} dice haber pagado y tiene {len(pendientes)} depósito(s) "
                    f"sin conciliar por S/ {pendientes.monto.sum():,.2f} — Recaudo prioriza el caso",
                )
            elif len(suyos):
                self._registrar(
                    "Cobranza", "cerrar_sin_gestion",
                    f"{c['cliente']} dice haber pagado y sus {len(suyos)} depósito(s) ya están "
                    f"aplicados — sacar de la ruta de cobranza, no volver a llamarlo",
                )
        return clasificados, k

    # ------------------------------------------------------------------ reportes

    def carga_humana(self, decisiones):
        return recaudo.carga_humana(decisiones)

    def imprimir_log(self):
        print("\n" + "=" * 78)
        print("LOG DE AUDITORÍA")
        print("=" * 78)
        for e in self.log:
            print(f"[{e['ts']}] {e['agente']:<12} {e['accion']:<24} {e['detalle']}")


def main():
    print("Cargando datos del reto...\n")
    f = datos.facturas()
    p = datos.pagos()
    ncs = datos.notas_credito()
    clientes = datos.clientes()
    fija = datos.planta_fija()
    movil = datos.planta_movil()

    s = Supervisor()

    decisiones, k_recaudo = s.recaudo(f, p)
    fuga, impacto, k_fact = s.facturacion(fija, movil, f, ncs)
    pcd, aging, prioridad, k_bi = s.bi(clientes, f, p, fuga)
    clasificados, k_cob = s.cobranza(decisiones)

    if "--log" in sys.argv:
        s.imprimir_log()
    else:
        print("(log de auditoría completo con --log; se muestran los hitos)\n")
        for e in s.log:
            if e["accion"] not in ("asignar",):
                print(f"  · {e['agente']:<12} {e['detalle']}")

    carga = s.carga_humana(decisiones)

    print("\n" + "=" * 78)
    print("INDICADORES")
    print("=" * 78)
    for titulo, k in [("RECAUDO", k_recaudo), ("FACTURACIÓN", k_fact),
                      ("BI", k_bi), ("COBRANZA", k_cob)]:
        print(f"\n{titulo}")
        for nombre, valor in k.items():
            if isinstance(valor, float):
                valor = f"{valor:,.2f}"
            elif isinstance(valor, int):
                valor = f"{valor:,}"
            print(f"    {nombre:<34} {valor}")

    print(f"\nCARGA HUMANA")
    print(f"    {'minutos_por_dia_habil':<34} {carga['minutos_por_dia_habil']}")
    print(f"    {'fte':<34} {carga['fte']}  (una persona a tiempo parcial)")
    print("\n" + "=" * 78)
    print("Precisión medida contra ground truth:  python backtest.py")
    print("Desglose de la cola humana:            python triaje.py")
    print("=" * 78)


if __name__ == "__main__":
    main()
