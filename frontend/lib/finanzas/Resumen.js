"use client";

/**
 * El mes de un vistazo: lo que entró, lo que salió, lo que queda y lo
 * que falta por cobrar o por pagar. Más abajo, de dónde vino y en qué se
 * fue, y los últimos seis meses lado a lado.
 */

import { useEffect, useState } from "react";

import { api, readObject } from "../api";
import { Cifra, descargar, dinero, mesCorto, rejillaCifras } from "./comunes";

function comparar(actual, anterior) {
  const a = Number(actual), b = Number(anterior);
  if (!b) return null;
  const cambio = Math.round(((a - b) / Math.abs(b)) * 100);
  if (cambio === 0) return "igual que el mes anterior";
  return `${cambio > 0 ? "+" : ""}${cambio} % frente al mes anterior`;
}

export default function Resumen({ mes, irA }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setDatos(null); setError("");
    api(`/finanzas/resumen/?mes=${mes}`).then(readObject).then(setDatos)
      .catch((e) => setError(e.message));
  }, [mes]);

  async function excel() {
    setError("");
    try { await descargar(`/finanzas/exportar/?mes=${mes}`, `finanzas-${mes}.xlsx`); }
    catch (e) { setError(e.message); }
  }

  if (error) return <div className="error-box">{error}</div>;
  if (!datos) return <div className="card"><div className="empty">Cargando…</div></div>;

  const utilidad = Number(datos.utilidad);
  const obligaciones = datos.obligaciones || [];
  const pendientePersonal = Number(datos.honorarios_pendientes) + Number(datos.roles_pendientes)
    + obligaciones.reduce((s, o) => s + Number(o.monto), 0);

  return (
    <div>
      <div style={rejillaCifras}>
        <Cifra titulo="Ingresos cobrados" valor={dinero(datos.ingresos)} color="var(--petrol)"
               nota={comparar(datos.ingresos, datos.mes_anterior.ingresos)
                 || `${datos.cobros} cobro${datos.cobros === 1 ? "" : "s"}`} />
        <Cifra titulo="Egresos pagados" valor={dinero(datos.egresos)}
               nota={comparar(datos.egresos, datos.mes_anterior.egresos)} />
        <Cifra titulo={utilidad < 0 ? "Pérdida" : "Utilidad"} valor={dinero(datos.utilidad)}
               color={utilidad < 0 ? "var(--red)" : "var(--green)"}
               nota={datos.margen != null ? `Margen ${String(datos.margen).replace(".", ",")} %` : null} />
        <Cifra titulo="Por cobrar a pacientes" valor={dinero(datos.por_cobrar)}
               nota={Number(datos.por_cobrar_vencido) > 0 ? `${dinero(datos.por_cobrar_vencido)} vencido` : "Cuotas pendientes"}
               alerta={Number(datos.por_cobrar_vencido) > 0} />
      </div>

      {(Number(datos.por_pagar) > 0 || pendientePersonal > 0) && (
        <div className="card" style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
          <strong style={{ fontSize: 14 }}>Pendiente de pagar</strong>
          {Number(datos.por_pagar) > 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => irA("egresos")}>
              Cuentas por pagar: <span className="tabular" style={{ marginLeft: 4 }}>{dinero(datos.por_pagar)}</span>
              {Number(datos.por_pagar_vencido) > 0 && (
                <span className="badge badge-danger" style={{ marginLeft: 8 }}>{dinero(datos.por_pagar_vencido)} vencido</span>
              )}
            </button>
          )}
          {Number(datos.honorarios_pendientes) > 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => irA("honorarios")}>
              Honorarios: <span className="tabular" style={{ marginLeft: 4 }}>{dinero(datos.honorarios_pendientes)}</span>
            </button>
          )}
          {obligaciones.map((o) => (
            <button key={`${o.tipo}-${o.periodo}`} type="button" className="btn btn-ghost" onClick={() => irA("obligaciones")}>
              {o.tipo === "iess" ? "IESS" : "SRI"} {mesCorto(o.periodo)}:
              <span className="tabular" style={{ marginLeft: 4 }}>{dinero(o.monto)}</span>
            </button>
          ))}
          {Number(datos.roles_pendientes) > 0 && (
            <button type="button" className="btn btn-ghost" onClick={() => irA("roles")}>
              Sueldos: <span className="tabular" style={{ marginLeft: 4 }}>{dinero(datos.roles_pendientes)}</span>
            </button>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 18, alignItems: "start" }}>
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>Últimos seis meses</h3>
          <Serie filas={datos.serie} />
        </div>
        <div className="card">
          <h3 style={{ marginBottom: 12 }}>En qué se fue el dinero</h3>
          <Barras filas={datos.egresos_por_categoria.map((f) => [f.categoria, f.total])}
                  vacio="Sin egresos este mes." color="var(--amber)" />
          <h3 style={{ margin: "18px 0 12px" }}>Cómo pagaron los pacientes</h3>
          <Barras filas={datos.ingresos_por_forma.map((f) => [f.forma, f.total])}
                  vacio="Sin cobros este mes." color="var(--petrol)" />
        </div>
      </div>

      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h3>Para el contador</h3>
          <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
            Un Excel con los cobros, los egresos con RUC y número de factura, los honorarios con su retención y el rol de pagos del mes.
          </p>
        </div>
        <button type="button" className="btn btn-primary" onClick={excel}>⬇ Descargar Excel del mes</button>
      </div>
    </div>
  );
}

function Barras({ filas, vacio, color }) {
  const visibles = filas.filter(([, v]) => Number(v) > 0);
  if (!visibles.length) return <div style={{ fontSize: 14, color: "var(--ink-soft)" }}>{vacio}</div>;
  const max = Math.max(...visibles.map(([, v]) => Number(v)));
  return visibles.map(([nombre, valor]) => (
    <div key={nombre} style={{ marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
        <span>{nombre}</span>
        <span className="tabular" style={{ fontWeight: 600 }}>{dinero(valor)}</span>
      </div>
      <div style={{ height: 8, borderRadius: 4, background: "var(--line)" }}>
        <div style={{ height: "100%", borderRadius: 4, background: color, width: `${(Number(valor) / max) * 100}%`, minWidth: 6 }} />
      </div>
    </div>
  ));
}

/** Barras dobles por mes: ingresos y egresos, con la utilidad debajo. */
function Serie({ filas }) {
  const max = Math.max(1, ...filas.flatMap((f) => [Number(f.ingresos), Number(f.egresos)]));
  const alto = 120;
  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", height: alto + 4 }}>
        {filas.map((f) => (
          <div key={f.mes} style={{ flex: 1, display: "flex", gap: 3, alignItems: "flex-end", justifyContent: "center" }}
               title={`${f.mes}: ingresos ${dinero(f.ingresos)}, egresos ${dinero(f.egresos)}`}>
            <div style={{ width: "40%", maxWidth: 18, borderRadius: "4px 4px 0 0", background: "var(--petrol)",
                          height: Math.max(2, (Number(f.ingresos) / max) * alto) }} />
            <div style={{ width: "40%", maxWidth: 18, borderRadius: "4px 4px 0 0", background: "var(--amber)",
                          height: Math.max(2, (Number(f.egresos) / max) * alto) }} />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, borderTop: "1px solid var(--line)", paddingTop: 6 }}>
        {filas.map((f) => (
          <div key={f.mes} style={{ flex: 1, textAlign: "center", fontSize: 12 }}>
            <div style={{ color: "var(--ink-soft)", textTransform: "capitalize" }}>{mesCorto(f.mes)}</div>
            <div className="tabular" style={{ fontWeight: 600, color: Number(f.utilidad) < 0 ? "var(--red)" : "var(--ink)" }}>
              {Number(f.utilidad) === 0 ? "—" : dinero(f.utilidad, 0)}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
        <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "var(--petrol)", marginRight: 5 }} />Ingresos</span>
        <span><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: "var(--amber)", marginRight: 5 }} />Egresos</span>
        <span>Debajo, la utilidad de cada mes</span>
      </div>
    </div>
  );
}
